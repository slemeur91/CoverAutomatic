"""Cover movements: state changes, manual override detection, lost commands, travel time.

Mixin of CoverAutomaticCoordinator: it uses the coordinator's attributes."""
from __future__ import annotations

import logging
from typing import Any

from . import coordinator_common as common
from .coordinator_common import (
    _UNUSABLE_STATES,
    MANUAL_OVERRIDE_TOLERANCE,
    MAX_LOST_COMMAND_RETRIES,
    MAX_MEASURED_TRAVEL,
    MAX_TRAVEL_GROWTH,
    MIN_MEASURED_DISTANCE,
    SETTLE_TIME,
    STARTUP_GRACE_PERIOD,
    TRAVEL_TIME_MARGIN,
)
from .models import CoverStatus

# Same logger as the coordinator: the split does not change the log names
_LOGGER = logging.getLogger(__package__ + ".coordinator")


class MotionMixin:
    """Cover movements: state changes, manual override detection, lost commands, travel time."""

    def _update_last_position_from_state(self, entity_id: str) -> None:
        """Update _last_positions and _last_tilt_positions from current HA state."""
        state = self.hass.states.get(entity_id)
        if state and state.state not in ("unavailable", "unknown"):
            position = self._raw_position(state)
            if position is not None:
                self._last_positions[entity_id] = position
            else:
                _LOGGER.debug(
                    "Invalid position attribute for %s, resetting tracked position",
                    entity_id,
                )
                self._last_positions[entity_id] = None
            tilt_val = state.attributes.get("current_tilt_position")
            if tilt_val is not None:
                try:
                    self._last_tilt_positions[entity_id] = int(tilt_val)
                except (ValueError, TypeError):
                    self._last_tilt_positions[entity_id] = None

    def _handle_cover_state_change(  # noqa: C901 -- complexity 20, to reduce (see CHANGELOG 2.1.3)
        self, entity_id: str, old_state: Any, new_state: Any
    ) -> None:
        """Handle cover position changes to detect manual overrides."""
        if new_state is None:
            return

        cover = self.storage.covers.get(entity_id)
        if cover is None:
            return

        # Ignore unavailable/unknown states (e.g. during HA shutdown)
        if new_state.state in ("unavailable", "unknown"):
            return

        # Motion bookkeeping first: it must also see the reports received
        # during the grace, wind and settle periods ignored below.
        self._record_motion(entity_id, old_state, new_state)

        # Learn the cover's travel time from our own moves (feeds the settle time)
        self._measure_travel(entity_id, new_state)

        # Ignore during startup grace period (device reconnection can report
        # positions that differ from HA's persisted state)
        if (common.time_mod.monotonic() - self._startup_time) < STARTUP_GRACE_PERIOD:
            return

        # Ignore manual overrides during wind protection
        if self._wind_protected:
            return

        # Ignore position changes while cover is moving
        if new_state.state in ("opening", "closing"):
            return

        current_position = self._raw_position(new_state)

        # Ignore position changes during settle time after our own commands.
        # A report closer to our target restarts the settle time: some
        # gateways (Velux KLF 200) report neither opening/closing nor regular
        # positions, and queue the commands of several covers -- the move
        # then lasts longer than the learned travel time, and its last
        # positions must not be read as a manual override.
        last_cmd = self._last_command_time.get(entity_id, 0)
        if (common.time_mod.monotonic() - last_cmd) < self._settle_time(entity_id):
            if (
                current_position is not None
                and entity_id in self._pending_settle
                and self._is_progressing_to_target(entity_id, old_state, current_position)
            ):
                self._last_command_time[entity_id] = common.time_mod.monotonic()
            return

        if current_position is None:
            return

        # Closed -> open or open -> closed without a command from us: the
        # cover moved, whatever position it reports first (a Velux gateway
        # may first report 1-2 % while the cover is already opening).
        state_flip = (
            old_state is not None
            and old_state.state in ("open", "closed")
            and new_state.state in ("open", "closed")
            and old_state.state != new_state.state
        )

        # Slow covers that do not report opening/closing: while the position
        # keeps moving towards our own target, the cover is still travelling
        # from our command -- extend the settle window instead of reading the
        # intermediate position as a manual override.
        if entity_id in self._pending_settle and self._is_progressing_to_target(
            entity_id, old_state, current_position
        ):
            self._last_command_time[entity_id] = common.time_mod.monotonic()
            return

        # After settle time, sync actual position before override check
        # (HmIP actuators may not reach exact target position)
        if entity_id in self._pending_settle:
            self._pending_settle.discard(entity_id)
            expected_target = self._last_positions.get(entity_id)
            cover_raw = self.storage.get_cover_raw(entity_id)
            settle_threshold = (
                self._cover_val(cover_raw, "min_position_change") if cover_raw else MANUAL_OVERRIDE_TOLERANCE
            )
            if expected_target is not None and (
                abs(current_position - expected_target) > settle_threshold
                or (state_flip and current_position != expected_target)
            ):
                _LOGGER.debug(
                    "[%s] Post-settle: large deviation %d%% vs expected %d%%, checking override",
                    entity_id, current_position, expected_target,
                )
                if self._resend_if_lost(entity_id, current_position):
                    return
                # Fall through to override check below
            else:
                self._last_positions[entity_id] = current_position
                self._sync_tilt_from_state(entity_id, new_state)
                _LOGGER.debug(
                    "[%s] Post-settle sync: position %d%%",
                    entity_id, current_position,
                )
                return

        expected_position = self._last_positions.get(entity_id)

        position_mismatch = expected_position is not None and (
            abs(current_position - expected_position) >= MANUAL_OVERRIDE_TOLERANCE
            or (state_flip and current_position != expected_position)
        )

        # Check tilt mismatch if cover supports tilt
        tilt_mismatch = False
        expected_tilt = self._last_tilt_positions.get(entity_id)
        if expected_tilt is not None:
            current_tilt_val = new_state.attributes.get("current_tilt_position")
            if current_tilt_val is not None:
                try:
                    current_tilt = int(current_tilt_val)
                    if abs(current_tilt - expected_tilt) >= MANUAL_OVERRIDE_TOLERANCE:
                        tilt_mismatch = True
                except (ValueError, TypeError):
                    pass

        if position_mismatch or tilt_mismatch:
            if entity_id in self._safety_holds:
                # A safety rule drives the cover: no pause, the next cycle
                # re-applies the rule's position.
                _LOGGER.debug("[%s] Position change ignored: safety rule active", entity_id)
                return
            if cover.auto_enabled and self._cover_states.get(entity_id) in (CoverStatus.AUTO, CoverStatus.VENTING):
                details = self._override_details(entity_id, expected_position, current_position)
                _LOGGER.info(
                    "[%s] Manual override -> PAUSED (expected pos %s, got %s, expected tilt %s, "
                    "state %s -> %s, first report after last command: %s %% after %s s)",
                    entity_id,
                    expected_position,
                    current_position,
                    expected_tilt,
                    old_state.state if old_state is not None else None,
                    new_state.state,
                    details.get("first_position"),
                    details.get("first_after"),
                )
                self.pause_cover(cover, details=details)

    def _record_motion(self, entity_id: str, old_state: Any, new_state: Any) -> None:
        """Record position/motion changes of a cover (not attribute-only reports).

        Two uses:
        - the time of the last real change (position, state, opening /
          closing) feeds the stillness check of resume-on-match: Zigbee
          covers re-report attributes (linkquality) every few seconds, so
          state.last_updated never looks still;
        - whether the cover moved at all since our last command, even during
          the settle time: a user counter-order (up/stop) during our move
          brings the cover back to its start position, which must not be
          read as a lost command and resent.
        """
        new_pos = self._raw_position(new_state)
        moving = new_state.state in ("opening", "closing")
        old_usable = old_state is not None and old_state.state not in _UNUSABLE_STATES
        old_pos = self._raw_position(old_state) if old_usable else None
        changed = moving or not old_usable or old_state.state != new_state.state or old_pos != new_pos
        if changed:
            self._runtime_dict("_position_changed_at")[entity_id] = common.time_mod.monotonic()
            # First position reported after our last command (diagnostics)
            sent_at = self._runtime_dict("_command_sent_at").get(entity_id)
            first = self._runtime_dict("_first_report")
            if sent_at is not None and new_pos is not None and entity_id not in first:
                first[entity_id] = {
                    "position": new_pos,
                    "after": round(common.time_mod.monotonic() - sent_at, 1),
                }
        move = self._move_start.get(entity_id)
        if move is not None and (
            moving or (new_pos is not None and abs(new_pos - move[1]) > MANUAL_OVERRIDE_TOLERANCE)
        ):
            self._runtime_set("_moved_since_command").add(entity_id)

    def _data_raw_target(
        self, entity_id: str, cover_raw: dict[str, Any], status: CoverStatus
    ) -> int | None:
        """Raw position the current cycle data asks for (as the apply cycle sends it)."""
        cover_data = ((self.data or {}).get("covers") or {}).get(entity_id) or {}
        target = cover_data.get("target_position")
        if not isinstance(target, (int, float)) or isinstance(target, bool):
            return None
        target = int(target)
        if status == CoverStatus.VENTING:
            vent_min = self._cover_val(cover_raw, "vent_position")
            if isinstance(vent_min, (int, float)) and not isinstance(vent_min, bool):
                target = max(target, int(vent_min))
        if cover_raw.get("inverted", False):
            target = 100 - target
        return self._effective_position(entity_id, target)

    def _resend_if_lost(self, entity_id: str, current: int) -> bool:
        """Resend a position command the cover did not react to at all.

        After the settle time, a cover still at the start position of our
        own move (raw positions) most likely never received the command
        (radio/cloud command lost). That is not a manual override: resend
        the command, at most MAX_LOST_COMMAND_RETRIES times, instead of
        pausing the automation. Returns True when the command was resent.

        Never resent when the cover moved at all since the command (a user
        counter-order also ends at the start position), when the automation
        is off, or when the command is no longer what the rules ask for.
        """
        if not self.storage.enabled:
            return False
        move = self._move_start.get(entity_id)
        if move is None:
            return False
        if entity_id in self._runtime_set("_moved_since_command"):
            _LOGGER.debug("[%s] Cover moved since our command: not a lost command", entity_id)
            return False
        _, start_pos, target = move
        if (
            abs(current - start_pos) > MANUAL_OVERRIDE_TOLERANCE
            or abs(current - target) <= MANUAL_OVERRIDE_TOLERANCE
            or self._last_positions.get(entity_id) != target
            or self._wind_protected
        ):
            return False
        # Only moves the apply cycle may still drive: AUTO/VENTING, or a
        # paused/manual cover held by a safety rule (never LOCKED / wind).
        status = self._cover_states.get(entity_id, CoverStatus.AUTO)
        if status in (CoverStatus.LOCKED, CoverStatus.WIND_PROTECTED) or (
            status not in (CoverStatus.AUTO, CoverStatus.VENTING)
            and entity_id not in self._safety_holds
        ):
            return False
        cover_raw = self.storage.get_cover_raw(entity_id)
        if cover_raw is None or self._data_raw_target(entity_id, cover_raw, status) != target:
            return False
        if self._blocked_by_unknown_lock(entity_id, cover_raw, target, current):
            return False
        if self._lost_command_retries is None:
            self._lost_command_retries = {}
        retries = self._lost_command_retries.get(entity_id, 0)
        if retries >= MAX_LOST_COMMAND_RETRIES:
            _LOGGER.warning(
                "[%s] Cover did not move to %d%% after %d resends (still at %d%%)",
                entity_id, target, retries, current,
            )
            self._lost_command_retries.pop(entity_id, None)
            self._move_start.pop(entity_id, None)
            return False
        self._lost_command_retries[entity_id] = retries + 1
        _LOGGER.warning(
            "[%s] Command %d%% apparently lost (cover still at %d%%), resending (%d/%d)",
            entity_id, target, current, retries + 1, MAX_LOST_COMMAND_RETRIES,
        )
        now = common.time_mod.monotonic()
        self._last_command_time[entity_id] = now
        self._move_start[entity_id] = (now, start_pos, target)
        self._pending_settle.add(entity_id)
        self.hass.async_create_task(self._position_call(entity_id, target))
        return True

    def _travel_time(self, entity_id: str) -> float | None:
        """Full travel time of a cover.

        Order: value entered on the cover, then the measured value, then the
        global default travel time; None when none is known (30 s settle).
        """
        def _positive(value: Any) -> float | None:
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return float(value)
            return None

        cover_raw = self.storage.get_cover_raw(entity_id)
        if isinstance(cover_raw, dict):
            for key in ("travel_time", "measured_travel_time"):
                if (value := _positive(cover_raw.get(key))) is not None:
                    return value
        return _positive(getattr(self.storage, "default_travel_time", None))

    def _settle_time(self, entity_id: str) -> float:
        """Seconds after our own command during which moves are not manual.

        At least SETTLE_TIME; longer for slow covers whose full travel time
        (configured or measured) plus a margin exceeds it.
        """
        travel = self._travel_time(entity_id)
        if travel is None:
            return SETTLE_TIME
        return max(SETTLE_TIME, travel + TRAVEL_TIME_MARGIN)

    def _measure_travel(self, entity_id: str, new_state: Any) -> None:
        """Measure the full travel time when a commanded move reaches its target.

        Only moves of at least MIN_MEASURED_DISTANCE % are used, scaled to a
        full 0-100 % travel, and smoothed with the previous measurement. A
        polled cover reports its arrival late (next poll): a new sample is
        capped at MAX_TRAVEL_GROWTH x the previous value so one late poll
        cannot inflate the settle time.
        """
        start = self._move_start.get(entity_id)
        if start is None:
            return
        started_at, start_pos, target = start
        elapsed = common.time_mod.monotonic() - started_at
        if elapsed > MAX_MEASURED_TRAVEL:
            self._move_start.pop(entity_id, None)
            return
        if new_state.state in ("opening", "closing"):
            return
        try:
            position = int(new_state.attributes.get("current_position"))
        except (ValueError, TypeError):
            return
        if abs(position - target) > MANUAL_OVERRIDE_TOLERANCE:
            return
        self._move_start.pop(entity_id, None)
        # The command arrived: a later lost command gets fresh resends
        if self._lost_command_retries:
            self._lost_command_retries.pop(entity_id, None)
        distance = abs(start_pos - target)
        if distance < MIN_MEASURED_DISTANCE or elapsed < 1:
            return
        full = min(elapsed * 100 / distance, MAX_MEASURED_TRAVEL)
        cover_raw = self.storage.get_cover_raw(entity_id)
        previous = cover_raw.get("measured_travel_time") if isinstance(cover_raw, dict) else None
        if isinstance(previous, (int, float)) and not isinstance(previous, bool) and previous > 0:
            if full > previous * MAX_TRAVEL_GROWTH:
                # Capped sample: already a bounded step up. Averaging it with
                # the previous value again halved the growth, so a cover whose
                # first measurement was too short needed many moves to reach
                # its real travel time (settle time too short meanwhile).
                full = previous * MAX_TRAVEL_GROWTH
            else:
                full = (previous + full) / 2
        full = round(full, 1)
        _LOGGER.debug("[%s] Measured travel time: %.1f s", entity_id, full)
        self.storage.update_cover_measured_travel(entity_id, full)

    def _override_details(self, entity_id: str, expected: int | None, actual: int) -> dict[str, Any]:
        """Why a manual pause was decided, for the activity log and the logbook.

        Expected and read positions (raw, as the cover reports them), and the
        first position reported after our last command with its delay -- a
        gateway may announce the target at once (a lost command then looks
        like a move), or report a cover late.
        """
        details: dict[str, Any] = {"expected": expected, "actual": actual}
        first = self._runtime_dict("_first_report").get(entity_id)
        if first is not None:
            details["first_position"] = first["position"]
            details["first_after"] = first["after"]
        return details

    def _moving_on_its_own(self, entity_id: str, current: int) -> bool:
        """Whether the cover moved a moment ago and is not where we left it.

        Its position changed less than its settle time ago and differs from
        the position we expect: someone else may be moving it (remote,
        vendor app) while the gateway reports no opening/closing state.
        """
        changed_at = self._runtime_dict("_position_changed_at").get(entity_id)
        expected = self._last_positions.get(entity_id)
        return (
            changed_at is not None
            and expected is not None
            and current != expected
            and (common.time_mod.monotonic() - changed_at) < self._settle_time(entity_id)
        )

    def _is_progressing_to_target(
        self, entity_id: str, old_state: Any, current_position: int
    ) -> bool:
        """Return True if the cover moved strictly closer to its commanded target."""
        target = self._last_positions.get(entity_id)
        if target is None or old_state is None:
            return False
        try:
            old_position = int(old_state.attributes.get("current_position"))
        except (ValueError, TypeError):
            return False
        return abs(current_position - target) < abs(old_position - target)

"""Applying rule positions and tilts to the covers.

Mixin of CoverAutomaticCoordinator: it uses the coordinator's attributes."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from . import coordinator_common as common
from . import i18n
from .const import (
    LOG_EVENT_POSITION,
    SET_POSITION_FEATURE_FLAG,
    TILT_COMMAND_DELAY,
    TILT_FEATURE_FLAG,
)
from .coordinator_common import (
    MANUAL_OVERRIDE_TOLERANCE,
)
from .models import CoverStatus

# Same logger as the coordinator: the split does not change the log names
_LOGGER = logging.getLogger(__package__ + ".coordinator")


class ApplyMixin:
    """Applying rule positions and tilts to the covers."""

    def _sync_tilt_from_state(self, entity_id: str, state: Any) -> None:
        """Sync _last_tilt_positions from cover state attributes."""
        tilt_val = state.attributes.get("current_tilt_position")
        if tilt_val is not None:
            try:
                self._last_tilt_positions[entity_id] = int(tilt_val)
            except (ValueError, TypeError):
                pass

    @staticmethod
    def _raw_position(state: Any) -> int | None:
        """HA position of a cover state (raw, not inverted).

        Covers without a current_position attribute (open/close only) are
        read from their state instead of being taken for closed (0).
        """
        value = state.attributes.get("current_position")
        if value is None:
            return {"open": 100, "closed": 0}.get(state.state)
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _supports_set_position(self, entity_id: str) -> bool:
        """Whether a cover accepts set_cover_position.

        Covers that only support open/close (some RTS / relay covers) must
        get open_cover / close_cover instead; set_cover_position is rejected
        by them. Without a supported_features attribute the cover is assumed
        to support positions (previous behaviour).
        """
        state = self.hass.states.get(entity_id)
        if state is None:
            return True
        features = state.attributes.get("supported_features")
        if isinstance(features, bool) or not isinstance(features, int):
            return True
        return bool(features & SET_POSITION_FEATURE_FLAG)

    def _effective_position(self, entity_id: str, position: int) -> int:
        """Raw position a command really reaches (open/close-only: 0 or 100)."""
        if self._supports_set_position(entity_id):
            return position
        return 100 if position >= 50 else 0

    def _position_call(self, entity_id: str, position: int) -> Any:
        """Service call moving a cover to a raw position (awaitable).

        Open/close-only covers are opened from 50 % up, closed below.
        """
        if self._supports_set_position(entity_id):
            return self.hass.services.async_call(
                "cover", "set_cover_position",
                {"entity_id": entity_id, "position": position},
                blocking=False,
            )
        service = "open_cover" if position >= 50 else "close_cover"
        return self.hass.services.async_call(
            "cover", service, {"entity_id": entity_id}, blocking=False,
        )

    async def _async_send_position(self, entity_id: str, position: int) -> None:
        """Send a raw position to a cover (see _position_call)."""
        await self._position_call(entity_id, position)

    def _get_current_position(self, entity_id: str) -> int | None:
        """Get current cover position (handles inverted covers)."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        pos = self._raw_position(state)
        if pos is None:
            return None
        cover_raw = self.storage.get_cover_raw(entity_id)
        if cover_raw and cover_raw.get("inverted", False):
            pos = 100 - pos
        return pos

    async def async_apply_positions(self) -> None:
        """Apply calculated positions to covers with hysteresis.

        Serialised: an apply cycle sleeping in the command stagger must not
        interleave with the next one (a stale target could be sent after a
        newer one, or both cycles command the same cover).
        """
        if self._apply_lock is None:
            self._apply_lock = asyncio.Lock()
        async with self._apply_lock:
            await self._async_apply_positions_locked()

    async def _async_apply_positions_locked(self) -> None:
        """Apply calculated positions (caller holds the apply lock)."""
        if not self.data:
            return

        now = common.dt_util.now().timestamp()
        stagger = self.storage.command_stagger
        command_sent = False

        for entity_id, cover_data in self.data.get("covers", {}).items():
            # Use live status from _cover_states instead of snapshot
            status = self._cover_states.get(entity_id, CoverStatus.AUTO)
            # A safety rule also drives paused/manual/wind covers (never LOCKED)
            safety = cover_data.get("safety") is True and status != CoverStatus.LOCKED
            if status not in (CoverStatus.AUTO, CoverStatus.VENTING) and not safety:
                # A new protective/paused state supersedes a pending
                # protective-exit bypass -- drop it so it cannot skip the
                # time hysteresis on an unrelated move later.
                self._post_protective_exit.discard(entity_id)
                self._hysteresis_info[entity_id] = None
                if cover_data.get("target_position") is not None:
                    _LOGGER.debug("[%s] No command: status %s", entity_id, status.value)
                continue

            target = cover_data.get("target_position")
            if target is None:
                self._hysteresis_info[entity_id] = None
                continue

            cover_raw = self.storage.get_cover_raw(entity_id)
            if cover_raw is None:
                continue

            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown"):
                continue

            # Skip covers that are physically moving. HmIP-style actuators keep
            # reporting the pre-move position until travel finishes; for a long
            # move whose travel time exceeds SETTLE_TIME, the override check
            # below would misread that stale position as a manual override and
            # falsely PAUSE the cover. _pending_settle is left intact so the
            # post-settle sync runs once the cover reports its final position.
            if state.state in ("opening", "closing"):
                continue

            current = self._raw_position(state)
            if current is None:
                continue

            # Enforce vent minimum position (logical, before inversion)
            original_target = target
            if status == CoverStatus.VENTING:
                vent_min = self._cover_val(cover_raw, "vent_position")
                if target < vent_min:
                    target = vent_min
                    _LOGGER.debug("[%s] VENTING: clamped %d%% -> %d%% (vent min)", entity_id, original_target, target)

            # Handle inverted covers (100% = closed)
            if cover_raw.get("inverted", False):
                target = 100 - target
            # Open/close-only covers reach 0 or 100 only: compare with that,
            # otherwise an intermediate target is re-commanded every cycle.
            target = self._effective_position(entity_id, target)

            # Our own target changed (rule / scenario / rule disabled / rule
            # edited) while the cover is still travelling to the position this
            # cycle commanded before. The stale position it reports is not a
            # manual override: send the new target right away instead of
            # waiting for the settle time and misreading the travel.
            expected_before = self._last_positions.get(entity_id)
            own_target_change = (
                entity_id in self._pending_settle
                and expected_before is not None
                and self._last_sent_target.get(entity_id) == expected_before
                and target != expected_before
            )
            if own_target_change:
                _LOGGER.info(
                    "[%s] Target changed during travel (%d%% -> %d%%), re-commanding",
                    entity_id, expected_before, target,
                )
                self._pending_settle.discard(entity_id)

            # Skip covers still settling after our commands (vent/lock moves, rule commands)
            last_cmd_t = self._last_command_time.get(entity_id, 0)
            if entity_id in self._pending_settle:
                if (common.time_mod.monotonic() - last_cmd_t) < self._settle_time(entity_id):
                    continue
                # Settle time passed: check if position deviated significantly (manual override)
                self._pending_settle.discard(entity_id)
                expected_target = self._last_positions.get(entity_id)
                settle_threshold = self._cover_val(cover_raw, "min_position_change")
                if expected_target is not None and abs(current - expected_target) > settle_threshold:
                    _LOGGER.debug(
                        "[%s] Post-settle: large deviation %d%% vs expected %d%%",
                        entity_id, current, expected_target,
                    )
                    # Not moved at all: lost command, resent (not a manual move)
                    if self._resend_if_lost(entity_id, current):
                        continue
                    # Don't sync -- let override check below detect the manual move
                else:
                    self._last_positions[entity_id] = current
                    self._sync_tilt_from_state(entity_id, state)
                    _LOGGER.debug("[%s] Post-settle sync: position %d%%", entity_id, current)

            # Detect manual override missed by state-change handler (e.g. during settle time)
            expected = self._last_positions.get(entity_id)
            if (
                not own_target_change
                and not safety
                and expected is not None
                and abs(current - expected) > MANUAL_OVERRIDE_TOLERANCE
                and (common.time_mod.monotonic() - self._last_command_time.get(entity_id, 0))
                >= self._settle_time(entity_id)
                and entity_id not in self._pending_settle
                and status in (CoverStatus.AUTO, CoverStatus.VENTING)
            ):
                cover = self.storage.covers.get(entity_id)
                if cover and cover.auto_enabled:
                    _LOGGER.info(
                        "[%s] Manual override detected in apply cycle (expected %d, got %d)",
                        entity_id, expected, current,
                    )
                    self.pause_cover(cover)
                    continue

            # Window state unknown (lock sensor unavailable, e.g. after a
            # restart): never lower the cover below its lock position.
            if self._blocked_by_unknown_lock(entity_id, cover_raw, target, current):
                self._hysteresis_info[entity_id] = None
                continue

            # Check hysteresis: minimum position change
            # Fully open/closed targets are honoured once even below
            # min_change: otherwise a cover resting a few percent short of an
            # end stop (e.g. 3% vs 0%) would never reach it. Once that end
            # stop has been commanded, normal hysteresis applies again so a
            # motor that settles at 1% is not re-commanded forever.
            min_change = self._cover_val(cover_raw, "min_position_change")
            position_diff = abs(current - target)
            endpoint_pending = (
                target in (0, 100)
                and self._last_sent_target.get(entity_id) != target
            )
            # A safety rule's new target is sent once regardless of min_change
            safety_pending = safety and self._last_sent_target.get(entity_id) != target
            if 0 < position_diff < min_change and not endpoint_pending and not safety_pending:
                _LOGGER.debug(
                    "Skipping %s: position change %d < min %d",
                    entity_id, position_diff, min_change
                )
                self._hysteresis_info[entity_id] = "position"
                self._last_positions[entity_id] = current
                self._sync_tilt_from_state(entity_id, state)
                # The position is close enough, but a tilt-only change of the
                # rule must still reach the slats.
                self._apply_rule_tilt(entity_id, cover_raw, cover_data, position_changed=False)
                continue

            # Check hysteresis: minimum time between changes.
            # Skipped on rule change (semantic state change like Day -> Night)
            # OR when the cover just exited a protective status (LOCKED /
            # VENTING) -- otherwise a long min_time_between_changes leaves
            # the cover at vent/lock position long after the sensor cleared.
            min_time = self._cover_val(cover_raw, "min_time_between_changes")
            last_change = cover_raw.get("last_position_change")
            current_rule = cover_data.get("matching_rule_id")
            rule_changed = (
                entity_id in self._last_move_rule
                and current_rule != self._last_move_rule[entity_id]
            )
            status_just_reset = entity_id in self._post_protective_exit
            if (
                position_diff > 0
                and last_change
                and (now - last_change) < min_time
                and not rule_changed
                and not status_just_reset
                and not own_target_change
                and not safety
            ):
                _LOGGER.debug(
                    "Skipping %s: only %ds since last change (min %ds)",
                    entity_id, int(now - last_change), min_time
                )
                self._hysteresis_info[entity_id] = "time"
                self._last_positions[entity_id] = current
                self._sync_tilt_from_state(entity_id, state)
                self._apply_rule_tilt(entity_id, cover_raw, cover_data, position_changed=False)
                continue
            # Past the time-hysteresis check: consume the one-shot bypass.
            self._post_protective_exit.discard(entity_id)

            position_changed = current != target
            if position_changed:
                if command_sent and stagger > 0:
                    await asyncio.sleep(stagger)
                    # The status may have changed during the stagger (manual
                    # pause, window opened, wind): don't send a stale command.
                    if (
                        (not safety and (self._wind_protected or not self.storage.enabled))
                        or self._cover_states.get(entity_id, CoverStatus.AUTO) != status
                    ):
                        _LOGGER.debug(
                            "[%s] Status changed during stagger, skipping command", entity_id
                        )
                        continue
                _LOGGER.info("[%s] Moving %d%% -> %d%%", entity_id, current, target)
                self._hysteresis_info[entity_id] = None
                self._last_positions[entity_id] = target
                self._last_sent_target[entity_id] = target
                self._last_command_time[entity_id] = common.time_mod.monotonic()
                self._move_start[entity_id] = (common.time_mod.monotonic(), current, target)
                self._runtime_set("_moved_since_command").discard(entity_id)
                self._last_move_rule[entity_id] = cover_data.get("matching_rule_id")
                self._pending_settle.add(entity_id)
                # A new command: lost-command resends start from zero
                if self._lost_command_retries:
                    self._lost_command_retries.pop(entity_id, None)
                self._log(
                    LOG_EVENT_POSITION, entity_id, f"{current}% -> {target}%",
                    {"key": "position", "from": current, "to": target,
                     "rule_id": cover_data.get("matching_rule_id")},
                )
                rule_id = cover_data.get("matching_rule_id")
                rule_obj = self.storage.rules.get(rule_id) if rule_id else None
                if rule_obj:
                    logbook_msg = i18n.text(
                        self.hass, "moved_rule",
                        from_pos=current, to_pos=target, rule=rule_obj.name,
                    )
                else:
                    logbook_msg = i18n.text(
                        self.hass, "moved", from_pos=current, to_pos=target
                    )
                self._logbook(
                    logbook_msg,
                    entity_id,
                )
                await self._async_send_position(entity_id, target)
                self.storage.update_cover_last_change(entity_id, now)
                command_sent = True
            else:
                self._hysteresis_info[entity_id] = None
                self._last_positions[entity_id] = current
                self._sync_tilt_from_state(entity_id, state)

            self._apply_rule_tilt(entity_id, cover_raw, cover_data, position_changed)

    def _apply_rule_tilt(
        self,
        entity_id: str,
        cover_raw: dict[str, Any],
        cover_data: dict[str, Any],
        position_changed: bool,
    ) -> None:
        """Send the rule's tilt when it differs (after a move with a delay)."""
        target_tilt = cover_data.get("target_tilt_position")
        if target_tilt is None:
            return
        if not (cover_raw.get("supports_tilt", False) and self._supports_tilt(entity_id)):
            return
        actual_tilt = 100 - target_tilt if cover_raw.get("inverted_tilt", False) else target_tilt
        last_tilt = self._last_tilt_positions.get(entity_id)
        # Always re-send after a position move: most venetian blind
        # actuators reset the slat angle while travelling, so an
        # unchanged target tilt would otherwise be lost.
        if (
            position_changed
            or last_tilt is None
            or abs(actual_tilt - last_tilt) > MANUAL_OVERRIDE_TOLERANCE
        ):
            self._last_tilt_positions[entity_id] = actual_tilt
            tilt_delay = TILT_COMMAND_DELAY if position_changed else 0
            if not position_changed:
                self._last_command_time[entity_id] = common.time_mod.monotonic()
            self._schedule_tilt(entity_id, actual_tilt, tilt_delay)

    def _supports_tilt(self, entity_id: str) -> bool:
        """Check if a cover entity supports tilt via HA features."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return False
        features = state.attributes.get("supported_features", 0)
        return bool(features & TILT_FEATURE_FLAG)

    def _schedule_tilt(
        self, entity_id: str, tilt: int, delay: float
    ) -> None:
        """Schedule a tilt command, cancelling any pending one for the same cover."""
        old_task = self._tilt_tasks.get(entity_id)
        if old_task and not old_task.done():
            old_task.cancel()
        self._tilt_tasks[entity_id] = self.hass.async_create_task(
            self._send_tilt_delayed(entity_id, tilt, delay)
        )

    async def _send_tilt_delayed(
        self, entity_id: str, tilt: int, delay: float
    ) -> None:
        """Send tilt command after optional delay."""
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_command_time[entity_id] = common.time_mod.monotonic()
            await self.hass.services.async_call(
                "cover",
                "set_cover_tilt_position",
                {"entity_id": entity_id, "tilt_position": tilt},
                blocking=False,
            )
        except Exception as err:
            _LOGGER.exception("Failed to send tilt to %s: %s", entity_id, err)
        finally:
            # Clean up task reference (guard against cancelled task clearing new ref)
            if self._tilt_tasks.get(entity_id) is asyncio.current_task():
                del self._tilt_tasks[entity_id]

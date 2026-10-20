"""Window sensors: lock, venting, unknown or missing sensors.

Mixin of CoverAutomaticCoordinator: it uses the coordinator's attributes."""
from __future__ import annotations

import logging
from typing import Any

from . import coordinator_common as common
from . import i18n
from .const import (
    BINARY_SENSOR_ON_STATES,
    LOG_EVENT_STATUS,
    TILT_COMMAND_DELAY,
)
from .coordinator_common import (
    _UNUSABLE_STATES,
)
from .models import CoverStatus

# Same logger as the coordinator: the split does not change the log names
_LOGGER = logging.getLogger(__package__ + ".coordinator")


class ContactsMixin:
    """Window sensors: lock, venting, unknown or missing sensors."""

    def _lock_open_window(self, entity_id: str, cover_raw: dict[str, Any]) -> None:
        """Lock a cover whose window is open (lock position, or held in place)."""
        if self._cover_states.get(entity_id) == CoverStatus.LOCKED:
            return
        lock_pos = self._cover_val(cover_raw, "lock_position")
        current = self._get_current_position(entity_id)
        if self._lock_moves(cover_raw, current, lock_pos):
            lock_tilt = self._cover_val(cover_raw, "lock_tilt_position")
            self._lock_cover(entity_id, lock_pos, lock_tilt=lock_tilt)
        else:
            if entity_id not in self._pre_lock_states:
                prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
                self._pre_lock_states[entity_id] = CoverStatus.AUTO if prev == CoverStatus.PAUSED else prev
            self._lock_in_place(entity_id, cover_raw)

    def _keeps_lock_sensor_unknown(self, entity_id: str, cover_raw: dict[str, Any]) -> bool:
        """Whether a LOCKED cover must stay locked: its window state is unknown.

        Never close a cover on a possibly open window: an unavailable lock
        sensor is not "closed".
        """
        return (
            self._cover_states.get(entity_id) == CoverStatus.LOCKED
            and self._is_sensor_unknown(cover_raw, "lock_sensor")
        )

    def _is_sensor_open(self, cover_raw: dict[str, Any], key: str) -> bool:
        """Check if a binary sensor (lock/vent) for a cover is open."""
        sensor = cover_raw.get(key)
        if not sensor:
            return False
        sensor_state = self.hass.states.get(sensor)
        if sensor_state is None:
            return False
        return sensor_state.state in BINARY_SENSOR_ON_STATES

    def _is_sensor_unknown(self, cover_raw: dict[str, Any], key: str) -> bool:
        """Check if a configured lock/vent sensor has no usable state.

        "unavailable" / "unknown" always count as unknown (possibly open
        window). A sensor entity that does not exist at all (state None) is
        only unknown during the startup grace period, while integrations are
        still loading: afterwards it was renamed or removed and would block
        the cover forever (restored LOCKED never released, moves down never
        sent), so it is treated like no sensor configured.
        """
        sensor = cover_raw.get(key)
        if not sensor:
            return False
        sensor_state = self.hass.states.get(sensor)
        if sensor_state is None:
            return self._in_startup_grace()
        return sensor_state.state in _UNUSABLE_STATES

    def _track_missing_lock_sensor(self, entity_id: str, cover_raw: dict[str, Any]) -> None:
        """Log once per cover that its lock sensor entity no longer exists.

        Such a sensor is ignored after the grace period (_is_sensor_unknown):
        the activity log tells the user why the window lock no longer acts.
        Logged again only after the sensor came back and disappeared again.
        """
        missing = self._runtime_set("_lock_sensor_missing")
        sensor = cover_raw.get("lock_sensor")
        if (
            not sensor
            or self.hass.states.get(sensor) is not None
            or self._in_startup_grace()
        ):
            missing.discard(entity_id)
            return
        if entity_id in missing:
            return
        missing.add(entity_id)
        _LOGGER.warning(
            "[%s] Lock sensor %s does not exist: window lock ignored", entity_id, sensor
        )
        self._log(LOG_EVENT_STATUS, entity_id, f"Lock sensor {sensor} missing, ignored",
                  {"key": "lock_sensor_missing", "sensor": sensor})

    @staticmethod
    def _is_real_transition(old_state: Any, new_state: Any) -> bool:
        """Whether a sensor event is a real change between two usable states."""
        return (
            old_state is not None
            and old_state.state not in _UNUSABLE_STATES
            and old_state.state != new_state.state
        )

    def _handle_contact_sensor_change(  # noqa: C901 -- complexity 28, to reduce (see CHANGELOG 2.1.3)
        self,
        sensor_id: str,
        lock_covers: list[str],
        vent_covers: list[str],
        old_state: Any,
        new_state: Any,
    ) -> None:
        """Handle contact sensor state changes (lock or vent)."""
        if new_state is None:
            return

        if new_state.state in ("unavailable", "unknown"):
            _LOGGER.warning("[%s] Sensor unavailable, ignoring state change", sensor_id)
            return

        is_open = new_state.state in BINARY_SENSOR_ON_STATES

        # Cache sensor states to avoid repeated hass.states.get() calls
        sensor_state_cache: dict[str, bool] = {}

        def is_sensor_open_cached(cover_raw: dict[str, Any], key: str) -> bool:
            sensor = cover_raw.get(key)
            if not sensor:
                return False
            if sensor not in sensor_state_cache:
                state = self.hass.states.get(sensor)
                sensor_state_cache[sensor] = (
                    state is not None and state.state in BINARY_SENSOR_ON_STATES
                )
            return sensor_state_cache[sensor]

        # Handle lock sensor covers (window open -> fully open)
        # Lock sensor always has priority - override even if already locked by vent
        for cover_id in lock_covers:
            cover_raw = self.storage.get_cover_raw(cover_id)
            if cover_raw is None:
                continue

            if is_open:
                lock_pos = self._cover_val(cover_raw, "lock_position")
                current = self._get_current_position(cover_id)
                if self._lock_moves(cover_raw, current, lock_pos):
                    self._lock_cover(cover_id, lock_pos, lock_tilt=self._cover_val(cover_raw, "lock_tilt_position"))
                else:
                    if cover_id not in self._pre_lock_states:
                        prev = self._cover_states.get(cover_id, CoverStatus.AUTO)
                        self._pre_lock_states[cover_id] = CoverStatus.AUTO if prev == CoverStatus.PAUSED else prev
                    self._lock_in_place(cover_id, cover_raw)
                    if self.data is not None:
                        self.async_set_updated_data(self.data)
            elif self._cover_states.get(cover_id) == CoverStatus.LOCKED and self._wind_protected:
                # Window closed during a storm: back to the wind protection
                # (this cover only).
                self._protect_one_from_wind(cover_id, cover_raw)
                if self.data is not None:
                    self.async_set_updated_data(self.data)
            elif self._cover_states.get(cover_id) == CoverStatus.LOCKED:
                # Only unlock if vent sensor is also not open
                if not is_sensor_open_cached(cover_raw, "vent_sensor"):
                    _LOGGER.debug("[%s] Lock sensor %s closed -> unlocking", cover_id, sensor_id)
                    self._unlock_cover(cover_id)
                else:
                    # Move to vent position if currently below it
                    self._pre_lock_states.pop(cover_id, None)
                    self._enter_venting(
                        cover_id, cover_raw, f"window {sensor_id} closed, vent still open"
                    )
                    if self.data is not None:
                        self.async_set_updated_data(self.data)

        # A vent sensor coming back from unavailable/unknown (or an event
        # without a state change, e.g. an attribute update) is no real
        # transition: acting on it would e.g. cancel a manual pause. The
        # periodic sync reconciles the status from the current sensor state.
        if not self._is_real_transition(old_state, new_state):
            if vent_covers:
                _LOGGER.debug(
                    "[%s] Vent sensor event without transition (%s -> %s), left to sync",
                    sensor_id, getattr(old_state, "state", None), new_state.state,
                )
            vent_covers = []

        # Handle vent sensor covers (vent open -> min position, automation continues)
        for cover_id in vent_covers:
            cover_raw = self.storage.get_cover_raw(cover_id)
            if cover_raw is None:
                continue

            # Skip if lock sensor is open (lock has priority)
            if is_sensor_open_cached(cover_raw, "lock_sensor"):
                continue
            # A tilted window does not override the wind protection
            if self._wind_protected:
                continue

            current_status = self._cover_states.get(cover_id, CoverStatus.AUTO)

            if is_open and current_status == CoverStatus.PAUSED:
                # A (manual) pause is kept, like the periodic sync does: a
                # window tilted for a few seconds must not cancel it. Only
                # the airflow is ensured (raised to the vent position when
                # below); the pause timer is unchanged.
                _LOGGER.debug(
                    "[%s] Vent sensor %s open while paused: pause kept", cover_id, sensor_id,
                )
                self._raise_to_vent_floor(cover_id, cover_raw)
            elif is_open and current_status not in (CoverStatus.LOCKED, CoverStatus.VENTING):
                # Move up to vent_position if currently below it
                self._enter_venting(cover_id, cover_raw, f"vent sensor {sensor_id} open")
                if self.data is not None:
                    self.async_set_updated_data(self.data)
            elif not is_open and current_status == CoverStatus.VENTING:
                # A PAUSED cover stays PAUSED (pause timer unchanged): the
                # vent sensor closing is no reason to end a manual pause.
                # Mirror the _sync_cover_statuses branch: a cover with automation
                # disabled returns to MANUAL, not AUTO, so the refresh triggered
                # below does not run an AUTO apply cycle (which could move a
                # disabled cover) before the next sync would correct the status.
                target = (
                    CoverStatus.AUTO
                    if cover_raw.get("auto_enabled", True)
                    else CoverStatus.MANUAL
                )
                _LOGGER.info(
                    "[%s] Vent sensor %s closed: %s -> %s",
                    cover_id, sensor_id, current_status.value, target.value,
                )
                self._log(LOG_EVENT_STATUS, cover_id, f"{current_status.value} -> {target.value}",
                          {"key": "status_change", "from": current_status.value,
                           "to": target.value, "sensor": sensor_id})
                self._cover_states[cover_id] = target
                self.storage.update_cover_status(cover_id, target.value, None)
                self._sync_expected_after_protective_exit(cover_id)
                # Mark for one-shot time-hysteresis bypass so the next apply
                # cycle re-applies the matching rule even when
                # min_time_between_changes has not elapsed.
                self._post_protective_exit.add(cover_id)
                if self.data is not None:
                    self.async_set_updated_data(self.data)
                self._schedule_refresh()

        # Pre-lock statuses may have changed (lock/unlock): persist them now
        # rather than at the next sync cycle.
        self._persist_runtime_state()

    @staticmethod
    def _lock_moves(cover_raw: dict[str, Any], current: int | None, lock_pos: int) -> bool:
        """Whether locking moves the cover to its lock position.

        With lock_hold_position the cover stays where it is (no position or
        tilt command); otherwise it only moves up to lock_pos, never down.
        """
        if cover_raw.get("lock_hold_position"):
            return False
        return current is None or current < lock_pos

    def _lock_in_place(
        self, entity_id: str, cover_raw: dict[str, Any], *, sensor_unknown: bool = False
    ) -> None:
        """Set a cover LOCKED without moving it (hold option or already above).

        With sensor_unknown the window state is unknown (sensor unavailable)
        rather than open: the cover is held as a precaution. The caller
        records the pre-lock state.
        """
        prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
        self._cover_states[entity_id] = CoverStatus.LOCKED
        self.storage.update_cover_status(entity_id, CoverStatus.LOCKED.value, None)
        self._update_last_position_from_state(entity_id)
        if prev == CoverStatus.LOCKED:
            return
        current = self._get_current_position(entity_id)
        sensor = cover_raw.get("lock_sensor")
        _LOGGER.info(
            "[%s] Window %s %s: %s -> locked (kept at %s%%)",
            entity_id, sensor, "state unknown" if sensor_unknown else "open", prev.value, current,
        )
        self._log(LOG_EVENT_STATUS, entity_id, f"{prev.value} -> locked (kept at {current}%)",
                  {"key": "status_change", "from": prev.value, "to": "locked",
                   "sensor": sensor, "position": current, "kept": True})

    def _raise_to_vent_floor(self, entity_id: str, cover_raw: dict[str, Any]) -> bool:
        """Raise a cover below its vent position to it (with the vent tilt).

        Returns True when a command was sent; otherwise the expected
        position is synced to where the cover is. Does not change the status:
        shared by _enter_venting and by a paused cover whose vent opens (the
        pause is kept, only the airflow is ensured).
        """
        vent_pos = self._cover_val(cover_raw, "vent_position")
        current = self._get_current_position(entity_id)
        if current is None or current >= vent_pos:
            self._update_last_position_from_state(entity_id)
            return False
        inverted = cover_raw.get("inverted", False)
        actual = (100 - vent_pos) if inverted else vent_pos
        self._last_positions[entity_id] = self._effective_position(entity_id, actual)
        self._last_command_time[entity_id] = common.time_mod.monotonic()
        self._pending_settle.add(entity_id)
        self.hass.async_create_task(self._position_call(entity_id, actual))
        vent_tilt = self._cover_val(cover_raw, "vent_tilt_position")
        if (
            isinstance(vent_tilt, int)
            and not isinstance(vent_tilt, bool)
            and cover_raw.get("supports_tilt", False)
        ):
            actual_tilt = 100 - vent_tilt if cover_raw.get("inverted_tilt", False) else vent_tilt
            self._last_tilt_positions[entity_id] = actual_tilt
            self._schedule_tilt(entity_id, actual_tilt, TILT_COMMAND_DELAY)
        return True

    def _enter_venting(self, entity_id: str, cover_raw: dict[str, Any], reason: str) -> None:
        """Set a cover VENTING, raising it to the vent position when below.

        When the cover is raised, the vent tilt (slats) is sent after the
        move like the lock tilt, so the configured airflow angle is applied.
        """
        prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
        vent_pos = self._cover_val(cover_raw, "vent_position")
        current = self._get_current_position(entity_id)
        if self._raise_to_vent_floor(entity_id, cover_raw):
            detail = f"moving {current}% -> {vent_pos}%"
        else:
            detail = f"kept at {current}%, min {vent_pos}%"
        self._cover_states[entity_id] = CoverStatus.VENTING
        self.storage.update_cover_status(entity_id, CoverStatus.VENTING.value, None)
        if prev == CoverStatus.VENTING:
            return
        _LOGGER.info("[%s] %s: %s -> venting (%s)", entity_id, reason, prev.value, detail)
        self._log(LOG_EVENT_STATUS, entity_id, f"{prev.value} -> venting ({detail})",
                  {"key": "status_change", "from": prev.value, "to": "venting",
                   "sensor": cover_raw.get("vent_sensor"), "position": vent_pos})

    def _lock_cover(
        self, entity_id: str, lock_position: int, *, lock_tilt: int | None = None
    ) -> None:
        """Lock a cover due to open contact sensor."""
        # Save previous state for restoration after unlock
        # If paused, save as AUTO (pause cancelled by lock priority)
        if entity_id not in self._pre_lock_states:
            prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
            self._pre_lock_states[entity_id] = CoverStatus.AUTO if prev == CoverStatus.PAUSED else prev
        prev_status = self._cover_states.get(entity_id, CoverStatus.AUTO)
        self._cover_states[entity_id] = CoverStatus.LOCKED
        prev_val = self._pre_lock_states.get(entity_id, CoverStatus.AUTO).value
        cover_raw = self.storage.get_cover_raw(entity_id)
        sensor = cover_raw.get("lock_sensor") if cover_raw else None
        _LOGGER.info(
            "[%s] Window %s open: %s -> locked, moving to %s%%",
            entity_id, sensor, prev_status.value, lock_position,
        )
        self._log(LOG_EVENT_STATUS, entity_id, f"{prev_val} -> locked",
                  {"key": "status_change", "from": prev_val, "to": "locked",
                   "sensor": sensor, "position": lock_position})
        self._logbook(i18n.text(self.hass, "locked", position=lock_position), entity_id)
        self.storage.update_cover_status(entity_id, CoverStatus.LOCKED.value, None)

        # Handle inverted covers
        actual_position = lock_position
        if cover_raw and cover_raw.get("inverted", False):
            actual_position = 100 - lock_position

        _LOGGER.debug("Locking cover %s at position %s (actual: %s)", entity_id, lock_position, actual_position)

        # Update expected position to prevent false manual override
        self._last_positions[entity_id] = self._effective_position(entity_id, actual_position)

        self._last_command_time[entity_id] = common.time_mod.monotonic()
        self.hass.async_create_task(self._position_call(entity_id, actual_position))

        # Send tilt command if supported and configured
        if lock_tilt is not None and cover_raw and cover_raw.get("supports_tilt", False):
            actual_tilt = lock_tilt
            if cover_raw.get("inverted_tilt", False):
                actual_tilt = 100 - lock_tilt
            self._last_tilt_positions[entity_id] = actual_tilt
            self._schedule_tilt(entity_id, actual_tilt, TILT_COMMAND_DELAY)

        if self.data is not None:
            self.async_set_updated_data(self.data)

    def _unlock_cover(self, entity_id: str) -> None:
        """Unlock a cover when its contact sensors are closed (or removed).

        Only acts on covers that are actually LOCKED or VENTING. A missing
        pre-lock state (e.g. VENTING entered directly, or a sensor removed
        from the cover config) falls back to AUTO instead of leaving the
        cover stuck in its protective status forever.
        """
        current = self._cover_states.get(entity_id)
        if current not in (CoverStatus.LOCKED, CoverStatus.VENTING):
            self._pre_lock_states.pop(entity_id, None)
            return

        self._log(LOG_EVENT_STATUS, entity_id, f"{current.value} -> unlocked",
                  {"key": "status_change", "from": current.value, "to": "unlocked"})
        self._logbook(i18n.text(self.hass, "unlocked"), entity_id)

        cover_raw = self.storage.get_cover_raw(entity_id)
        previous = self._pre_lock_states.pop(entity_id, CoverStatus.AUTO)
        # Restore PAUSED (pause not expired), MANUAL, or VENTING (vent
        # sensor still open); everything else returns to AUTO.
        target = CoverStatus.AUTO
        pause_until = None
        if previous == CoverStatus.PAUSED:
            pause_until = cover_raw.get("pause_until") if cover_raw else None
            if pause_until and common.dt_util.now().timestamp() < pause_until:
                target = CoverStatus.PAUSED
        elif previous == CoverStatus.MANUAL:
            target = CoverStatus.MANUAL
        elif previous == CoverStatus.VENTING:
            if cover_raw and self._is_sensor_open(cover_raw, "vent_sensor"):
                target = CoverStatus.VENTING
        # The automation may have been switched on/off during the lock
        target = self._status_for_automation(target, cover_raw)

        sensors = ", ".join(
            s for s in ((cover_raw or {}).get("lock_sensor"), (cover_raw or {}).get("vent_sensor")) if s
        ) or "-"
        _LOGGER.info(
            "[%s] Window %s closed: %s -> %s (kept at %s%%)",
            entity_id, sensors, current.value, target.value,
            self._get_current_position(entity_id),
        )

        self._cover_states[entity_id] = target
        self.storage.update_cover_status(
            entity_id, target.value, pause_until if target == CoverStatus.PAUSED else None
        )
        # Expected position: where the cover is (or is still going), so
        # neither a finished lock move nor the stop is taken as manual
        self._sync_expected_after_protective_exit(entity_id)
        if target != CoverStatus.AUTO:
            if self.data is not None:
                self.async_set_updated_data(self.data)
            return
        # One-shot time-hysteresis bypass for the next apply cycle.
        self._post_protective_exit.add(entity_id)
        self._schedule_refresh()

    def _sync_expected_after_protective_exit(self, entity_id: str) -> None:
        """Expected position when a cover leaves LOCKED / VENTING / wind protection.

        Normally the current position (the cover stays where the protection
        left it). But when the window closes while the cover is still
        travelling to its lock / vent / wind position, the current reading is
        a mid-travel value (e.g. 34 % on the way to 100 %): taking it as the
        expected position made the end of our own move look like a manual
        command a few seconds later, and the cover was paused. While our
        command is still settling, the commanded position is kept instead;
        the post-settle check then syncs to where the cover really stopped.
        """
        last_cmd = self._last_command_time.get(entity_id, 0)
        if (
            entity_id in self._pending_settle
            and self._last_positions.get(entity_id) is not None
            and (common.time_mod.monotonic() - last_cmd) < self._settle_time(entity_id)
        ):
            _LOGGER.debug(
                "[%s] Protection ended during our move: expected position kept at %s%%",
                entity_id, self._last_positions.get(entity_id),
            )
            return
        self._update_last_position_from_state(entity_id)

    def _blocked_by_unknown_lock(
        self, entity_id: str, cover_raw: dict[str, Any], raw_target: int, raw_current: int
    ) -> bool:
        """Whether a move must wait: it closes a cover on a possibly open window.

        While the lock sensor (window contact) is unavailable/unknown the
        window may be open: a cover is never driven down below its
        lock_position then. Upward moves stay allowed. Positions are raw
        (HA scale); inverted covers are mirrored here.
        """
        blocked_logged = self._runtime_set("_move_blocked_logged")
        if not self._is_sensor_unknown(cover_raw, "lock_sensor"):
            blocked_logged.discard(entity_id)
            return False
        if cover_raw.get("inverted", False):
            target, current = 100 - raw_target, 100 - raw_current
        else:
            target, current = raw_target, raw_current
        lock_pos = self._cover_val(cover_raw, "lock_position")
        if not isinstance(lock_pos, (int, float)) or isinstance(lock_pos, bool):
            lock_pos = 100
        if target < current and target < lock_pos:
            _LOGGER.debug(
                "[%s] Window state unknown: not lowering %d%% -> %d%% (lock position %d%%)",
                entity_id, current, target, lock_pos,
            )
            # Once per blocking episode: the apply cycle re-checks every scan
            if entity_id not in blocked_logged:
                blocked_logged.add(entity_id)
                sensor = cover_raw.get("lock_sensor")
                self._log(LOG_EVENT_STATUS, entity_id,
                          f"Move to {target}% blocked: window {sensor} state unknown",
                          {"key": "move_blocked_window_unknown", "sensor": sensor,
                           "position": target})
            return True
        blocked_logged.discard(entity_id)
        return False

    def _keep_status_sensor_unknown(self, entity_id: str, cover_raw: dict[str, Any]) -> None:
        """Keep LOCKED/VENTING while a lock/vent sensor is unavailable (log once)."""
        status = self._cover_states.get(entity_id, CoverStatus.AUTO)
        if entity_id in self._sensor_unknown_kept:
            _LOGGER.debug("[%s] Lock/vent sensor unavailable, keeping %s", entity_id, status.value)
            return
        self._sensor_unknown_kept.add(entity_id)
        sensors = ", ".join(
            s for s in (cover_raw.get("lock_sensor"), cover_raw.get("vent_sensor")) if s
        )
        current = self._get_current_position(entity_id)
        _LOGGER.debug(
            "[%s] Sensor %s unavailable: keeping %s (kept at %s%%)",
            entity_id, sensors, status.value, current,
        )
        self._log(LOG_EVENT_STATUS, entity_id, f"{status.value} kept (sensor unavailable)",
                  {"key": "sensor_unavailable", "status": status.value,
                   "sensor": sensors, "position": current})

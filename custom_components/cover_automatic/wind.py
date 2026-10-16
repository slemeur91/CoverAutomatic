"""Wind protection: activation, staggered commands, end of the protection.

Mixin of CoverAutomaticCoordinator: it uses the coordinator's attributes."""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from homeassistant.core import callback

from . import coordinator_common as common
from . import i18n
from .const import (
    LOG_EVENT_STATUS,
    LOG_EVENT_WIND,
)
from .models import CoverStatus

# Same logger as the coordinator: the split does not change the log names
_LOGGER = logging.getLogger(__package__ + ".coordinator")


class WindMixin:
    """Wind protection: activation, staggered commands, end of the protection."""

    def _set_wind_protected(self, active: bool) -> None:
        """Change the global wind protection state and persist it.

        Any real change ends the pending confirmation of a wind state
        restored at startup (the sensor has spoken, or settings changed).
        """
        self._wind_protected = active
        self._wind_restore_pending = False
        self._persist_runtime_state()

    def _get_wind_speed(self) -> float | None:
        """Get current wind speed from sensor."""
        sensor_id = self.storage.wind_sensor
        if not sensor_id:
            return None
        state = self.hass.states.get(sensor_id)
        if state is None:
            return None
        try:
            speed = float(state.state)
        except (ValueError, TypeError):
            return None
        if not math.isfinite(speed):  # NaN or inf is no valid reading
            return None
        self._wind_value_seen = True
        return speed

    def _check_wind_protection(self) -> None:
        """Check wind sensor and update global wind protection state.

        Uses hysteresis: activates at threshold, deactivates at
        threshold - hysteresis to prevent oscillation in gusty wind.
        """
        threshold = self.storage.wind_speed_threshold
        hysteresis = self.storage.wind_speed_hysteresis

        # Feature switched off (sensor removed or threshold set to 0) while
        # protection is active: release it, otherwise covers stay blocked.
        if self._wind_protected and (not self.storage.wind_sensor or threshold <= 0):
            _LOGGER.info("Wind protection DEACTIVATED (wind protection disabled in settings)")
            self._set_wind_protected(False)
            self._log(LOG_EVENT_WIND, None, "Deactivated (disabled in settings)",
                      {"key": "wind_disabled"})
            self._logbook(i18n.text(self.hass, "wind_disabled"))
            self._deactivate_wind_protection()
            return

        wind_speed = self._get_wind_speed()
        if self._drop_unconfirmed_wind_restore():
            return
        if wind_speed is None:
            if self._wind_protected and not self._wind_sensor_warned:
                self._wind_sensor_warned = True
                _LOGGER.warning("Wind sensor unavailable while WIND_PROTECTED, keeping protection active")
            return
        self._wind_sensor_warned = False

        if hysteresis >= threshold > 0:
            # Invalid config (e.g. older storage/import): the release level
            # threshold - hysteresis would be <= 0 and never reached.
            _LOGGER.debug(
                "wind_speed_hysteresis (%.1f) >= threshold (%.1f), ignoring hysteresis",
                hysteresis, threshold,
            )
            hysteresis = 0.0

        if not self._wind_protected and wind_speed >= threshold > 0:
            wind_pos = self._wind_position()
            _LOGGER.info(
                "Wind protection ACTIVATED (%.1f >= %.1f), covers -> %d%%",
                wind_speed, threshold, wind_pos,
            )
            self._set_wind_protected(True)
            self._log(LOG_EVENT_WIND, None, f"Activated ({wind_speed:.1f} >= {threshold:.1f})",
                      {"key": "wind_activated", "speed": round(wind_speed, 1),
                       "threshold": round(threshold, 1), "position": wind_pos})
            self._logbook(i18n.text(
                self.hass, "wind_activated",
                speed=f"{wind_speed:.1f}", threshold=f"{threshold:.1f}",
            ))
            self._activate_wind_protection()
        elif self._wind_protected and wind_speed <= threshold - hysteresis:
            _LOGGER.info("Wind protection DEACTIVATED (%.1f <= %.1f)", wind_speed, threshold - hysteresis)
            self._set_wind_protected(False)
            release = threshold - hysteresis
            self._log(LOG_EVENT_WIND, None, f"Deactivated ({wind_speed:.1f} <= {release:.1f})",
                      {"key": "wind_deactivated", "speed": round(wind_speed, 1),
                       "threshold": round(release, 1)})
            self._logbook(i18n.text(
                self.hass, "wind_deactivated",
                speed=f"{wind_speed:.1f}", threshold=f"{release:.1f}",
            ))
            self._deactivate_wind_protection()

    def _drop_unconfirmed_wind_restore(self) -> bool:
        """Drop a wind protection restored at startup the sensor never confirmed.

        The restored state is kept during the startup grace period (wind
        sensors often report late). At its end, a wind sensor entity that
        does not exist (renamed / removed) or that never gave a valid value
        since startup cannot release the protection: the covers would stay
        blocked at the wind position forever. The protection is then ended
        normally (covers back to their previous status) and logged once.
        Returns True when it was dropped.
        """
        if not self._wind_restore_pending or self._in_startup_grace():
            return False
        self._wind_restore_pending = False
        if not self._wind_protected:
            return False
        sensor_id = self.storage.wind_sensor
        if self.hass.states.get(sensor_id) is not None and self._wind_value_seen:
            return False
        _LOGGER.warning(
            "Wind protection restored at startup dropped: wind sensor %s %s",
            sensor_id,
            "does not exist" if self.hass.states.get(sensor_id) is None else "never reported a value",
        )
        self._set_wind_protected(False)
        self._log(LOG_EVENT_WIND, None, f"Restored wind protection dropped (sensor {sensor_id})",
                  {"key": "wind_restore_dropped", "sensor": sensor_id})
        self._deactivate_wind_protection()
        return True

    def _wind_position(self) -> int:
        """Logical position covers move to while wind protection is active."""
        value = getattr(self.storage, "wind_position", 100)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 100
        return max(0, min(100, int(value)))

    def _protect_one_from_wind(self, entity_id: str, cover_raw: dict[str, Any]) -> None:
        """Wind protection for one cover while it is active.

        An open window (lock sensor) wins over the wind: the cover stays or
        gets locked (emergency exit). Otherwise the cover takes the wind
        status and position -- only this cover is commanded, not all.
        """
        if self._is_sensor_open(cover_raw, "lock_sensor"):
            self._lock_open_window(entity_id, cover_raw)
            return
        status = self._cover_states.get(entity_id)
        if status == CoverStatus.WIND_PROTECTED:
            return
        if self._keeps_lock_sensor_unknown(entity_id, cover_raw):
            return
        prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
        if entity_id not in self._pre_lock_states:
            self._pre_lock_states[entity_id] = CoverStatus.AUTO if prev == CoverStatus.PAUSED else prev
        self._cover_states[entity_id] = CoverStatus.WIND_PROTECTED
        self.storage.update_cover_status(entity_id, CoverStatus.WIND_PROTECTED.value, None)
        self._log(LOG_EVENT_STATUS, entity_id, f"{prev.value} -> wind_protected",
                  {"key": "status_change", "from": prev.value, "to": "wind_protected"})
        if entity_id not in self._safety_holds:
            self._send_wind_position(entity_id)

    def _activate_wind_protection(self) -> None:
        """Set all covers to WIND_PROTECTED and move them to the wind position.

        Covers whose window is open are locked instead: the lock (emergency
        exit) has priority over the wind. A LOCKED cover whose window state
        is unknown stays locked (same guard as _protect_one_from_wind).
        """
        # A previous activation may still be sending: never run two
        # staggered wind sequences in parallel.
        self._cancel_wind_tasks()
        wind_pos = self._wind_position()
        commands: list[tuple[str, int]] = []
        for entity_id in self.storage._data.get("covers", {}):
            cover_raw = self.storage.get_cover_raw(entity_id)
            if cover_raw is None:
                continue

            if self._is_sensor_open(cover_raw, "lock_sensor"):
                self._lock_open_window(entity_id, cover_raw)
                continue
            if self._keeps_lock_sensor_unknown(entity_id, cover_raw):
                _LOGGER.debug("[%s] Wind protection: kept LOCKED (window state unknown)", entity_id)
                continue

            prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
            if prev not in (CoverStatus.WIND_PROTECTED,):
                if entity_id not in self._pre_lock_states:
                    self._pre_lock_states[entity_id] = CoverStatus.AUTO if prev == CoverStatus.PAUSED else prev

            self._cover_states[entity_id] = CoverStatus.WIND_PROTECTED
            self.storage.update_cover_status(entity_id, CoverStatus.WIND_PROTECTED.value, None)

            if entity_id in self._safety_holds:
                # A safety rule drives this cover: it keeps the rule's position
                _LOGGER.debug("[%s] Wind protection: kept by safety rule", entity_id)
                continue

            # Move to the wind position (logical, inverted covers mirrored)
            inverted = cover_raw.get("inverted", False)
            actual_position = (100 - wind_pos) if inverted else wind_pos
            self._last_positions[entity_id] = actual_position
            self._last_command_time[entity_id] = common.time_mod.monotonic()
            commands.append((entity_id, actual_position))

        if commands:
            self._start_wind_commands(commands)

        self._persist_runtime_state()
        if self.data is not None:
            self.async_set_updated_data(self.data)

    def _send_wind_position(self, entity_id: str) -> None:
        """Move one wind protected cover to the wind position."""
        cover_raw = self.storage.get_cover_raw(entity_id)
        if cover_raw is None:
            return
        wind_pos = self._wind_position()
        actual = (100 - wind_pos) if cover_raw.get("inverted", False) else wind_pos
        self._last_positions[entity_id] = actual
        self._last_command_time[entity_id] = common.time_mod.monotonic()
        _LOGGER.debug("[%s] Wind protection re-applied -> %d%%", entity_id, wind_pos)
        self._start_wind_commands([(entity_id, actual)])

    def _wind_task_set(self) -> set[asyncio.Task[None]]:
        """Pending wind command tasks (created lazily)."""
        if self._wind_tasks is None:
            self._wind_tasks = set()
        return self._wind_tasks

    def _start_wind_commands(self, commands: list[tuple[str, int]]) -> None:
        """Send wind commands in a tracked task (cancellable on release)."""
        task = self.hass.async_create_task(self._send_staggered_commands(commands))
        if isinstance(task, asyncio.Task):
            tasks = self._wind_task_set()
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    def _cancel_wind_tasks(self) -> None:
        """Cancel pending (staggered) wind commands."""
        tasks = self._wind_task_set()
        for task in list(tasks):
            if not task.done():
                task.cancel()
        tasks.clear()

    async def _send_staggered_commands(
        self, commands: list[tuple[str, int]]
    ) -> None:
        """Send wind position commands with optional stagger delay between them.

        The wind may drop, a window may open (LOCKED) or a safety rule may
        take over during the stagger sleeps: each command is re-checked
        right before it is sent, and the settle window starts at the actual
        send time (a late command must not be read as a manual move).
        """
        stagger = self.storage.command_stagger
        for i, (entity_id, position) in enumerate(commands):
            if i > 0 and stagger > 0:
                await asyncio.sleep(stagger)
            if (
                not self._wind_protected
                or self._cover_states.get(entity_id) != CoverStatus.WIND_PROTECTED
                or entity_id in self._safety_holds
            ):
                _LOGGER.debug("[%s] Wind command dropped: status changed meanwhile", entity_id)
                continue
            self._last_positions[entity_id] = self._effective_position(entity_id, position)
            self._last_command_time[entity_id] = common.time_mod.monotonic()
            await self._async_send_position(entity_id, position)

    def _deactivate_wind_protection(self) -> None:
        """Remove WIND_PROTECTED status from all covers, re-derive from sensors.

        Evaluates lock/vent sensors inline so covers with open windows
        transition directly to LOCKED/VENTING instead of briefly landing in
        AUTO and waiting for the next scan tick. A cover whose window state
        is unknown is locked in place (possibly open window).
        """
        # Wind commands still waiting for their stagger slot are obsolete
        self._cancel_wind_tasks()
        for entity_id in list(self.storage._data.get("covers", {})):
            if self._cover_states.get(entity_id) != CoverStatus.WIND_PROTECTED:
                continue

            cover_raw = self.storage.get_cover_raw(entity_id)
            if cover_raw is None:
                continue

            pre_wind = self._pre_lock_states.pop(entity_id, None)

            if self._is_sensor_open(cover_raw, "lock_sensor"):
                lock_pos = self._cover_val(cover_raw, "lock_position")
                current = self._get_current_position(entity_id)
                if self._lock_moves(cover_raw, current, lock_pos):
                    lock_tilt = self._cover_val(cover_raw, "lock_tilt_position")
                    self._lock_cover(entity_id, lock_pos, lock_tilt=lock_tilt)
                else:
                    # Record a pre-lock state (the pre-wind one was just
                    # dropped) so the window-closed unlock restores AUTO.
                    self._pre_lock_states[entity_id] = CoverStatus.AUTO
                    self._lock_in_place(entity_id, cover_raw)
                continue

            if self._is_sensor_unknown(cover_raw, "lock_sensor"):
                # Window state unknown (sensor unavailable): treat it as
                # possibly open. Handing the cover back to AUTO would let the
                # next rule close it on an open window; it stays where it is
                # (LOCKED) until the sensor reports again.
                self._pre_lock_states[entity_id] = self._status_for_automation(
                    pre_wind if pre_wind in (CoverStatus.AUTO, CoverStatus.MANUAL) else CoverStatus.AUTO,
                    cover_raw,
                )
                self._lock_in_place(entity_id, cover_raw, sensor_unknown=True)
                continue

            if self._is_sensor_open(cover_raw, "vent_sensor"):
                self._enter_venting(entity_id, cover_raw, "wind protection ended")
                continue

            # Automation switched off during the storm: MANUAL right away
            # (not AUTO until the next sync), whatever the pre-wind status.
            target = self._status_for_automation(CoverStatus.AUTO, cover_raw)
            self._cover_states[entity_id] = target
            self.storage.update_cover_status(entity_id, target.value, None)
            self._sync_expected_after_protective_exit(entity_id)
            # Like the lock/vent exits: return to the rule right away instead
            # of waiting for min_time_between_changes.
            if target == CoverStatus.AUTO:
                self._post_protective_exit.add(entity_id)

        self._persist_runtime_state()
        if self.data is not None:
            self.async_set_updated_data(self.data)

    @callback
    def _handle_wind_sensor_change(self, new_state: Any) -> None:
        """Handle wind sensor state change."""
        if new_state is None:
            return
        if new_state.state in ("unavailable", "unknown"):
            _LOGGER.warning("Wind sensor unavailable, keeping current protection state")
            return
        self._check_wind_protection()
        self._schedule_refresh()

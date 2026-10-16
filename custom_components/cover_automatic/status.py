"""Cover statuses: pause, resume, manual mode, resume on match.

Mixin of CoverAutomaticCoordinator: it uses the coordinator's attributes."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from . import coordinator_common as common
from . import i18n
from .const import (
    LOG_EVENT_STATUS,
)
from .coordinator_common import (
    _UNUSABLE_STATES,
    MANUAL_OVERRIDE_TOLERANCE,
    RESUME_MATCH_GRACE,
    SETTLE_TIME,
)
from .models import CoverConfig, CoverStatus

# Same logger as the coordinator: the split does not change the log names
_LOGGER = logging.getLogger(__package__ + ".coordinator")


class StatusMixin:
    """Cover statuses: pause, resume, manual mode, resume on match."""

    @staticmethod
    def _status_for_automation(
        status: CoverStatus, cover_raw: dict[str, Any] | None
    ) -> CoverStatus:
        """Align a status restored after a protection with auto_enabled.

        The pre-lock / pre-wind status was recorded when the protection
        started; the automation may have been switched on or off since then
        (switch, import, resume refused while locked). A MANUAL status with
        the automation now on becomes AUTO -- the cover would otherwise never
        be driven again -- and AUTO / PAUSED with the automation off becomes
        MANUAL. Other statuses (VENTING) are returned unchanged.
        """
        auto_enabled = bool((cover_raw or {}).get("auto_enabled", True))
        if status == CoverStatus.MANUAL and auto_enabled:
            return CoverStatus.AUTO
        if status in (CoverStatus.AUTO, CoverStatus.PAUSED) and not auto_enabled:
            return CoverStatus.MANUAL
        return status

    def pause_cover(self, cover: CoverConfig, manual: bool = True) -> None:
        """Pause automation for a cover.

        Protective statuses (wind, window lock) and disabled automation
        (MANUAL) take precedence over a pause: overwriting them would only be
        undone by the next sync cycle, re-sending protective commands.

        manual: the pause comes from a detected manual override (the cover
        was moved by hand). Explicit pauses (pause / pause_all services) pass
        False: resume-on-match must not end them -- the user asked for a
        pause, not for a one-off position.
        """
        prev = self._cover_states.get(cover.entity_id, CoverStatus.AUTO)
        if prev in (CoverStatus.WIND_PROTECTED, CoverStatus.LOCKED, CoverStatus.MANUAL):
            _LOGGER.debug(
                "[%s] Pause ignored: cover is %s", cover.entity_id, prev.value
            )
            return
        self._cover_states[cover.entity_id] = CoverStatus.PAUSED
        self._runtime_dict("_pause_manual")[cover.entity_id] = manual
        if prev != CoverStatus.PAUSED:
            if self._paused_at is None:
                self._paused_at = {}
            self._paused_at[cover.entity_id] = common.time_mod.monotonic()
            self._log(LOG_EVENT_STATUS, cover.entity_id, f"{prev.value} -> paused",
                      {"key": "status_change", "from": prev.value, "to": "paused"})
        duration = cover.pause_duration if cover.pause_duration is not None else self.storage.pause_duration
        pause_until = common.dt_util.now().timestamp() + (duration * 60)
        self.storage.update_cover_status(
            cover.entity_id, CoverStatus.PAUSED.value, pause_until
        )
        if prev != CoverStatus.PAUSED:
            self._logbook(
                i18n.text(self.hass, "paused", minutes=duration),
                cover.entity_id,
            )
        if self.data is not None:
            self.async_set_updated_data(self.data)

    def resume_cover(self, entity_id: str, logbook_text: str | None = None) -> None:
        """Resume automation for a cover.

        logbook_text replaces the plain "resumed" logbook entry (automatic
        resume, with its reason).
        """
        # Wind protection cannot be overridden manually
        if self._wind_protected:
            return
        cover_raw = self.storage.get_cover_raw(entity_id)
        if cover_raw:
            # Don't override LOCKED status if lock/vent sensor is still active,
            # nor while the window state is unknown (possibly open window).
            # A refused resume is still the user's wish: the unlock restores
            # AUTO instead of the recorded pre-lock status (e.g. MANUAL).
            if self._cover_states.get(entity_id) == CoverStatus.LOCKED:
                if self._is_sensor_open(cover_raw, "lock_sensor") or self._is_sensor_open(cover_raw, "vent_sensor"):
                    self._pre_lock_states[entity_id] = CoverStatus.AUTO
                    self._persist_runtime_state()
                    return
                if self._is_sensor_unknown(cover_raw, "lock_sensor"):
                    _LOGGER.info("[%s] Resume refused: window state unknown, cover stays locked", entity_id)
                    self._pre_lock_states[entity_id] = CoverStatus.AUTO
                    self._persist_runtime_state()
                    return
            prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
            # Resuming ends any protective episode: a stale pre-lock status
            # would otherwise be restored by a later unlock.
            self._pre_lock_states.pop(entity_id, None)
            self._runtime_dict("_pause_manual").pop(entity_id, None)
            # Resume to VENTING if vent sensor is still open
            if self._is_sensor_open(cover_raw, "vent_sensor"):
                target = CoverStatus.VENTING
                self._cover_states[entity_id] = CoverStatus.VENTING
                self.storage.update_cover_status(entity_id, CoverStatus.VENTING.value, None)
                self._logbook(i18n.text(self.hass, "resumed_venting"), entity_id)
            else:
                target = CoverStatus.AUTO
                self._cover_states[entity_id] = CoverStatus.AUTO
                self.storage.update_cover_status(entity_id, CoverStatus.AUTO.value, None)
                self._logbook(logbook_text or i18n.text(self.hass, "resumed"), entity_id)
            if prev != target:
                _LOGGER.debug("[%s] Resumed: %s -> %s", entity_id, prev.value, target.value)
                self._log(LOG_EVENT_STATUS, entity_id, f"{prev.value} -> {target.value}",
                          {"key": "status_change", "from": prev.value, "to": target.value})
            # Sync expected position to current to prevent immediate re-pause
            self._update_last_position_from_state(entity_id)
            if self.data is not None:
                self.async_set_updated_data(self.data)

    def _sync_cover_statuses(self) -> None:
        """Sync cover statuses from sensor states.

        Updates _cover_states and storage for all covers. Called once per
        update cycle to avoid side effects in property accessors.
        Priority: LOCKED (window open) > WIND_PROTECTED > VENTING > PAUSED
        > AUTO > MANUAL.
        """
        # Check wind protection first (global)
        self._check_wind_protection()

        for entity_id in self.storage._data.get("covers", {}):
            cover_raw = self.storage.get_cover_raw(entity_id)
            if cover_raw is None:
                continue
            self._track_missing_lock_sensor(entity_id, cover_raw)

            # Wind protection: above everything except an open window (lock)
            if self._wind_protected:
                self._protect_one_from_wind(entity_id, cover_raw)
                continue

            # An unavailable lock/vent sensor is not "closed": keep the
            # protective status unchanged this cycle (no lock, no unlock).
            sensor_unknown = (
                self._is_sensor_unknown(cover_raw, "lock_sensor")
                or self._is_sensor_unknown(cover_raw, "vent_sensor")
            )

            # Check lock sensor state (window contact)
            if self._is_sensor_open(cover_raw, "lock_sensor"):
                if self._cover_states.get(entity_id) != CoverStatus.LOCKED:
                    lock_pos = self._cover_val(cover_raw, "lock_position")
                    current = self._get_current_position(entity_id)
                    if self._lock_moves(cover_raw, current, lock_pos):
                        lock_tilt = self._cover_val(cover_raw, "lock_tilt_position")
                        self._lock_cover(entity_id, lock_pos, lock_tilt=lock_tilt)
                    else:
                        prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
                        self._pre_lock_states[entity_id] = CoverStatus.AUTO if prev == CoverStatus.PAUSED else prev
                        self._lock_in_place(entity_id, cover_raw)
                self._sensor_unknown_kept.discard(entity_id)
                continue

            if sensor_unknown and self._cover_states.get(entity_id) in (
                CoverStatus.LOCKED, CoverStatus.VENTING,
            ):
                self._keep_status_sensor_unknown(entity_id, cover_raw)
                continue
            if entity_id in self._sensor_unknown_kept:
                self._sensor_unknown_kept.discard(entity_id)
                _LOGGER.debug("[%s] Lock/vent sensor available again", entity_id)

            # Check vent sensor state - also above auto_enabled
            if self._is_sensor_open(cover_raw, "vent_sensor"):
                current_status = self._cover_states.get(entity_id, CoverStatus.AUTO)
                # Respect PAUSED during venting (manual override)
                if current_status == CoverStatus.PAUSED:
                    pause_until = cover_raw.get("pause_until")
                    if pause_until and common.dt_util.now().timestamp() > pause_until:
                        # Pause expired -> back to VENTING. The cover may have
                        # been lowered manually during the pause: raise it to
                        # the vent position again (logs the status change).
                        _LOGGER.debug("[%s] Pause expired: paused -> venting", entity_id)
                        self._enter_venting(entity_id, cover_raw, "pause expired, vent open")
                elif current_status != CoverStatus.VENTING:
                    self._enter_venting(
                        entity_id, cover_raw, f"vent sensor {cover_raw.get('vent_sensor')} open"
                    )
                continue

            # If was locked/venting but sensors now closed, restore auto
            if self._cover_states.get(entity_id) in (CoverStatus.LOCKED, CoverStatus.VENTING):
                self._unlock_cover(entity_id)
                continue

            if not cover_raw.get("auto_enabled", True):
                # Persist MANUAL like the LOCKED/VENTING branches do, so the
                # status survives a restart (which resets all statuses to AUTO)
                # and the panel, which renders the persisted cover status,
                # reflects the disabled automation instead of showing AUTO.
                prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
                if prev != CoverStatus.MANUAL:
                    _LOGGER.debug("[%s] Automation disabled: %s -> manual", entity_id, prev.value)
                    self._log(LOG_EVENT_STATUS, entity_id, f"{prev.value} -> manual",
                              {"key": "status_change", "from": prev.value, "to": "manual"})
                    self._cover_states[entity_id] = CoverStatus.MANUAL
                    self.storage.update_cover_status(entity_id, CoverStatus.MANUAL.value, None)
                continue

            # Check pause expiry
            status = self._cover_states.get(entity_id, CoverStatus.AUTO)
            if status == CoverStatus.PAUSED:
                pause_until = cover_raw.get("pause_until")
                if pause_until and common.dt_util.now().timestamp() > pause_until:
                    _LOGGER.debug("[%s] Pause expired: paused -> auto", entity_id)
                    self._log(LOG_EVENT_STATUS, entity_id, "paused -> auto",
                              {"key": "status_change", "from": "paused", "to": "auto"})
                    self._cover_states[entity_id] = CoverStatus.AUTO
                    self.storage.update_cover_status(entity_id, CoverStatus.AUTO.value, None)
                    # Sync expected position to prevent false override after resume
                    self._update_last_position_from_state(entity_id)

        # Protective state must survive a restart (see _restore_cover_states)
        self._persist_runtime_state()

    def get_cover_status(self, entity_id: str) -> CoverStatus:
        """Get automation status for a cover (read-only, no side effects)."""
        cover_raw = self.storage.get_cover_raw(entity_id)
        if cover_raw is None:
            return CoverStatus.MANUAL

        live = self._cover_states.get(entity_id, CoverStatus.AUTO)
        if not cover_raw.get("auto_enabled", True):
            # Protective statuses also act on covers with automation off
            # (window open -> locked, storm -> wind position): report them.
            if live in (CoverStatus.LOCKED, CoverStatus.WIND_PROTECTED):
                return live
            return CoverStatus.MANUAL

        return live

    def _resume_on_match(self, cover: CoverConfig) -> bool:
        """End a manual pause when the cover is back at its rule's position.

        Two cases: the cover was put back by hand where the rule wants it, or
        the winning rule changed and now asks for the position the cover was
        left at. Only a PAUSED cover (never MANUAL, i.e. automation switched
        off, nor a protective status). Conditions: option enabled (cover or
        Settings), grace period after the pause started, cover still (not
        moving, no position report for SETTLE_TIME), a rule gives a target
        and the position (and the rule's tilt, when set) match it within the
        minimum position change. Returns True when the cover was resumed.
        """
        entity_id = cover.entity_id
        if self._cover_states.get(entity_id) != CoverStatus.PAUSED or not self.storage.enabled:
            return False
        enabled = cover.pause_resume_on_match
        if enabled is None:
            enabled = self.storage.pause_resume_on_match
        if not enabled:
            return False
        # Only pauses from a manual override; an explicit pause (service)
        # lasts its duration. Origin unknown (restored after a restart):
        # treated as manual, the previous behaviour.
        if not self._runtime_dict("_pause_manual").get(entity_id, True):
            return False
        now_mono = common.time_mod.monotonic()
        paused_at = (self._paused_at or {}).get(entity_id)
        if paused_at is not None and now_mono - paused_at < RESUME_MATCH_GRACE:
            return False
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (*_UNUSABLE_STATES, "opening", "closing"):
            return False
        # Stillness from the last real position/motion change: last_updated
        # also moves on attribute-only reports (Zigbee linkquality), so a
        # still cover never looked still. Unknown (no change seen since
        # startup): fall back to the state's last_changed.
        changed_at = self._runtime_dict("_position_changed_at").get(entity_id)
        if changed_at is not None:
            if now_mono - changed_at < SETTLE_TIME:
                return False
        else:
            last_changed = getattr(state, "last_changed", None)
            if isinstance(last_changed, datetime) and (
                (common.dt_util.utcnow() - last_changed).total_seconds() < SETTLE_TIME
            ):
                return False
        current = self._raw_position(state)
        if current is None:
            return False
        result = self.engine.evaluate_cover(cover)
        if result is None or result.position is None:
            return False
        cover_raw = self.storage.get_cover_raw(entity_id) or {}
        target = int(result.position)
        if self._is_sensor_open(cover_raw, "vent_sensor"):
            target = max(target, int(self._cover_val(cover_raw, "vent_position")))
        if cover_raw.get("inverted", False):
            target = 100 - target
        target = self._effective_position(entity_id, target)
        tolerance = self._cover_val(cover_raw, "min_position_change")
        if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool):
            tolerance = MANUAL_OVERRIDE_TOLERANCE
        if abs(current - target) > tolerance:
            return False
        tilt_target = getattr(result, "tilt_position", None)
        if tilt_target is not None and cover_raw.get("supports_tilt", False):
            tilt_now = state.attributes.get("current_tilt_position")
            if tilt_now is not None:
                try:
                    tilt_now = int(tilt_now)
                except (TypeError, ValueError):
                    tilt_now = None
            if tilt_now is not None:
                wanted = 100 - int(tilt_target) if cover_raw.get("inverted_tilt", False) else int(tilt_target)
                if abs(tilt_now - wanted) > tolerance:
                    return False
        rule = self.storage.rules.get(result.rule_id) if result.rule_id else None
        rule_name = rule.name if rule else (result.rule_id or "-")
        _LOGGER.info(
            "[%s] Pause ended: position %d%% matches rule %s", entity_id, current, rule_name,
        )
        self.resume_cover(
            entity_id, logbook_text=i18n.text(self.hass, "resumed_match", rule=rule_name),
        )
        if self._cover_states.get(entity_id) == CoverStatus.PAUSED:
            return False  # resume refused (wind protection)
        (self._paused_at or {}).pop(entity_id, None)
        return True

    def set_cover_manual(self, entity_id: str) -> None:
        """Set a cover's status to MANUAL (public API for platforms).

        The entities (automation switch, status sensor) are notified right
        away, also when a protection keeps the status: the switch state
        changed either way. Without it a toggle from the panel only showed
        in Home Assistant at the next update cycle (up to a minute later).
        """
        self._set_cover_manual_status(entity_id)
        if self.data is not None:
            self.async_set_updated_data(self.data)

    def _set_cover_manual_status(self, entity_id: str) -> None:
        """Status part of set_cover_manual (no entity notification)."""
        prev = self._cover_states.get(entity_id, CoverStatus.AUTO)
        if prev in (CoverStatus.LOCKED, CoverStatus.VENTING) or (
            self._wind_protected and prev == CoverStatus.WIND_PROTECTED
        ):
            # Protections keep acting on a disabled cover: the status stays
            # (no re-broadcast of the wind position to every cover, no lost
            # window lock). Overwriting LOCKED/VENTING would also make the
            # next sync lock/vent the cover again. After the protection ends
            # the sync sets MANUAL from auto_enabled=False.
            _LOGGER.debug("[%s] Automation disabled while %s: status kept", entity_id, prev.value)
            return
        if prev != CoverStatus.MANUAL:
            _LOGGER.debug("[%s] Automation disabled: %s -> manual", entity_id, prev.value)
            self._log(LOG_EVENT_STATUS, entity_id, f"{prev.value} -> manual",
                      {"key": "status_change", "from": prev.value, "to": "manual"})
        self._cover_states[entity_id] = CoverStatus.MANUAL
        self.storage.update_cover_status(entity_id, CoverStatus.MANUAL.value, None)

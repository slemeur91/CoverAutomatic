"""Data update coordinator for CoverAutomatic."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.logbook import async_log_entry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import coordinator_common as common
from . import i18n
from .apply import ApplyMixin
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOG_EVENT_RULE,
    LOG_EVENT_SCENARIO,
    LOG_EVENT_STATUS,
    SIGNAL_DATA_UPDATED,
)
from .contacts import ContactsMixin
from .coordinator_common import (
    PRE_LOCK_STATES_KEY,
    STARTUP_GRACE_PERIOD,
    WIND_STATE_KEY,
    _is_safety,
)
from .engine import RuleEngine
from .models import CoverConfig, CoverStatus
from .motion import MotionMixin
from .reload import ReloadMixin
from .status import StatusMixin
from .storage import ActivityLogStorage, CoverAutomaticStorage
from .sun import get_facade_sun_times, is_sun_on_facade
from .tracking import TrackingMixin
from .wind import WindMixin

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class CoverAutomaticCoordinator(
    TrackingMixin, WindMixin, ContactsMixin, MotionMixin, ReloadMixin, ApplyMixin, StatusMixin,
    DataUpdateCoordinator[dict[str, Any]],
):
    """Coordinate data updates and rule evaluation."""

    # Runtime helpers created lazily (see their accessors): the class
    # defaults keep coordinators built without __init__ (tests) working.
    _wind_tasks: set[asyncio.Task[None]] | None = None
    _lost_command_retries: dict[str, int] | None = None
    _apply_lock: asyncio.Lock | None = None
    _paused_at: dict[str, float] | None = None
    # Origin of each pause: True = manual override detected, False = explicit
    # pause (service). Unknown (e.g. restored after a restart) = manual.
    _pause_manual: dict[str, bool] | None = None
    # Covers that moved at all since our last position command (even during
    # the settle time): a lost-command resend is only for covers that did not
    # react at all -- a user counter-order also ends at the start position.
    _moved_since_command: set[str] | None = None
    # Monotonic time of the last position / motion change of each cover
    # (attribute-only reports such as Zigbee linkquality do not count)
    _position_changed_at: dict[str, float] | None = None
    # Covers whose lock sensor entity no longer exists (logged once)
    _lock_sensor_missing: set[str] | None = None
    # Covers whose move is blocked by an unknown window state (logged once
    # per blocking episode)
    _move_blocked_logged: set[str] | None = None
    # Wind protection restored from storage, still to be confirmed by the
    # wind sensor before the end of the startup grace period
    _wind_restore_pending: bool = False
    # The wind sensor gave a valid numeric value since startup
    _wind_value_seen: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        storage: CoverAutomaticStorage,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=config_entry,
        )
        self.storage = storage
        self.engine = RuleEngine(hass, storage)
        # Integration version shown in the panel, set by async_setup_api()
        self.version: str = "0"
        self._tracked_entities: set[str] = set()
        self._unsub_state_change: list[Any] = []
        self._cover_states: dict[str, CoverStatus] = {}
        self._last_positions: dict[str, int | None] = {}
        self._last_tilt_positions: dict[str, int | None] = {}
        self._tilt_tasks: dict[str, asyncio.Task[None]] = {}
        self._last_command_time: dict[str, float] = {}
        self._pending_settle: set[str] = set()
        self._pre_lock_states: dict[str, CoverStatus] = {}
        # Last readable state (open?) per lock/vent sensor. A report is only a
        # change against it: unavailable -> off after a reconnect is none.
        self._contact_open: dict[str, bool] = {}
        self._wind_protected: bool = False
        self._hysteresis_info: dict[str, str | None] = {}
        self._last_matching_rules: dict[str, str | None] = {}
        # Active scenario seen at the previous update (None before the first)
        self._last_scenario: str | None = None
        self._last_move_rule: dict[str, str | None] = {}
        # Last position actually commanded by the apply cycle (raw, inverted)
        self._last_sent_target: dict[str, int] = {}
        # Moves commanded by the apply cycle, for travel time measurement:
        # entity_id -> (monotonic start, start position, target), raw positions
        self._move_start: dict[str, tuple[float, int, int]] = {}
        # Covers that just exited a protective status (LOCKED / VENTING) and
        # need to bypass the time hysteresis once -- otherwise a long
        # min_time_between_changes leaves the cover at vent/lock position
        # long after the sensor has cleared.
        self._post_protective_exit: set[str] = set()
        # Covers currently driven by a safety rule: entity_id -> rule id
        self._safety_holds: dict[str, str] = {}
        # Covers whose protective status is kept because a lock/vent sensor
        # is unavailable (logged once per outage)
        self._sensor_unknown_kept: set[str] = set()
        # Wind sensor unavailable while protected (warned once per outage)
        self._wind_sensor_warned: bool = False
        # Pending wind command tasks (staggered sends), cancelled when the
        # wind protection ends or is re-activated and on shutdown
        self._wind_tasks = set()
        # Resends of lost position commands per cover (bounded)
        self._lost_command_retries = {}
        # Serialises apply cycles: one may sleep during the command stagger
        self._apply_lock = asyncio.Lock()
        # Start of each manual pause (monotonic), for the resume-on-match grace
        self._paused_at = {}
        self._pause_manual = {}
        self._moved_since_command = set()
        self._position_changed_at = {}
        self._lock_sensor_missing = set()
        self._move_blocked_logged = set()
        self._wind_restore_pending = False
        self._wind_value_seen = False
        self._startup_time: float = common.time_mod.monotonic()
        self._startup_skip: bool = True
        self._grace_synced: bool = False
        self._unsub_update_listener: Any = None
        self.log_storage: ActivityLogStorage | None = None

    def _runtime_set(self, name: str) -> set[str]:
        """Per-cover runtime set created lazily (coordinators built without __init__)."""
        value = getattr(self, name, None)
        if value is None:
            value = set()
            setattr(self, name, value)
        return value

    def _runtime_dict(self, name: str) -> dict[str, Any]:
        """Per-cover runtime dict created lazily (see _runtime_set)."""
        value = getattr(self, name, None)
        if value is None:
            value = {}
            setattr(self, name, value)
        return value

    def _in_startup_grace(self) -> bool:
        """Whether the startup grace period (sensor stabilisation) is running."""
        return (common.time_mod.monotonic() - self._startup_time) < STARTUP_GRACE_PERIOD

    def _cover_val(self, cover_raw: dict[str, Any], key: str) -> Any:
        """Get cover config value with global fallback from storage."""
        val = cover_raw.get(key)
        if val is not None:
            return val
        return getattr(self.storage, key, None)

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        await self.storage.async_load()
        self._restore_cover_states()
        await self._async_setup_default_scenarios()
        self._setup_state_tracking()
        self._unsub_update_listener = self.async_add_listener(
            self._fire_update_event
        )

    @callback
    def _fire_update_event(self) -> None:
        """Notify panel subscriptions (WebSocket) of data changes."""
        async_dispatcher_send(self.hass, SIGNAL_DATA_UPDATED)

    def _restore_cover_states(self) -> None:
        """Restore cover states from persisted storage data.

        Restores PAUSED (with unexpired timer), the protective statuses
        LOCKED / VENTING (with their pre-lock status) and, when the wind
        protection was active and is still configured, WIND_PROTECTED.
        Everything else starts as AUTO and is re-derived by
        _sync_cover_statuses.

        The protective statuses must survive a restart: battery sensors
        (Zigbee) or alarm integrations often report "unknown" for minutes
        after startup, and an AUTO cover whose window state is unknown would
        otherwise be closed by the next night rule on an open window. While
        the sensor stays unknown the sync keeps the restored status; once it
        reports "closed" the cover is unlocked normally.
        """
        data = self.storage._data
        wind_configured = bool(self.storage.wind_sensor) and self.storage.wind_speed_threshold > 0
        self._wind_protected = data.get(WIND_STATE_KEY) is True and wind_configured
        # Confirmed by the wind sensor before the end of the grace period,
        # otherwise dropped (see _drop_unconfirmed_wind_restore)
        self._wind_restore_pending = self._wind_protected
        if self._wind_protected:
            _LOGGER.info("Startup: wind protection was active, kept until the wind sensor reports")
        stored_pre_lock = data.get(PRE_LOCK_STATES_KEY)
        if not isinstance(stored_pre_lock, dict):
            stored_pre_lock = {}
        kept = {CoverStatus.LOCKED.value, CoverStatus.VENTING.value}
        if self._wind_protected:
            kept.add(CoverStatus.WIND_PROTECTED.value)
        for entity_id, cover_data in data.get("covers", {}).items():
            stored_status = cover_data.get("status", "auto")
            if stored_status == CoverStatus.PAUSED.value:
                pause_until = cover_data.get("pause_until")
                if pause_until and common.dt_util.now().timestamp() < pause_until:
                    self._cover_states[entity_id] = CoverStatus.PAUSED
                    continue
            if stored_status in kept:
                self._cover_states[entity_id] = CoverStatus(stored_status)
                try:
                    self._pre_lock_states[entity_id] = CoverStatus(stored_pre_lock.get(entity_id))
                except ValueError:
                    pass  # no (or invalid) pre-lock status: unlock falls back to AUTO
                _LOGGER.debug("[%s] Startup: restored %s", entity_id, stored_status)
                continue
            # Reset everything else to AUTO (lock/vent re-detected from sensors)
            if stored_status != CoverStatus.AUTO.value:
                _LOGGER.debug("[%s] Startup: reset %s -> AUTO", entity_id, stored_status)
            self._cover_states[entity_id] = CoverStatus.AUTO
            if stored_status != CoverStatus.AUTO.value:
                self.storage.update_cover_status(
                    entity_id, CoverStatus.AUTO.value, None
                )
        self._persist_runtime_state()

    def _persist_runtime_state(self) -> None:
        """Write the wind state and the pre-lock statuses into the store.

        Only written (debounced save) when changed. Called after every sync
        cycle as well, which also rewrites the keys after an import replaced
        the whole store content.
        """
        data = self.storage._data
        pre_lock = {
            entity_id: status.value
            for entity_id, status in self._pre_lock_states.items()
            if isinstance(status, CoverStatus)
        }
        if data.get(WIND_STATE_KEY) is self._wind_protected and data.get(PRE_LOCK_STATES_KEY) == pre_lock:
            return
        data[WIND_STATE_KEY] = self._wind_protected
        data[PRE_LOCK_STATES_KEY] = pre_lock
        self.storage._schedule_save()

    async def _async_setup_default_scenarios(self) -> None:
        """Create default scenarios (named in the HA language) if none exist.

        Existing default scenarios whose name was never changed (still one of
        the built-in names in any language) are renamed to the current HA
        language, so an English-named "Everyday" becomes "Quotidien" on a
        French installation. User-chosen names are left untouched.
        """
        from .models import Scenario

        icons = {
            "everyday": "mdi:home",
            "summer": "mdi:white-balance-sunny",
            "winter": "mdi:snowflake",
            "vacation": "mdi:airplane",
            "cinema": "mdi:movie",
            "manual": "mdi:hand-back-right",
        }
        if not self.storage.scenarios:
            for scenario_id in i18n.DEFAULT_SCENARIO_IDS:
                await self.storage.async_add_scenario(
                    Scenario(
                        id=scenario_id,
                        name=i18n.text(self.hass, f"scenario_{scenario_id}"),
                        icon=icons[scenario_id],
                    ),
                    save=False,
                )
            await self.storage.async_save()
            return

        renamed = False
        for scenario_id in i18n.DEFAULT_SCENARIO_IDS:
            raw = self.storage._data.get("scenarios", {}).get(scenario_id)
            if not isinstance(raw, dict):
                continue
            localized = i18n.text(self.hass, f"scenario_{scenario_id}")
            name = raw.get("name")
            if name != localized and name in i18n.default_scenario_names(scenario_id):
                raw["name"] = localized
                renamed = True
        if renamed:
            self.storage._invalidate_cache()
            await self.storage.async_save()

    def get_active_rules(self) -> dict[str, list[str]]:
        """Get currently active rules and their matched covers.

        Returns dict of {rule_id: [cover_entity_ids]}.
        """
        if self.data and "active_rules" in self.data:
            return self.data["active_rules"]
        return {}

    def get_live_cover_data(self) -> dict[str, dict[str, Any]]:
        """Get live runtime data for all covers."""
        result: dict[str, dict[str, Any]] = {}
        if self.data:
            for entity_id, cover_data in self.data.get("covers", {}).items():
                cover_raw = self.storage.get_cover_raw(entity_id)
                pause_until = cover_raw.get("pause_until") if cover_raw else None
                rule_id = cover_data.get("matching_rule_id")
                rule_name = None
                if rule_id:
                    rule = self.storage.rules.get(rule_id)
                    rule_name = rule.name if rule else rule_id
                # Comfort mode from engine cache
                comfort = self.engine._last_comfort_mode.get(entity_id)
                result[entity_id] = {
                    "target_position": cover_data.get("target_position"),
                    "hysteresis": self._hysteresis_info.get(entity_id),
                    "pause_until": pause_until,
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "comfort_mode": comfort.value if comfort else None,
                    "last_change": cover_raw.get("last_position_change") if cover_raw else None,
                }
        return result

    # ---- Public read-only accessors for entities / dashboard card ----

    @property
    def wind_protected(self) -> bool:
        """Whether wind protection is currently active."""
        return self._wind_protected

    def get_wind_speed(self) -> float | None:
        """Current wind speed from the configured sensor (None if unknown)."""
        return self._get_wind_speed()

    def get_logical_position(self, entity_id: str) -> int | None:
        """Current position on the rules' scale (inverted covers mirrored)."""
        return self._get_current_position(entity_id)

    def get_cover_live(self, entity_id: str) -> dict[str, Any]:
        """Live runtime data of one cover (rule, target, pause, comfort)."""
        cover_data = (self.data or {}).get("covers", {}).get(entity_id, {})
        cover_raw = self.storage.get_cover_raw(entity_id) or {}
        rule_id = cover_data.get("matching_rule_id")
        rule_name = None
        if rule_id:
            rule = self.storage.rules.get(rule_id)
            rule_name = rule.name if rule else rule_id
        comfort = self.engine._last_comfort_mode.get(entity_id)
        return {
            "target_position": cover_data.get("target_position"),
            "rule_id": rule_id,
            "rule_name": rule_name,
            "safety": bool(cover_data.get("safety", False)),
            "pause_until": cover_raw.get("pause_until"),
            "comfort_mode": comfort.value if comfort else None,
            "last_change": cover_raw.get("last_position_change"),
        }

    def _facade_live(self, facade_id: str, facade: Any) -> dict[str, Any]:
        """Live data of a facade: sun on it now, today's sun entry/exit times.

        The times (local HH:MM, None when the sun does not reach the facade)
        are computed once per day and facade. They are only displayed: a
        failure leaves them empty instead of blocking the update cycle.
        """
        try:
            sun_entry, sun_exit = get_facade_sun_times(self.hass, facade)
        except Exception:  # noqa: BLE001 -- display only
            _LOGGER.debug("Sun times unavailable for facade %s", facade_id, exc_info=True)
            sun_entry = sun_exit = None
        return {
            "sun_on_facade": is_sun_on_facade(self.hass, facade),
            "sun_entry": sun_entry,
            "sun_exit": sun_exit,
        }

    def get_live_facade_data(self) -> dict[str, dict[str, Any]]:
        """Get live runtime data for facades (sun on facade)."""
        if self.data:
            return self.data.get("facades", {})
        return {}

    def _log(
        self, event_type: str, entity_id: str | None = None,
        message: str = "", data: dict[str, Any] | None = None,
    ) -> None:
        """Add an activity log entry if log_storage is available."""
        if self.log_storage:
            self.log_storage.add_entry(event_type, entity_id, message, data)

    def _log_scenario_change(self) -> None:
        """Write the new active scenario to the activity log when it changed.

        Checked once per update, so every way of switching (select entity,
        service, panel, deleted scenario) is covered. The first update after
        startup only records the current scenario.
        """
        current = self.storage.effective_active_scenario
        # getattr: coordinators built without __init__ in tests
        previous, self._last_scenario = self._last_scenario, current
        if previous is None or previous == current:
            return
        scenarios = self.storage.scenarios

        def name(scenario_id: str) -> str:
            scenario = scenarios.get(scenario_id)
            return scenario.name if scenario else scenario_id

        _LOGGER.info("Scenario changed: %s -> %s", previous, current)
        self._log(LOG_EVENT_SCENARIO, None, f"{previous} -> {current}",
                  {"key": "scenario_change", "from": name(previous), "to": name(current),
                   "from_id": previous, "to_id": current})
        self._logbook(i18n.text(self.hass, "scenario_changed", scenario=name(current)))

    def _logbook(self, message: str, entity_id: str | None = None) -> None:
        """Write an entry to the HA logbook when enabled in settings."""
        if not self.storage.logbook_enabled:
            return
        async_log_entry(
            self.hass,
            i18n.text(self.hass, "logbook_name"),
            message,
            domain=DOMAIN,
            entity_id=entity_id,
        )

    @callback
    def _schedule_refresh(self) -> None:
        """Request a debounced refresh from a callback.

        The task belongs to the config entry, so it is cancelled on unload
        instead of outliving the coordinator.
        """
        entry = self.config_entry
        if entry is None:
            self.hass.async_create_task(self.async_request_refresh())
            return
        entry.async_create_background_task(
            self.hass, self.async_request_refresh(), f"{DOMAIN}_refresh"
        )

    async def _async_update_data(self) -> dict[str, Any]:  # noqa: C901 -- complexity 16, to reduce (see CHANGELOG 2.1.3)
        """Update data and evaluate rules."""
        # Compile native Home Assistant conditions (async) so the rule
        # evaluation below can run them synchronously; track new entities.
        try:
            if await self.engine.async_prepare_ha_conditions():
                self._setup_state_tracking()
        except Exception:  # noqa: BLE001 -- never block the update cycle
            _LOGGER.exception("Failed to prepare Home Assistant conditions")

        # Sync cover statuses from sensors before evaluation
        self._sync_cover_statuses()
        self._log_scenario_change()

        result: dict[str, Any] = {
            "covers": {},
            "facades": {},
            "scenario": self.storage.active_scenario,
        }
        # Track which rules are currently winning for which covers
        active_rules: dict[str, list[str]] = {}

        for facade_id, facade in self.storage.facades.items():
            result["facades"][facade_id] = self._facade_live(facade_id, facade)

        # Safety takeovers/releases only act once commands may be sent
        in_grace = (common.time_mod.monotonic() - self._startup_time) < STARTUP_GRACE_PERIOD

        for entity_id, cover in self.storage.covers.items():
            status = self.get_cover_status(entity_id)
            target_position: int | None = None
            target_tilt_position: int | None = None
            matching_rule_id: str | None = None

            if not in_grace and status == CoverStatus.PAUSED and self._resume_on_match(cover):
                status = self.get_cover_status(entity_id)
            engine_result = self._evaluate_cover_rules(cover, status)
            safety = _is_safety(engine_result)
            if not in_grace and self._update_safety_hold(
                entity_id, engine_result if safety else None, status
            ):
                # Released a paused cover: evaluate it as AUTO right away
                status = self.get_cover_status(entity_id)
                engine_result = self._evaluate_cover_rules(cover, status)
                safety = _is_safety(engine_result)
            if engine_result is not None:
                target_position = engine_result.position
                target_tilt_position = engine_result.tilt_position
                matching_rule_id = engine_result.rule_id
                if matching_rule_id:
                    active_rules.setdefault(matching_rule_id, []).append(entity_id)

            # Always refresh comfort mode for live display (independent of rules)
            self.engine._get_comfort_mode(cover)

            # Log rule match changes
            prev_rule = self._last_matching_rules.get(entity_id)
            if matching_rule_id != prev_rule:
                self._last_matching_rules[entity_id] = matching_rule_id
                if matching_rule_id:
                    rule_name = self.storage.rules.get(matching_rule_id)
                    rn = rule_name.name if rule_name else matching_rule_id
                    self._log(
                        LOG_EVENT_RULE, entity_id, f"{rn} -> {target_position}%",
                        {"key": "rule", "rule_id": matching_rule_id, "rule_name": rn,
                         "position": target_position},
                    )

            result["covers"][entity_id] = {
                "status": status.value,
                "target_position": target_position,
                "target_tilt_position": target_tilt_position,
                "facade_id": cover.facade_id,
                "matching_rule_id": matching_rule_id,
                "safety": safety,
            }

        result["active_rules"] = active_rules

        # Store result first so async_apply_positions can use it
        self.data = result

        # Skip position application during startup grace period to avoid
        # unnecessary movements caused by incomplete sensor data (e.g. sun.sun,
        # temperature sensors not yet stable), which would trigger low-priority
        # fallback rules instead of the correct shading rules.
        startup_elapsed = common.time_mod.monotonic() - self._startup_time
        if startup_elapsed < STARTUP_GRACE_PERIOD:
            if self._startup_skip:
                self._startup_skip = False
                # Initialize _last_positions from current HA state
                for eid in self.storage._data.get("covers", {}):
                    self._update_last_position_from_state(eid)
                _LOGGER.debug("Startup: initialized positions from HA state")
            _LOGGER.debug(
                "Startup grace period: skipping position application (%ds remaining)",
                int(STARTUP_GRACE_PERIOD - startup_elapsed),
            )
            return result

        # Re-sync positions after grace period ends (devices now fully
        # connected, positions stable -- overwrite stale startup values)
        if not self._grace_synced:
            self._grace_synced = True
            for eid in self.storage._data.get("covers", {}):
                self._update_last_position_from_state(eid)
            _LOGGER.info("Grace period ended: re-synced cover positions from HA state")

        # Apply calculated positions to covers
        await self.async_apply_positions()

        return result

    def _evaluate_cover_rules(self, cover: CoverConfig, status: CoverStatus) -> Any:
        """Evaluate the rules that may drive a cover in its current status.

        AUTO/VENTING covers with the automation enabled use all rules. Covers
        that are paused, manual, wind protected, or with the global automation
        disabled only follow safety rules. LOCKED covers follow none.
        """
        if status in (CoverStatus.AUTO, CoverStatus.VENTING) and self.storage.enabled:
            return self.engine.evaluate_cover(cover)
        if status == CoverStatus.LOCKED:
            return None
        result = self.engine.evaluate_cover(cover, safety_only=True)
        return result if _is_safety(result) else None

    def _update_safety_hold(
        self, entity_id: str, target: Any, status: CoverStatus
    ) -> bool:
        """Track which covers a safety rule drives; handle takeover/release.

        On release a paused cover returns to AUTO, a wind protected one goes
        back to the wind position (wind still active), manual covers and a
        disabled automation get no further command.
        Returns True when the cover status changed (pause cancelled).
        """
        new_rule = target.rule_id if target is not None else None
        prev_rule = self._safety_holds.get(entity_id)
        if new_rule == prev_rule:
            return False
        if new_rule:
            self._safety_holds[entity_id] = new_rule
            if prev_rule is not None:
                _LOGGER.debug("[%s] Safety rule %s -> %s", entity_id, prev_rule, new_rule)
                return False
            rule_name = target.rule_name or new_rule
            status_val = status.value if self.storage.enabled else f"{status.value}, automation off"
            _LOGGER.info(
                "[%s] Safety rule '%s' takes over (%s) -> %d%%",
                entity_id, rule_name, status_val, target.position,
            )
            self._log(LOG_EVENT_RULE, entity_id,
                      f"Safety rule {rule_name} takes over ({status_val}) -> {target.position}%",
                      {"key": "safety_takeover", "rule_id": new_rule, "rule_name": rule_name,
                       "status": status.value, "position": target.position})
            return False

        # Released
        self._safety_holds.pop(entity_id, None)
        rule = self.storage.rules.get(prev_rule)
        rule_name = rule.name if rule else prev_rule
        live = self._cover_states.get(entity_id, CoverStatus.AUTO)
        changed = False
        if status == CoverStatus.PAUSED and live == CoverStatus.PAUSED:
            # The pause is cancelled: the cover returns to normal automation
            self._cover_states[entity_id] = CoverStatus.AUTO
            self.storage.update_cover_status(entity_id, CoverStatus.AUTO.value, None)
            self._update_last_position_from_state(entity_id)
            self._log(LOG_EVENT_STATUS, entity_id, "paused -> auto",
                      {"key": "status_change", "from": "paused", "to": "auto"})
            released_to = "paused -> auto"
            changed = True
        elif live == CoverStatus.WIND_PROTECTED and self._wind_protected:
            self._send_wind_position(entity_id)
            released_to = f"wind protection -> {self._wind_position()}%"
        else:
            released_to = status.value if self.storage.enabled else "automation off"
        _LOGGER.info("[%s] Safety rule '%s' released (%s)", entity_id, rule_name, released_to)
        self._log(LOG_EVENT_RULE, entity_id, f"Safety rule {rule_name} released ({released_to})",
                  {"key": "safety_release", "rule_id": prev_rule, "rule_name": rule_name,
                   "status": status.value})
        return changed

    def rename_rule_references(self, old_id: str, new_id: str) -> None:
        """Follow a rule id rename in runtime state (no spurious rule change)."""
        for mapping in (self._last_move_rule, self._last_matching_rules, self._safety_holds):
            for key, value in mapping.items():
                if value == old_id:
                    mapping[key] = new_id
        if not isinstance(self.data, dict):
            return
        for cover_data in (self.data.get("covers") or {}).values():
            if isinstance(cover_data, dict) and cover_data.get("matching_rule_id") == old_id:
                cover_data["matching_rule_id"] = new_id
        active = self.data.get("active_rules")
        if isinstance(active, dict) and old_id in active:
            self.data["active_rules"] = {
                (new_id if key == old_id else key): value for key, value in active.items()
            }

    @callback
    def async_sync_entities(self) -> None:
        """Sync HA entities with the configured covers/facades.

        Removes registry entries of deleted covers/facades and notifies the
        platforms (coordinator listeners) so they add entities for new ones.
        """
        entry = getattr(self, "config_entry", None)
        if entry is not None:
            from .entities import async_cleanup_orphan_entities

            async_cleanup_orphan_entities(self.hass, entry, self.storage)
        self.async_update_listeners()

    def reconcile_after_import(self) -> None:
        """Align the cover statuses with auto_enabled after an import.

        An import can switch a cover's automation on or off without going
        through the switch entity: a re-enabled cover would stay MANUAL (and
        never be driven again), a disabled one would stay AUTO until the next
        sync. Protective statuses are kept by resume_cover/set_cover_manual.
        """
        for entity_id, cover_raw in list(self.storage._data.get("covers", {}).items()):
            if not isinstance(cover_raw, dict):
                continue
            if cover_raw.get("auto_enabled", True):
                if self._cover_states.get(entity_id, CoverStatus.AUTO) == CoverStatus.MANUAL:
                    self.resume_cover(entity_id)
            else:
                self.set_cover_manual(entity_id)

    async def async_shutdown(self) -> None:
        """Shut down coordinator."""
        if self._unsub_update_listener:
            self._unsub_update_listener()
            self._unsub_update_listener = None

        # Pending staggered wind commands must not run after unload
        self._cancel_wind_tasks()
        self._persist_runtime_state()

        # Cancel pending tilt tasks
        for task in self._tilt_tasks.values():
            if not task.done():
                task.cancel()
        self._tilt_tasks.clear()

        for unsub in self._unsub_state_change:
            unsub()
        self._unsub_state_change.clear()
        # Flush pending debounced saves to prevent data loss
        self.storage.flush_pending_save()
        if self.log_storage:
            self.log_storage.flush_pending_save()
        try:
            await self.storage.async_save()
            if self.log_storage:
                await self.log_storage.async_save()
        except Exception:
            _LOGGER.warning("Failed to flush pending save during shutdown")

        # Base class: cancel the scheduled refresh and shut the debouncer
        # down, so no refresh (and no cover command) can run after unload.
        await super().async_shutdown()

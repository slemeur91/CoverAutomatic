"""State tracking: which entities are watched and how their changes are routed.

Mixin of CoverAutomaticCoordinator: it uses the coordinator's attributes."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

from .sun import SUN_ENTITY_ID

if TYPE_CHECKING:
    from homeassistant.core import Event


class TrackingMixin:
    """State tracking: which entities are watched and how their changes are routed."""

    def _setup_state_tracking(self, full_refresh: bool = False) -> None:  # noqa: C901 -- complexity 34, to reduce (see CHANGELOG 2.1.3)
        """Set up state change tracking for relevant entities.

        Args:
            full_refresh: If True, remove all existing listeners and re-register.
                         If False, only add listeners for new entities.
        """
        if full_refresh:
            # Remove all existing listeners
            for unsub in self._unsub_state_change:
                unsub()
            self._unsub_state_change.clear()
            self._tracked_entities.clear()

            # Cleanup orphaned entries from runtime state dicts
            current_covers = set(self.storage._data.get("covers", {}).keys())
            for state_dict in (
                self._cover_states,
                self._last_positions,
                self._last_tilt_positions,
                self._pre_lock_states,
                self._last_command_time,
                self._tilt_tasks,
                self._hysteresis_info,
                self._last_matching_rules,
                self._last_move_rule,
                self._last_sent_target,
                self._move_start,
                self._safety_holds,
            ):
                orphaned = set(state_dict.keys()) - current_covers
                for entity_id in orphaned:
                    value = state_dict.pop(entity_id)
                    if isinstance(value, asyncio.Task) and not value.done():
                        value.cancel()
            if self._lost_command_retries:
                for entity_id in set(self._lost_command_retries) - current_covers:
                    self._lost_command_retries.pop(entity_id, None)
            if self._paused_at:
                for entity_id in set(self._paused_at) - current_covers:
                    self._paused_at.pop(entity_id, None)
            for name in ("_pause_manual", "_position_changed_at"):
                mapping = self._runtime_dict(name)
                for entity_id in set(mapping) - current_covers:
                    mapping.pop(entity_id, None)
            for name in ("_moved_since_command", "_lock_sensor_missing", "_move_blocked_logged"):
                entries = self._runtime_set(name)
                entries -= set(entries) - current_covers
            # Per-entity sets: drop orphaned entity ids as well
            for state_set in (
                self._pending_settle, self._post_protective_exit, self._sensor_unknown_kept,
            ):
                state_set -= set(state_set) - current_covers
            # Rule engine per-cover caches (comfort mode, warnings)
            engine = getattr(self, "engine", None)
            if engine is not None:
                engine.forget_covers_except(current_covers)

        entities_to_track: set[str] = {SUN_ENTITY_ID}

        for entity_id, cover_data in self.storage._data.get("covers", {}).items():
            entities_to_track.add(entity_id)
            if lock_sensor := cover_data.get("lock_sensor"):
                entities_to_track.add(lock_sensor)
            if vent_sensor := cover_data.get("vent_sensor"):
                entities_to_track.add(vent_sensor)
            if indoor_sensor := cover_data.get("indoor_temp_sensor"):
                entities_to_track.add(indoor_sensor)
            if isinstance(occupancy := cover_data.get("occupancy_sensor"), str) and occupancy:
                entities_to_track.add(occupancy)

        if self.storage.outdoor_temp_sensor:
            entities_to_track.add(self.storage.outdoor_temp_sensor)

        if self.storage.indoor_temp_sensor:
            entities_to_track.add(self.storage.indoor_temp_sensor)

        if self.storage.weather_entity:
            entities_to_track.add(self.storage.weather_entity)

        if self.storage.wind_sensor:
            entities_to_track.add(self.storage.wind_sensor)

        if self.storage.solar_sensor:
            entities_to_track.add(self.storage.solar_sensor)

        if self.storage.workday_sensor:
            entities_to_track.add(self.storage.workday_sensor)

        # Entity holding the solar threshold (a change re-evaluates the rules)
        if isinstance(ref := self.storage.solar_threshold_entity, str) and ref:
            entities_to_track.add(ref)

        for rule_data in self.storage._data.get("rules", {}).values():
            for condition in rule_data.get("conditions", []):
                params = condition.get("params") or {}
                if not isinstance(params, dict):
                    continue
                # The panel stores entities under "entity_id" (state_is,
                # numeric_state, workday); "sensor"/"entity" are legacy keys.
                for key in ("sensor", "entity", "entity_id"):
                    ref = params.get(key)
                    if isinstance(ref, str) and ref:
                        entities_to_track.add(ref)

        # Entities referenced by native Home Assistant conditions (incl. templates)
        try:
            entities_to_track |= set(self.engine.ha_condition_entities())
        except (AttributeError, TypeError):
            pass

        new_entities = entities_to_track - self._tracked_entities

        if new_entities:
            unsub = async_track_state_change_event(
                self.hass,
                list(new_entities),
                self._async_on_state_change,
            )
            self._unsub_state_change.append(unsub)
            self._tracked_entities.update(new_entities)

    def refresh_state_tracking(self) -> None:
        """Refresh state tracking after configuration changes.

        Performs a full refresh to ensure removed entities are no longer tracked.
        """
        self._setup_state_tracking(full_refresh=True)

    def _get_covers_by_sensor(self, sensor_id: str) -> tuple[list[str], list[str]]:
        """Get cover entity IDs that use a specific sensor.

        Returns:
            Tuple of (lock_covers, vent_covers) - covers using this as lock/vent sensor.
        """
        lock_covers = []
        vent_covers = []
        for entity_id, cover_data in self.storage._data.get("covers", {}).items():
            if cover_data.get("lock_sensor") == sensor_id:
                lock_covers.append(entity_id)
            if cover_data.get("vent_sensor") == sensor_id:
                vent_covers.append(entity_id)
        return lock_covers, vent_covers

    @callback
    def _async_on_state_change(self, event: Event) -> None:
        """Handle state changes of tracked entities."""
        entity_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if entity_id in self.storage._data.get("covers", {}):
            self._handle_cover_state_change(entity_id, old_state, new_state)
            # A managed cover may also feed a rule condition
            if self._is_rule_entity(entity_id):
                self._schedule_refresh()
        elif entity_id == self.storage.wind_sensor:
            self._handle_wind_sensor_change(new_state)
        else:
            lock_covers, vent_covers = self._get_covers_by_sensor(entity_id)
            if lock_covers or vent_covers:
                self._handle_contact_sensor_change(
                    entity_id, lock_covers, vent_covers, old_state, new_state
                )
                # The same entity may also feed a rule condition
                if self._is_rule_entity(entity_id):
                    self._schedule_refresh()
            else:
                self._schedule_refresh()

    def _is_rule_entity(self, entity_id: str) -> bool:
        """Return True if a rule condition references this entity."""
        try:
            if entity_id in self.engine.ha_condition_entities():
                return True
        except (AttributeError, TypeError):
            pass
        for rule_data in self.storage._data.get("rules", {}).values():
            for condition in rule_data.get("conditions", []):
                params = condition.get("params") or {}
                if isinstance(params, dict) and entity_id in (
                    params.get("sensor"), params.get("entity"), params.get("entity_id"),
                ):
                    return True
        return False

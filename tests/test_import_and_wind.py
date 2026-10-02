"""Reliable import (types, runtime state) and lock priority over wind."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.cover_automatic.models import Condition, CoverConfig, CoverStatus, Rule
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401
from tests.test_storage import mock_hass as st_hass  # noqa: F401
from tests.test_storage import mock_store, storage  # noqa: F401


def _base(**settings) -> dict:
    return {
        "facades": {}, "rules": {}, "scenarios": {"everyday": {"id": "everyday", "name": "E"}},
        "covers": {"cover.a": {"entity_id": "cover.a", "name": "A"}},
        **settings,
    }


class TestImportTypes:
    @pytest.mark.asyncio
    async def test_text_values_are_converted(self, storage) -> None:
        storage._data = _base()
        await storage.async_import_data(_base(
            enabled="false", logbook_enabled="0", sun_neutral_ignore="off",
            pause_duration="15", comfort_temp_min="20.5", wind_position="30",
        ))
        assert storage.enabled is False
        assert storage.logbook_enabled is False
        assert storage.sun_neutral_ignore is False
        assert storage.pause_duration == 15
        assert storage.comfort_temp_min == 20.5
        assert storage.wind_position == 30

    @pytest.mark.asyncio
    async def test_unusable_value_keeps_current(self, storage) -> None:
        storage._data = _base(pause_duration=30)
        await storage.async_import_data(_base(pause_duration="abc", enabled="maybe", wind_sensor=12))
        assert storage.pause_duration == 30
        assert storage._data.get("enabled") is None  # key dropped -> default
        assert storage.enabled is True
        assert storage.wind_sensor is None

    def test_flags_of_covers_rules_conditions(self) -> None:
        cover = CoverConfig.from_dict({"entity_id": "c", "name": "C", "auto_enabled": "false",
                                       "inverted": "true", "lock_hold_position": "0"})
        assert (cover.auto_enabled, cover.inverted, cover.lock_hold_position) == (False, True, False)
        rule = Rule.from_dict({"id": "r", "name": "R", "enabled": "false"})
        assert rule.enabled is False
        cond = Condition.from_dict({"type": "state_is", "params": {}, "negate": "false"})
        assert cond.negate is False


class TestImportRuntimeState:
    @pytest.mark.asyncio
    async def test_status_and_pause_stay_local(self, storage) -> None:
        storage._data = _base()
        storage._data["covers"]["cover.a"].update(status="paused", pause_until=9e12, last_position_change=5.0)
        imported = _base()
        imported["covers"]["cover.a"].update(status="auto", pause_until=None, last_position_change=1.0)
        imported["covers"]["cover.b"] = {"entity_id": "cover.b", "name": "B", "status": "locked",
                                         "pause_until": 123.0}
        await storage.async_import_data(imported)
        a = storage._data["covers"]["cover.a"]
        assert (a["status"], a["pause_until"], a["last_position_change"]) == ("paused", 9e12, 5.0)
        b = storage._data["covers"]["cover.b"]
        assert (b["status"], b["pause_until"]) == ("auto", None)


class TestLockBeatsWind:
    def _raw(self, **extra) -> dict:
        return {"auto_enabled": True, "lock_sensor": "binary_sensor.w", "lock_position": 100,
                "inverted": False, **extra}

    def test_window_opened_during_wind_locks_and_stays(self, coordinator, mock_hass, mock_storage) -> None:
        raw = self._raw()
        mock_storage._data = {"covers": {"cover.t": raw, "cover.u": {"auto_enabled": True}}}
        mock_storage.get_cover_raw.side_effect = lambda e: mock_storage._data["covers"].get(e)
        coordinator._wind_protected = True
        coordinator._cover_states = {"cover.t": CoverStatus.WIND_PROTECTED, "cover.u": CoverStatus.WIND_PROTECTED}
        mock_hass.states.get.side_effect = (
            lambda e: MockState("on") if e.startswith("binary") else MockState("closed", {"current_position": 0}))
        coordinator._handle_contact_sensor_change("binary_sensor.w", ["cover.t"], [], MockState("off"), MockState("on"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        # Next cycles: the locked cover stays locked and no wind broadcast happens
        with patch.object(coordinator, "_check_wind_protection"), \
             patch.object(coordinator, "_send_wind_position") as send_one, \
             patch.object(coordinator, "_activate_wind_protection") as send_all:
            coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        send_one.assert_not_called()
        send_all.assert_not_called()

    def test_window_closed_during_wind_back_to_wind_only_this_cover(self, coordinator, mock_hass, mock_storage) -> None:
        raw = self._raw()
        mock_storage._data = {"covers": {"cover.t": raw}}
        mock_storage.get_cover_raw.side_effect = lambda e: mock_storage._data["covers"].get(e)
        coordinator._wind_protected = True
        coordinator._cover_states = {"cover.t": CoverStatus.LOCKED}
        mock_hass.states.get.side_effect = (
            lambda e: MockState("off") if e.startswith("binary") else MockState("open", {"current_position": 100}))
        with patch.object(coordinator, "_send_wind_position") as send_one, \
             patch.object(coordinator, "_activate_wind_protection") as send_all:
            coordinator._handle_contact_sensor_change("binary_sensor.w", ["cover.t"], [], MockState("on"), MockState("off"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.WIND_PROTECTED
        send_one.assert_called_once_with("cover.t")
        send_all.assert_not_called()

    def test_unknown_window_state_keeps_lock(self, coordinator, mock_hass, mock_storage) -> None:
        raw = self._raw()
        mock_storage._data = {"covers": {"cover.t": raw}}
        mock_storage.get_cover_raw.side_effect = lambda e: mock_storage._data["covers"].get(e)
        coordinator._wind_protected = True
        coordinator._cover_states = {"cover.t": CoverStatus.LOCKED}
        mock_hass.states.get.side_effect = (
            lambda e: MockState("unavailable") if e.startswith("binary") else MockState("open", {"current_position": 100}))
        with patch.object(coordinator, "_check_wind_protection"), \
             patch.object(coordinator, "_send_wind_position") as send_one:
            coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        send_one.assert_not_called()

    def test_activation_with_open_window_locks_that_cover(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage._data = {"covers": {"cover.t": self._raw(), "cover.u": {"auto_enabled": True, "inverted": False}}}
        mock_storage.get_cover_raw.side_effect = lambda e: mock_storage._data["covers"].get(e)
        mock_hass.states.get.side_effect = (
            lambda e: MockState("on") if e.startswith("binary") else MockState("closed", {"current_position": 0}))
        with patch.object(coordinator, "_send_staggered_commands") as staggered:
            coordinator._activate_wind_protection()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        assert coordinator._cover_states["cover.u"] == CoverStatus.WIND_PROTECTED
        cmds = staggered.call_args[0][0]
        assert [c[0] for c in cmds] == ["cover.u"]

    def test_tilted_window_does_not_override_wind(self, coordinator, mock_hass, mock_storage) -> None:
        raw = {"auto_enabled": True, "vent_sensor": "binary_sensor.v", "vent_position": 30, "inverted": False}
        mock_storage.get_cover_raw.return_value = raw
        coordinator._wind_protected = True
        coordinator._cover_states = {"cover.t": CoverStatus.WIND_PROTECTED}
        mock_hass.states.get.side_effect = (
            lambda e: MockState("on") if e.startswith("binary") else MockState("closed", {"current_position": 0}))
        coordinator._handle_contact_sensor_change("binary_sensor.v", [], ["cover.t"], MockState("off"), MockState("on"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.WIND_PROTECTED

    def test_manual_during_wind_no_broadcast(self, coordinator, mock_storage) -> None:
        coordinator._wind_protected = True
        coordinator._cover_states = {"cover.t": CoverStatus.WIND_PROTECTED}
        coordinator.set_cover_manual("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.WIND_PROTECTED

"""Coordinator tests: safety rules, wind position, threshold tracking, logs."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from custom_components.cover_automatic.engine import RuleEngine
from custom_components.cover_automatic.models import (
    Condition,
    ConditionType,
    CoverConfig,
    CoverStatus,
    Rule,
)
from tests.test_coordinator import (  # noqa: F401 -- pytest fixtures
    MockState,
    coordinator,
    mock_hass,
    mock_storage,
)

COVER = "cover.test"
STORM = "binary_sensor.storm"


def _storm_rule(**extra) -> Rule:
    return Rule(
        id="storm", name="Storm", priority=5, cover_ids=[COVER], target_position=0,
        conditions=[Condition(type=ConditionType.STATE_IS, params={"entity_id": STORM, "state": "on"})],
        safety=True, **extra,
    )


def _setup(coordinator, mock_hass, mock_storage, *, rules, auto_enabled=True, position=50,
           storm="on", inverted=False) -> dict:
    raw = {
        "entity_id": COVER, "name": "Test", "auto_enabled": auto_enabled, "inverted": inverted,
        "lock_sensor": None, "vent_sensor": None, "min_position_change": 5,
        "min_time_between_changes": 300, "pause_until": None,
        # Recent change: the time hysteresis would block a normal rule
        "last_position_change": time.time() - 10,
    }
    mock_storage._data = {"covers": {COVER: raw}, "rules": {}, "facades": {}, "scenarios": {}}
    mock_storage.covers = {COVER: CoverConfig.from_dict(raw)}
    mock_storage.rules = {r.id: r for r in rules}
    mock_storage.scenarios = {}
    mock_storage.enabled = True
    mock_storage.solar_sensor = None
    mock_storage.workday_sensor = None
    mock_storage.wind_position = 100
    mock_storage.logbook_enabled = False
    mock_storage.get_cover_raw = MagicMock(side_effect=lambda eid: mock_storage._data["covers"].get(eid))
    states = {
        COVER: MockState("open", {"current_position": position}),
        STORM: MockState(storm),
    }
    mock_hass.states.get = MagicMock(side_effect=states.get)
    coordinator.engine = RuleEngine(mock_hass, mock_storage)
    coordinator._states = states
    return raw


def _position_calls(mock_hass) -> list[int]:
    return [
        c.args[2]["position"] for c in mock_hass.services.async_call.call_args_list
        if c.args[1] == "set_cover_position"
    ]


class TestSafetyRule:
    @pytest.mark.asyncio
    async def test_paused_cover_driven_then_pause_cancelled(self, coordinator, mock_hass, mock_storage) -> None:
        raw = _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()])
        raw["pause_until"] = time.time() + 3600
        coordinator._cover_states[COVER] = CoverStatus.PAUSED

        await coordinator._async_update_data()

        assert coordinator.data["covers"][COVER]["safety"] is True
        assert _position_calls(mock_hass) == [0]
        assert coordinator._cover_states[COVER] == CoverStatus.PAUSED
        assert coordinator._safety_holds == {COVER: "storm"}

        # Storm over: the pause is cancelled, cover back to AUTO
        coordinator._states[STORM] = MockState("off")
        coordinator._states[COVER] = MockState("open", {"current_position": 0})
        await coordinator._async_update_data()
        assert coordinator._cover_states[COVER] == CoverStatus.AUTO
        mock_storage.update_cover_status.assert_called_with(COVER, "auto", None)
        assert coordinator._safety_holds == {}

    @pytest.mark.asyncio
    async def test_manual_cover_driven_and_stays_manual(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()], auto_enabled=False)
        await coordinator._async_update_data()
        assert _position_calls(mock_hass) == [0]

        coordinator._states[STORM] = MockState("off")
        await coordinator._async_update_data()
        assert coordinator._cover_states[COVER] == CoverStatus.MANUAL
        assert _position_calls(mock_hass) == [0]  # no further command

    @pytest.mark.asyncio
    async def test_global_automation_disabled(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()])
        mock_storage.enabled = False
        await coordinator._async_update_data()
        assert _position_calls(mock_hass) == [0]

    @pytest.mark.asyncio
    async def test_locked_cover_not_overridden(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()])
        coordinator._cover_states[COVER] = CoverStatus.LOCKED
        with patch.object(coordinator, "_sync_cover_statuses"):
            await coordinator._async_update_data()
        assert coordinator.data["covers"][COVER]["target_position"] is None
        assert _position_calls(mock_hass) == []

    @pytest.mark.asyncio
    async def test_normal_rule_ignored_for_paused_cover(self, coordinator, mock_hass, mock_storage) -> None:
        raw = _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule(enabled=True)])
        mock_storage.rules["storm"].safety = False
        raw["pause_until"] = time.time() + 3600
        coordinator._cover_states[COVER] = CoverStatus.PAUSED
        await coordinator._async_update_data()
        assert _position_calls(mock_hass) == []

    @pytest.mark.asyncio
    async def test_higher_priority_normal_rule_wins_for_auto(self, coordinator, mock_hass, mock_storage) -> None:
        high = Rule(id="high", name="High", priority=50, cover_ids=[COVER], target_position=80)
        raw = _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule(), high])
        raw["last_position_change"] = None
        await coordinator._async_update_data()
        assert coordinator.data["covers"][COVER]["matching_rule_id"] == "high"
        assert coordinator.data["covers"][COVER]["safety"] is False
        assert _position_calls(mock_hass) == [80]

    @pytest.mark.asyncio
    async def test_startup_grace_not_bypassed(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()], auto_enabled=False)
        coordinator._startup_time = time.monotonic()
        await coordinator._async_update_data()
        assert _position_calls(mock_hass) == []
        assert coordinator._safety_holds == {}

    @pytest.mark.asyncio
    async def test_small_change_sent_once(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()], position=23)
        mock_storage.rules["storm"].target_position = 20
        await coordinator._async_update_data()
        assert _position_calls(mock_hass) == [20]
        # Motor settled 3% short: not re-commanded every cycle
        coordinator._pending_settle.discard(COVER)
        coordinator._last_command_time[COVER] = 0
        await coordinator._async_update_data()
        assert _position_calls(mock_hass) == [20]

    def test_no_pause_while_safety_drives(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()])
        coordinator._safety_holds[COVER] = "storm"
        coordinator._last_positions[COVER] = 0
        with patch.object(coordinator, "pause_cover") as pause:
            coordinator._handle_cover_state_change(
                COVER, None, MockState("open", {"current_position": 60})
            )
        pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_takeover_and_release_logged(self, coordinator, mock_hass, mock_storage, caplog) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()], auto_enabled=False)
        coordinator.log_storage = MagicMock()
        with caplog.at_level(logging.DEBUG):
            await coordinator._async_update_data()
            await coordinator._async_update_data()
            coordinator._states[STORM] = MockState("off")
            await coordinator._async_update_data()
        assert sum("takes over" in r.message for r in caplog.records) == 1
        assert sum("released" in r.message for r in caplog.records) == 1
        keys = [c.args[3].get("key") for c in coordinator.log_storage.add_entry.call_args_list]
        assert "safety_takeover" in keys and "safety_release" in keys

    def test_wind_release_reapplies_wind_position(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(coordinator, mock_hass, mock_storage, rules=[_storm_rule()])
        mock_storage.wind_position = 70
        coordinator._wind_protected = True
        coordinator._cover_states[COVER] = CoverStatus.WIND_PROTECTED
        coordinator._safety_holds[COVER] = "storm"
        coordinator._update_safety_hold(COVER, None, CoverStatus.WIND_PROTECTED)
        assert coordinator._last_positions[COVER] == 70
        assert coordinator._cover_states[COVER] == CoverStatus.WIND_PROTECTED


class TestWindPosition:
    def _setup_wind(self, coordinator, mock_storage, mock_hass, *, inverted=False) -> None:
        mock_storage.wind_sensor = "sensor.wind"
        mock_storage.wind_speed_threshold = 50.0
        mock_storage.wind_speed_hysteresis = 10.0
        raw = {"entity_id": COVER, "auto_enabled": True, "inverted": inverted,
               "lock_sensor": None, "vent_sensor": None}
        mock_storage._data["covers"] = {COVER: raw}
        mock_storage.get_cover_raw.return_value = raw
        mock_hass.states.get.return_value = MockState("60", {"current_position": 50})

    @pytest.mark.parametrize(("inverted", "expected"), [(False, 30), (True, 70)])
    def test_wind_uses_setting(self, coordinator, mock_storage, mock_hass, inverted, expected) -> None:
        self._setup_wind(coordinator, mock_storage, mock_hass, inverted=inverted)
        mock_storage.wind_position = 30
        coordinator._check_wind_protection()
        assert coordinator._last_positions[COVER] == expected

    def test_invalid_setting_defaults_to_open(self, coordinator, mock_storage, mock_hass) -> None:
        self._setup_wind(coordinator, mock_storage, mock_hass)
        mock_storage.wind_position = MagicMock()
        coordinator._check_wind_protection()
        assert coordinator._last_positions[COVER] == 100

    def test_safety_held_cover_not_moved(self, coordinator, mock_storage, mock_hass) -> None:
        self._setup_wind(coordinator, mock_storage, mock_hass)
        coordinator._safety_holds[COVER] = "storm"
        coordinator._check_wind_protection()
        assert coordinator._cover_states[COVER] == CoverStatus.WIND_PROTECTED
        assert COVER not in coordinator._last_positions

    def test_unavailable_wind_sensor_warned_once(self, coordinator, mock_storage, mock_hass, caplog) -> None:
        self._setup_wind(coordinator, mock_storage, mock_hass)
        coordinator._wind_protected = True
        mock_hass.states.get.return_value = MockState("unavailable")
        with caplog.at_level(logging.WARNING):
            for _ in range(3):
                coordinator._check_wind_protection()
        assert sum("Wind sensor unavailable" in r.message for r in caplog.records) == 1


class TestThresholdTracking:
    def test_threshold_entities_tracked(self, coordinator, mock_storage) -> None:
        mock_storage._data = {
            "covers": {COVER: {"comfort_temp_min_entity": "input_number.cmin"}}, "rules": {},
        }
        mock_storage.comfort_temp_min_entity = None
        mock_storage.comfort_temp_max_entity = "input_number.gmax"
        mock_storage.solar_threshold_entity = "number.solar"
        coordinator.engine = MagicMock()
        coordinator.engine.ha_condition_entities.return_value = set()
        with patch(
            "custom_components.cover_automatic.coordinator.async_track_state_change_event"
        ) as track:
            coordinator._setup_state_tracking()
        tracked = set(track.call_args.args[1])
        assert {"input_number.cmin", "input_number.gmax", "number.solar"} <= tracked


class TestRenameReferences:
    def test_runtime_references_follow(self, coordinator) -> None:
        coordinator._last_move_rule = {COVER: "old"}
        coordinator._last_matching_rules = {COVER: "old"}
        coordinator._safety_holds = {COVER: "old"}
        coordinator.data = {
            "covers": {COVER: {"matching_rule_id": "old"}},
            "active_rules": {"old": [COVER], "other": []},
        }
        coordinator.rename_rule_references("old", "new")
        assert coordinator._last_move_rule[COVER] == "new"
        assert coordinator._last_matching_rules[COVER] == "new"
        assert coordinator._safety_holds[COVER] == "new"
        assert coordinator.data["covers"][COVER]["matching_rule_id"] == "new"
        assert list(coordinator.data["active_rules"]) == ["new", "other"]


class TestTransitionLogs:
    def _setup(self, mock_hass, mock_storage, raw, states) -> None:
        mock_storage._data = {"covers": {COVER: raw}, "rules": {}}
        mock_storage.get_cover_raw = MagicMock(return_value=raw)
        mock_hass.states.get = MagicMock(
            side_effect=lambda eid: MockState(states[eid], {"current_position": 60}) if eid in states else None
        )

    def test_hold_lock_logged_once(self, coordinator, mock_hass, mock_storage, caplog) -> None:
        raw = {"auto_enabled": True, "lock_sensor": "binary_sensor.window", "lock_position": 100,
               "vent_sensor": None, "inverted": False, "lock_hold_position": True}
        self._setup(mock_hass, mock_storage, raw, {"binary_sensor.window": "on", COVER: "open"})
        coordinator.log_storage = MagicMock()
        with caplog.at_level(logging.DEBUG):
            coordinator._sync_cover_statuses()
            coordinator._sync_cover_statuses()
        assert coordinator._cover_states[COVER] == CoverStatus.LOCKED
        lines = [r.message for r in caplog.records if "locked" in r.message]
        assert len(lines) == 1 and "kept at 60%" in lines[0]
        entry = coordinator.log_storage.add_entry.call_args.args[3]
        assert entry["to"] == "locked" and entry["kept"] is True

    def test_sensor_unavailable_logged_once(self, coordinator, mock_hass, mock_storage, caplog) -> None:
        raw = {"auto_enabled": True, "lock_sensor": "binary_sensor.window", "lock_position": 100,
               "vent_sensor": None, "inverted": False}
        self._setup(mock_hass, mock_storage, raw, {"binary_sensor.window": "unavailable", COVER: "open"})
        coordinator._cover_states[COVER] = CoverStatus.LOCKED
        with caplog.at_level(logging.DEBUG):
            for _ in range(3):
                coordinator._sync_cover_statuses()
        assert coordinator._cover_states[COVER] == CoverStatus.LOCKED
        assert sum("(kept at" in r.message for r in caplog.records) == 1

    def test_pause_expiry_logged(self, coordinator, mock_hass, mock_storage, caplog) -> None:
        raw = {"auto_enabled": True, "lock_sensor": None, "vent_sensor": None,
               "pause_until": time.time() - 5}
        self._setup(mock_hass, mock_storage, raw, {COVER: "open"})
        coordinator._cover_states[COVER] = CoverStatus.PAUSED
        coordinator.log_storage = MagicMock()
        with caplog.at_level(logging.DEBUG):
            coordinator._sync_cover_statuses()
        assert coordinator._cover_states[COVER] == CoverStatus.AUTO
        assert any("Pause expired" in r.message for r in caplog.records)
        assert coordinator.log_storage.add_entry.call_args.args[3]["to"] == "auto"

    def test_unlock_logs_restored_status(self, coordinator, mock_hass, mock_storage, caplog) -> None:
        # MANUAL is restored only while the automation is still off
        raw = {"auto_enabled": False, "lock_sensor": "binary_sensor.window", "lock_position": 100,
               "vent_sensor": None, "inverted": False}
        self._setup(mock_hass, mock_storage, raw, {"binary_sensor.window": "off", COVER: "open"})
        coordinator._cover_states[COVER] = CoverStatus.LOCKED
        coordinator._pre_lock_states[COVER] = CoverStatus.MANUAL
        with caplog.at_level(logging.DEBUG):
            coordinator._sync_cover_statuses()
        assert coordinator._cover_states[COVER] == CoverStatus.MANUAL
        assert any("locked -> manual" in r.message for r in caplog.records)

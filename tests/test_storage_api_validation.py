"""Storage and API validation: cross checks, invalid data, migrations, import, rule ordering."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations
import logging
import pytest
from custom_components.cover_automatic.api import ws_settings_update
from custom_components.cover_automatic.models import ConditionType, CoverConfig, Rule, Scenario
from custom_components.cover_automatic.storage import _ALL_MIGRATIONS, settings_cross_error, MIGRATION_PAUSE_DURATION_120, resolve_active_scenario
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_engine import engine, mock_hass, mock_storage, MockState  # noqa: F401
from tests.test_storage import mock_store, storage  # noqa: F401
from tests.test_storage_api_robustness import _base_config, _invalid, _valid
from unittest.mock import MagicMock, patch
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401


class TestSettingsCrossChecks:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("fields", [{"enabled": False}, {"comfort_temp_min": 20}])
    async def test_legacy_invalid_pair_does_not_block_other_settings(self, fields) -> None:
        # solar_hysteresis >= solar_threshold was accepted before
        storage = _make_storage(solar_threshold=100.0, solar_hysteresis=150.0)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, **fields},
                                 storage, _make_coordinator())
        conn.send_error.assert_not_called()
        conn.send_result.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field", ["solar_threshold", "solar_hysteresis"])
    async def test_changing_a_related_field_is_still_checked(self, field) -> None:
        storage = _make_storage(solar_threshold=100.0, solar_hysteresis=150.0)
        conn = _make_connection()
        value = 120 if field == "solar_threshold" else 140
        await ws_settings_update(_make_hass(), conn, {"id": 1, field: value},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_solar_hysteresis"
        storage.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fixing_the_pair_is_accepted(self) -> None:
        storage = _make_storage(solar_threshold=100.0, solar_hysteresis=150.0)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, "solar_hysteresis": 20},
                                 storage, _make_coordinator())
        conn.send_error.assert_not_called()
        assert storage.solar_hysteresis == 20

    def test_helper_without_changed_runs_all_checks(self) -> None:
        values = {"comfort_temp_min": 21, "comfort_temp_max": 25, "comfort_temp_min_b": 22,
                  "comfort_temp_max_b": 24, "wind_speed_threshold": 0,
                  "wind_speed_hysteresis": 0, "solar_threshold": 100, "solar_hysteresis": 150}
        assert settings_cross_error(values.get)[0] == "invalid_solar_hysteresis"
        assert settings_cross_error(values.get, {"enabled"}) is None
        assert settings_cross_error(values.get, {"solar_threshold"})[0] == "invalid_solar_hysteresis"


def _rule(conditions, **extra) -> dict:
    return {"id": "r", "name": "Night", "cover_ids": ["cover.a"], "conditions": conditions,
            "scenario_ids": ["everyday"], **extra}


BAD_CONDITIONS = [
    {"type": "temperature_above", "params": {"temperature": "nan"}},
    {"type": "no_such_type", "params": {}},
    {"params": {}},
    "not a dict",
]


class TestInvalidConditionDisablesRule:
    @pytest.mark.parametrize("bad", BAD_CONDITIONS)
    def test_from_dict_disables_and_warns(self, bad, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            rule = Rule.from_dict(_rule([bad]))
        assert rule.enabled is False
        assert rule.conditions == []
        assert "Night" in caplog.text and "disabled" in caplog.text

    def test_partial_loss_also_disables(self) -> None:
        good = {"type": "time_after_sunset", "params": {"offset": 0}}
        rule = Rule.from_dict(_rule([good, BAD_CONDITIONS[0]]))
        assert rule.enabled is False
        assert [c.type for c in rule.conditions] == [ConditionType.TIME_AFTER_SUNSET]

    def test_rule_without_conditions_stays_enabled(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            assert Rule.from_dict(_rule([])).enabled is True
            assert Rule.from_dict({"id": "r", "name": "N"}).enabled is True
        assert "disabled" not in caplog.text

    def test_valid_conditions_stay_enabled(self) -> None:
        rule = Rule.from_dict(_rule([{"type": "time_after_sunset", "params": {"offset": 15}}]))
        assert rule.enabled is True

    @pytest.mark.asyncio
    async def test_storage_load_disables_and_persists(self, storage, mock_store) -> None:
        data = _base_config()
        data["rules"] = {"r": _rule([BAD_CONDITIONS[1]])}
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage.rules["r"].enabled is False
        # the raw store is consistent (and a save is scheduled)
        assert storage._data["rules"]["r"]["enabled"] is False
        mock_store.async_delay_save.assert_called()

    @pytest.mark.asyncio
    async def test_storage_load_keeps_rule_without_conditions(self, storage, mock_store) -> None:
        data = _base_config()
        data["rules"] = {"r": _rule([])}
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage.rules["r"].enabled is True

    @pytest.mark.asyncio
    async def test_import_disables(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["rules"] = {"r": _rule([BAD_CONDITIONS[0]])}
        await storage.async_import_data(data)
        assert "r" in storage.rules
        assert storage.rules["r"].enabled is False
        assert storage._data["rules"]["r"]["enabled"] is False


class TestMeasuredTravelExport:
    @pytest.mark.asyncio
    async def test_exported(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_measured_travel("cover.a", 23.5)
        cover = storage.get_export_data()["covers"]["cover.a"]
        assert cover["measured_travel_time"] == 23.5
        for key in ("status", "pause_until", "last_position_change"):
            assert key not in cover

    @pytest.mark.asyncio
    async def test_import_keeps_local_value_for_existing_cover(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_measured_travel("cover.a", 23.5)
        data = _base_config()
        data["covers"]["cover.a"]["measured_travel_time"] = 99.0
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].measured_travel_time == 23.5

    @pytest.mark.asyncio
    async def test_import_existing_cover_without_learned_value_stays_none(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        data = _base_config()
        data["covers"]["cover.a"]["measured_travel_time"] = 99.0
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].measured_travel_time is None

    @pytest.mark.asyncio
    async def test_import_takes_file_value_for_new_cover(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"].update(measured_travel_time=31.0, status="paused",
                                         pause_until=123.0, last_position_change=5.0)
        await storage.async_import_data(data)
        cover = storage.covers["cover.a"]
        assert cover.measured_travel_time == 31.0
        # runtime state is still never taken from the file
        assert cover.status.value == "auto"
        assert cover.pause_until is None
        assert cover.last_position_change is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [0, -5, "nan", "x"])
    async def test_import_unusable_value_for_new_cover(self, storage, bad) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"]["measured_travel_time"] = bad
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].measured_travel_time is None

    @pytest.mark.asyncio
    async def test_round_trip(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_measured_travel("cover.a", 18.0)
        exported = storage.get_export_data()
        # fresh installation
        storage._data = {}
        storage._invalidate_cache()
        await storage.async_import_data(exported)
        assert storage.covers["cover.a"].measured_travel_time == 18.0


class TestAzimuthNormalized:
    @pytest.mark.parametrize("command", ["facade/add", "facade/update"])
    @pytest.mark.parametrize(("raw", "expected"), [
        (-90, 270.0), (-1, 359.0), (400, 40.0), (720, 0.0), (360, 0.0), (0, 0.0),
        (180.5, 180.5), ("450", 90.0), (-0.0, 0.0), (-1e-20, 0.0),
    ])
    def test_normalized(self, command, raw, expected) -> None:
        key = {"name": "F"} if command == "facade/add" else {"facade_id": "f"}
        msg = _valid(command, **key, azimuth_start=raw, azimuth_end=raw)
        assert msg["azimuth_start"] == expected
        assert msg["azimuth_end"] == expected
        assert 0 <= msg["azimuth_start"] < 360

    @pytest.mark.parametrize("bad", ["nan", "inf", "-inf", True, "x", None])
    def test_non_finite_rejected(self, bad) -> None:
        _invalid("facade/add", name="F", azimuth_start=bad)

    def test_start_equals_end_full_circle(self) -> None:
        msg = _valid("facade/add", name="F", azimuth_start=0, azimuth_end=360)
        assert msg["azimuth_start"] == msg["azimuth_end"] == 0.0

    @pytest.mark.parametrize("command", ["facade/add", "facade/update"])
    def test_min_elevation_still_bounded(self, command) -> None:
        key = {"name": "F"} if command == "facade/add" else {"facade_id": "f"}
        _invalid(command, **key, min_elevation=400)


class TestPauseDurationZero:
    def test_model_normalizes(self) -> None:
        assert CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                      "pause_duration": 0}).pause_duration == 1
        assert CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                      "pause_duration": None}).pause_duration is None
        assert CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                      "pause_duration": 45}).pause_duration == 45

    @pytest.mark.asyncio
    async def test_storage_load_normalizes_raw(self, storage, mock_store) -> None:
        data = _base_config()
        data["covers"]["cover.a"]["pause_duration"] = 0
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage.covers["cover.a"].pause_duration == 1
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 1
        mock_store.async_delay_save.assert_called()

    @pytest.mark.asyncio
    async def test_storage_load_leaves_valid_data_untouched(self, storage, mock_store) -> None:
        data = _base_config()
        data["covers"]["cover.a"]["pause_duration"] = 30
        data["migrations"] = list(_ALL_MIGRATIONS)
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 30
        mock_store.async_delay_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_normalizes(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"]["pause_duration"] = 0
        await storage.async_import_data(data)
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 1
        assert storage.covers["cover.a"].pause_duration == 1


COVER = CoverConfig(entity_id="cover.a", name="A", facade_id="south")


class TestRemoveLastAssignment:
    @pytest.mark.asyncio
    async def test_remove_last_cover_disables_rule(self, storage) -> None:
        storage._data = {
            "covers": {"cover.a": {"entity_id": "cover.a", "name": "A"}},
            "facades": {},
            "rules": {
                "r1": {"id": "r1", "name": "R1", "enabled": True, "cover_ids": ["cover.a"],
                       "facade_ids": [], "conditions": [{"type": "workday"}]},
                "r2": {"id": "r2", "name": "R2", "enabled": True, "cover_ids": ["cover.a", "cover.b"],
                       "facade_ids": [], "conditions": []},
                "g": {"id": "g", "name": "G", "enabled": True, "cover_ids": [],
                      "facade_ids": [], "conditions": [{"type": "workday"}]},
            },
            "scenarios": {},
        }
        await storage.async_remove_cover("cover.a")
        assert storage._data["rules"]["r1"]["enabled"] is False
        assert storage._data["rules"]["r2"]["enabled"] is True
        # Global from the start: untouched
        assert storage._data["rules"]["g"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_remove_last_facade_disables_rule(self, storage) -> None:
        storage._data = {
            "covers": {},
            "facades": {"south": {"id": "south", "name": "S", "azimuth_start": 90, "azimuth_end": 270}},
            "rules": {
                "r1": {"id": "r1", "name": "R1", "enabled": True, "cover_ids": [],
                       "facade_ids": ["south"], "conditions": [{"type": "workday"}]},
                "r2": {"id": "r2", "name": "R2", "enabled": True, "cover_ids": ["cover.x"],
                       "facade_ids": ["south"], "conditions": []},
            },
            "scenarios": {},
        }
        await storage.async_remove_facade("south")
        assert storage.rules["r1"].enabled is False
        assert storage.rules["r2"].enabled is True


class TestActiveScenario:
    def test_resolve_helper(self) -> None:
        assert resolve_active_scenario("night", {"day": 1, "night": 2}) == "night"
        assert resolve_active_scenario("", {"day": 1, "night": 2}) == "day"
        assert resolve_active_scenario("gone", {"day": 1}) == "day"
        assert resolve_active_scenario("", {}) == "everyday"

    def test_storage_property(self, storage) -> None:
        storage._data = {"scenarios": {"day": {}, "night": {}}, "active_scenario": ""}
        assert storage.effective_active_scenario == "day"

    def test_engine_uses_first_scenario(self, engine, mock_storage) -> None:
        mock_storage.active_scenario = ""
        mock_storage.scenarios = {
            "day": Scenario(id="day", name="Day", rules_disabled=["r1"]),
            "night": Scenario(id="night", name="Night"),
        }
        mock_storage.rules = {
            "r1": Rule(id="r1", name="R1", cover_ids=["cover.a"], target_position=40),
        }
        # Previously an unknown scenario activated every rule
        assert engine.evaluate_cover(COVER) is None

    @pytest.mark.asyncio
    async def test_api_rejects_empty_scenario(self) -> None:
        from custom_components.cover_automatic.api import ws_settings_update

        conn = _make_connection()
        storage = _make_storage()
        storage._data["scenarios"] = {"day": {"name": "Day"}}
        msg = {"id": 1, "type": "cover_automatic/settings/update", "active_scenario": ""}
        await ws_settings_update(_make_hass(), conn, msg, storage, _make_coordinator())
        assert conn.send_error.call_args[0][1] == "not_found"


class TestPauseMigration:
    @pytest.mark.asyncio
    async def test_runs_once_and_is_persisted(self, storage, mock_store) -> None:
        data = {
            "covers": {"cover.a": {"entity_id": "cover.a", "name": "A", "pause_duration": 120}},
            "rules": {}, "scenarios": {}, "facades": {},
        }
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage._data["covers"]["cover.a"]["pause_duration"] is None
        assert MIGRATION_PAUSE_DURATION_120 in storage._data["migrations"]
        mock_store.async_delay_save.assert_called()

        # A deliberate 120 set later survives the next load
        storage._data["covers"]["cover.a"]["pause_duration"] = 120
        mock_store.async_load.return_value = storage._data
        mock_store.async_delay_save.reset_mock()
        await storage.async_load()
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 120
        mock_store.async_delay_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_install_has_marker(self, storage, mock_store) -> None:
        mock_store.async_load.return_value = None
        await storage.async_load()
        assert storage._data["migrations"] == list(_ALL_MIGRATIONS)
        assert MIGRATION_PAUSE_DURATION_120 in storage._data["migrations"]

    @pytest.mark.asyncio
    async def test_import_keeps_marker(self, storage, mock_store) -> None:
        mock_store.async_load.return_value = None
        await storage.async_load()
        # A file already migrated keeps its deliberate 120 ...
        await storage.async_import_data({
            "covers": {"cover.a": {"entity_id": "cover.a", "name": "A", "pause_duration": 120}},
            "migrations": [MIGRATION_PAUSE_DURATION_120],
        })
        assert MIGRATION_PAUSE_DURATION_120 in storage._data["migrations"]
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 120
        # ... while a file without the marker gets the migration replayed
        await storage.async_import_data({
            "covers": {"cover.a": {"entity_id": "cover.a", "name": "A", "pause_duration": 120}},
        })
        assert MIGRATION_PAUSE_DURATION_120 in storage._data["migrations"]
        assert storage._data["covers"]["cover.a"]["pause_duration"] is None


class TestImportRobustness:
    def test_rule_coercion(self) -> None:
        rule = Rule.from_dict({
            "id": "r", "name": "R", "priority": "10", "target_position": "150",
            "target_tilt_position": "abc",
        })
        assert rule.priority == 10
        assert rule.target_position == 100
        assert rule.target_tilt_position is None
        assert Rule.from_dict({"id": "r", "name": "R", "priority": None}).priority == 10
        assert Rule.from_dict({"id": "r", "name": "R", "target_position": -5}).target_position == 0

    def test_cover_coercion(self) -> None:
        cover = CoverConfig.from_dict({
            "entity_id": "cover.a", "name": "A", "lock_position": "120",
            "vent_position": "x", "min_position_change": "5", "pause_duration": "30",
            "comfort_temp_min": "bad",
        })
        assert cover.lock_position == 100
        assert cover.vent_position is None
        assert cover.min_position_change == 5
        assert cover.pause_duration == 30
        assert cover.comfort_temp_min is None

    @pytest.mark.asyncio
    async def test_import_rekeys_and_normalises(self, storage, engine, mock_storage) -> None:
        await storage.async_import_data({
            "covers": {"wrong": {"entity_id": "cover.a", "name": "A"}},
            "rules": {"x": {"id": "r1", "name": "R", "priority": "10", "target_position": "40",
                            "cover_ids": ["cover.a"]}},
            "scenarios": {"s": {"id": "everyday", "name": "E"}},
            "facades": {"f": {"id": "south", "name": "S", "azimuth_start": "90", "azimuth_end": 270}},
        })
        assert list(storage._data["covers"]) == ["cover.a"]
        assert list(storage._data["rules"]) == ["r1"]
        assert list(storage._data["scenarios"]) == ["everyday"]
        assert list(storage._data["facades"]) == ["south"]
        assert storage._data["rules"]["r1"]["priority"] == 10
        assert storage._data["rules"]["r1"]["target_position"] == 40
        assert storage._data["facades"]["south"]["azimuth_start"] == 90.0

        # A rule with "priority": "10" works in the engine
        mock_storage.rules = storage.rules
        mock_storage.scenarios = storage.scenarios
        target = engine.evaluate_cover(CoverConfig(entity_id="cover.a", name="A"))
        assert target is not None and target.position == 40


class TestRuleOrderingApi:
    @pytest.mark.asyncio
    async def test_new_rule_goes_to_bottom_with_own_priority(self) -> None:
        from custom_components.cover_automatic.api import ws_rule_add
        from tests.test_api import _real_rule_ordering

        storage = _make_storage()
        storage._data = {"rules": {"a": {"id": "a", "priority": 20}, "b": {"id": "b", "priority": 10}}}
        _real_rule_ordering(storage)

        async def add(rule, save=True):
            storage._data["rules"][rule.id] = rule.to_dict()
        storage.async_add_rule.side_effect = add
        await ws_rule_add(_make_hass(), _make_connection(), {"id": 1, "name": "Zz"}, storage, _make_coordinator())
        prios = {k: v["priority"] for k, v in storage._data["rules"].items()}
        assert prios == {"a": 30, "b": 20, "zz": 10}

    def test_rule_name_length_limited(self) -> None:
        import voluptuous as vol

        from custom_components.cover_automatic.api import _RULE_NAME
        _RULE_NAME("x" * 100)
        with pytest.raises(vol.Invalid):
            _RULE_NAME("x" * 101)

    @pytest.mark.asyncio
    async def test_duplicate_truncates_long_name(self) -> None:
        from unittest.mock import AsyncMock

        from custom_components.cover_automatic.api import ws_rule_duplicate
        storage = _make_storage(rules={"r": Rule(id="r", name="R")})
        storage.async_duplicate_rule = AsyncMock(return_value=True)
        await ws_rule_duplicate(_make_hass(), _make_connection(), {"id": 1, "rule_id": "r", "name": "y" * 150},
                                storage, _make_coordinator())
        assert len(storage.async_duplicate_rule.call_args[0][2]) <= 97


class TestUnloadedEntry:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("state_name", "refused"), [("NOT_LOADED", True), ("LOADED", False)])
    async def test_commands_refused_after_unload(self, state_name, refused) -> None:
        from homeassistant.config_entries import ConfigEntryState

        from custom_components.cover_automatic import api

        registered = {}
        coord = _make_coordinator()
        coord.config_entry = MagicMock(state=getattr(ConfigEntryState, state_name))
        with (
            patch.object(api.websocket_api, "async_response", lambda fn: fn),
            patch.object(api.websocket_api, "require_admin", lambda fn: fn),
            patch.object(api.websocket_api, "async_register_command",
                         side_effect=lambda h, ct, fn, schema=None: registered.__setitem__(ct, fn)),
            patch.object(api, "ws_get_config") as get_config,
        ):
            api.async_setup_api(MagicMock(), _make_storage(), coord)
            conn = _make_connection()
            await registered["cover_automatic/config"](MagicMock(), conn, {"id": 5})
        assert conn.send_error.called is refused
        assert get_config.called is not refused

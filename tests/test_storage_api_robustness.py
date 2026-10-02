"""Storage/API hardening (finite floats, import validation, refs, export)."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.cover_automatic.api import (
    _SETTINGS_FIELDS,
    _parse_conditions,
    async_setup_api,
    ws_facade_update,
    ws_import_config,
    ws_rule_add,
    ws_rule_update,
    ws_settings_update,
)
from custom_components.cover_automatic.models import (
    Condition,
    ConditionType,
    CoverConfig,
    Facade,
    Rule,
    Scenario,
    _str_list,
    finite_float,
)
from custom_components.cover_automatic.storage import (
    _ALL_MIGRATIONS,
    GLOBAL_SETTING_KEYS,
    MIGRATION_PAUSE_DURATION_120,
    MIGRATION_PREEMPTIVE_TRISTATE,
    SETTING_VALIDATORS,
)
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_storage import mock_hass, mock_store, storage  # noqa: F401 -- pytest fixtures


def _schemas() -> dict[str, vol.Schema]:
    """WS schemas as registered, keyed by command suffix."""
    from homeassistant.components import websocket_api as real_ws

    schemas: dict[str, vol.Schema] = {}
    with patch("custom_components.cover_automatic.api.websocket_api") as mock_ws:
        mock_ws.BASE_COMMAND_MESSAGE_SCHEMA = real_ws.BASE_COMMAND_MESSAGE_SCHEMA

        def capture(hass, command_type, handler=None, schema=None):
            schemas[command_type.split("/", 1)[1]] = schema

        mock_ws.async_register_command.side_effect = capture
        async_setup_api(_make_hass(), _make_storage(), _make_coordinator())
    return schemas


def _msg(command: str, **fields) -> dict:
    return {"id": 1, "type": f"cover_automatic/{command}", **fields}


def _valid(command: str, **fields) -> dict:
    return _schemas()[command](_msg(command, **fields))


def _invalid(command: str, **fields) -> None:
    with pytest.raises(vol.Invalid):
        _schemas()[command](_msg(command, **fields))


def _base_config() -> dict:
    return {
        "facades": {"south": {"id": "south", "name": "S", "azimuth_start": 135, "azimuth_end": 225,
                              "cover_ids": ["cover.a"]}},
        "covers": {"cover.a": {"entity_id": "cover.a", "name": "A", "facade_id": "south"}},
        "rules": {"r1": {"id": "r1", "name": "R1", "cover_ids": ["cover.a"],
                         "scenario_ids": ["everyday"]}},
        "scenarios": {"everyday": {"id": "everyday", "name": "E"}},
        "active_scenario": "everyday",
        "migrations": list(_ALL_MIGRATIONS),
    }


# ---------------------------------------------------------------------------
# 1. Non-finite floats
# ---------------------------------------------------------------------------

class TestFiniteFloats:
    @pytest.mark.parametrize("bad", ["nan", "NaN", "inf", "-inf", float("nan"), float("inf"), True, "x"])
    def test_finite_float_rejects(self, bad) -> None:
        with pytest.raises(vol.Invalid):
            finite_float(bad)

    def test_finite_float_accepts_numbers(self) -> None:
        assert finite_float("12.5") == 12.5
        assert finite_float(3) == 3.0

    @pytest.mark.parametrize("command", ["facade/add", "facade/update"])
    @pytest.mark.parametrize("field", ["azimuth_start", "azimuth_end", "min_elevation"])
    @pytest.mark.parametrize("bad", ["nan", "inf"])
    def test_facade_schema_rejects(self, command, field, bad) -> None:
        key = {"name": "F"} if command == "facade/add" else {"facade_id": "f"}
        _invalid(command, **key, **{field: bad})

    def test_negative_azimuth_normalized(self) -> None:
        # Out-of-range bearings are normalised (% 360)
        assert _valid("facade/add", name="F", azimuth_start=-1)["azimuth_start"] == 359.0

    def test_facade_schema_accepts_360(self) -> None:
        msg = _valid("facade/add", name="F", azimuth_start=0, azimuth_end=360)
        assert msg["azimuth_end"] == 0.0

    def test_settings_schema_rejects_non_finite(self) -> None:
        for key in ("comfort_temp_min", "comfort_temp_max", "wind_speed_threshold",
                    "wind_speed_hysteresis", "solar_threshold", "solar_hysteresis",
                    "house_rotation", "command_stagger", "comfort_hysteresis",
                    "threshold_hysteresis"):
            _invalid("settings/update", **{key: "nan"})
            _invalid("settings/update", **{key: "inf"})

    def test_settings_schema_bounds(self) -> None:
        _invalid("settings/update", comfort_temp_min=1000)
        _invalid("settings/update", pause_duration="inf")
        assert _valid("settings/update", comfort_temp_min="20.5")["comfort_temp_min"] == 20.5

    def test_cover_comfort_rejects_nan(self) -> None:
        _invalid("cover/update", entity_id="cover.a", comfort_temp_min="nan")
        _invalid("cover/update", entity_id="cover.a", comfort_temp_max=float("inf"))
        assert _valid("cover/update", entity_id="cover.a", comfort_temp_min=None)["comfort_temp_min"] is None

    def test_facade_from_dict_rejects_non_finite_azimuth(self) -> None:
        for bad in (None, float("nan"), float("inf"), "nan", "abc"):
            with pytest.raises(ValueError):
                Facade.from_dict({"id": "f", "name": "F", "azimuth_start": bad, "azimuth_end": 90})

    def test_facade_from_dict_replaces_bad_elevation(self) -> None:
        facade = Facade.from_dict({"id": "f", "name": "F", "azimuth_start": 360,
                                   "azimuth_end": 90, "min_elevation": float("nan")})
        assert facade.min_elevation == 0.0
        assert facade.azimuth_start == 0.0

    def test_condition_rejects_non_finite_param(self) -> None:
        for key in ("value", "elevation", "temperature", "hysteresis", "delta", "offset"):
            with pytest.raises(ValueError):
                Condition.from_dict({"type": "numeric_state", "params": {key: "nan"}})
        cond = Condition.from_dict({"type": "numeric_state", "params": {"value": "12"}})
        assert cond.params["value"] == "12"
        _, errors = _parse_conditions([{"type": "temperature_above", "params": {"value": float("inf")}}])
        assert errors

    def test_storage_skips_corrupted_entries(self, storage, caplog) -> None:
        # orjson writes NaN as null: the reloaded facade has azimuth None
        storage._data = {
            "facades": {
                "bad": {"id": "bad", "name": "B", "azimuth_start": None, "azimuth_end": 90},
                "good": {"id": "good", "name": "G", "azimuth_start": 90, "azimuth_end": 180},
            },
            "covers": {"cover.x": {"name": "no entity id"},
                       "cover.a": {"entity_id": "cover.a", "name": "A"}},
            "rules": {"bad": {"name": "no id"}, "r": {"id": "r", "name": "R"}},
            "scenarios": {"bad": "text", "s": {"id": "s", "name": "S"}},
        }
        storage._invalidate_cache()
        assert list(storage.facades) == ["good"]
        assert list(storage.covers) == ["cover.a"]
        assert list(storage.rules) == ["r"]
        assert list(storage.scenarios) == ["s"]
        assert "corrupted facades entry 'bad'" in caplog.text
        # Export keeps working
        json.dumps(storage.get_export_data())


# ---------------------------------------------------------------------------
# 2. Entity fields of CoverConfig
# ---------------------------------------------------------------------------

class TestCoverEntityFields:
    def test_non_string_entities_become_none(self) -> None:
        cover = CoverConfig.from_dict({
            "entity_id": "cover.a", "name": "A", "lock_sensor": 5, "vent_sensor": ["x"],
            "indoor_temp_sensor": {"a": 1}, "facade_id": 3, "occupancy_sensor": "",
        })
        assert cover.lock_sensor is None
        assert cover.vent_sensor is None
        assert cover.indoor_temp_sensor is None
        assert cover.facade_id is None
        assert cover.occupancy_sensor is None

    def test_string_entities_kept(self) -> None:
        cover = CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                       "lock_sensor": "binary_sensor.w"})
        assert cover.lock_sensor == "binary_sensor.w"


# ---------------------------------------------------------------------------
# 3/4/15. Settings bounds and cross checks (import + WS)
# ---------------------------------------------------------------------------

class TestImportSettingsBounds:
    def test_validators_cover_every_setting(self) -> None:
        assert set(SETTING_VALIDATORS) == set(GLOBAL_SETTING_KEYS)
        assert set(SETTING_VALIDATORS) | {"active_scenario"} == set(_SETTINGS_FIELDS)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("key", "bad"), [
        ("comfort_temp_min", 1000), ("comfort_temp_max", "nan"), ("pause_duration", 0),
        ("pause_duration", 10000), ("house_rotation", 500), ("wind_position", 150),
        ("lock_position", -3), ("command_stagger", 9), ("comfort_hysteresis", 0),
        ("min_time_between_changes", 5), ("wind_speed_threshold", -1),
        ("outdoor_temp_sensor", "not an entity"), ("default_travel_time", 5000),
    ])
    async def test_out_of_range_keeps_local(self, storage, key, bad) -> None:
        await storage.async_load()
        before = getattr(storage, key)
        await storage.async_import_data({**_base_config(), key: bad})
        assert getattr(storage, key) == before

    @pytest.mark.asyncio
    async def test_valid_values_are_imported(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data({**_base_config(), "comfort_temp_min": "19",
                                         "pause_duration": "30", "outdoor_temp_sensor": "sensor.t"})
        assert storage.comfort_temp_min == 19.0
        assert storage.pause_duration == 30
        assert storage.outdoor_temp_sensor == "sensor.t"

    @pytest.mark.asyncio
    async def test_comfort_min_not_below_max_keeps_local(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data({**_base_config(), "comfort_temp_min": 26,
                                         "comfort_temp_max": 22})
        assert (storage.comfort_temp_min, storage.comfort_temp_max) == (21.0, 25.0)
        # Only one side imported, but conflicting with the local other side
        await storage.async_import_data({**_base_config(), "comfort_temp_min": 30})
        assert storage.comfort_temp_min < storage.comfort_temp_max

    @pytest.mark.asyncio
    async def test_wind_and_solar_hysteresis_checked(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data({
            **_base_config(), "wind_speed_threshold": 10, "wind_speed_hysteresis": 12,
            "solar_threshold": 200, "solar_hysteresis": 200,
        })
        assert storage.wind_speed_threshold == 0.0
        assert storage.wind_speed_hysteresis == 0.0
        assert storage.solar_threshold == 0.0
        assert storage.solar_hysteresis == 0.0
        await storage.async_import_data({
            **_base_config(), "wind_speed_threshold": 10, "wind_speed_hysteresis": 2,
            "solar_threshold": 200, "solar_hysteresis": 50,
        })
        assert (storage.wind_speed_threshold, storage.wind_speed_hysteresis) == (10.0, 2.0)
        assert (storage.solar_threshold, storage.solar_hysteresis) == (200.0, 50.0)


class TestSolarHysteresisWs:
    @pytest.mark.asyncio
    async def test_rejected_when_not_below_threshold(self) -> None:
        storage = _make_storage(solar_threshold=100.0)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, "solar_hysteresis": 100},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_solar_hysteresis"
        storage.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_allowed_without_threshold(self) -> None:
        storage = _make_storage(solar_threshold=0.0)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, "solar_hysteresis": 30},
                                 storage, _make_coordinator())
        conn.send_error.assert_not_called()

    @pytest.mark.asyncio
    async def test_existing_codes_unchanged(self) -> None:
        storage = _make_storage()
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, "comfort_temp_min": 30},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_comfort_range"
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn,
                                 {"id": 1, "wind_speed_threshold": 5, "wind_speed_hysteresis": 5},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_wind_hysteresis"


# ---------------------------------------------------------------------------
# 5. Import references and whitelist
# ---------------------------------------------------------------------------

class TestImportReferences:
    def test_str_list(self) -> None:
        assert _str_list("cover.a") == []
        assert _str_list(["a", 1, None, "", "a", "b"]) == ["a", "b"]
        assert _str_list(None) == []

    def test_models_do_not_split_strings(self) -> None:
        facade = Facade.from_dict({"id": "f", "name": "F", "azimuth_start": 0,
                                   "azimuth_end": 90, "cover_ids": "cover.a"})
        assert facade.cover_ids == []
        scenario = Scenario.from_dict({"id": "s", "name": "S", "rules_disabled": "r1"})
        assert scenario.rules_disabled == []
        rule = Rule.from_dict({"id": "r", "name": "R", "cover_ids": "cover.a"})
        assert rule.cover_ids == []
        assert rule.enabled is False  # never silently global
        assert Rule.from_dict({"id": "r", "name": "R", "scenario_ids": "s"}).scenario_ids is None
        assert Rule.from_dict({"id": "r", "name": "R"}).enabled is True

    @pytest.mark.asyncio
    async def test_unknown_ids_dropped_and_rules_disabled(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.b"] = {"entity_id": "cover.b", "name": "B", "facade_id": "ghost"}
        data["covers"]["light.x"] = {"entity_id": "light.x", "name": "not a cover"}
        data["facades"]["south"]["cover_ids"] = ["cover.b", "cover.zzz"]
        data["rules"]["r2"] = {"id": "r2", "name": "R2", "facade_ids": ["ghost"],
                               "cover_ids": ["cover.zzz"]}
        data["rules"]["r3"] = {"id": "r3", "name": "R3", "cover_ids": ["cover.a", "cover.zzz"],
                               "scenario_ids": ["everyday", "ghost"]}
        data["rules"]["r4"] = {"id": "r4", "name": "R4", "cover_ids": ["cover.a"],
                               "scenario_ids": ["ghost"]}
        data["rules"]["global"] = {"id": "global", "name": "G"}
        data["scenarios"]["everyday"]["rules_disabled"] = ["r3", "ghost"]
        await storage.async_import_data(data)

        assert set(storage.covers) == {"cover.a", "cover.b"}
        assert storage.covers["cover.b"].facade_id is None
        # Rebuilt from cover.facade_id
        assert storage.facades["south"].cover_ids == ["cover.a"]
        assert storage.rules["r2"].enabled is False
        assert storage.rules["r2"].cover_ids == [] and storage.rules["r2"].facade_ids == []
        assert storage.rules["r3"].enabled is True
        assert storage.rules["r3"].cover_ids == ["cover.a"]
        assert storage.rules["r3"].scenario_ids == ["everyday"]
        assert storage.rules["r4"].enabled is False
        assert storage.rules["r4"].scenario_ids == []
        assert storage.rules["global"].enabled is True  # was global in the file
        assert storage.scenarios["everyday"].rules_disabled == ["r3"]

    @pytest.mark.asyncio
    async def test_unknown_keys_and_runtime_fields_not_taken(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_status("cover.a", "paused", 1234.0)
        storage.update_cover_last_change("cover.a", 99.0)
        storage.update_cover_measured_travel("cover.a", 21.5)
        data = _base_config()
        data["covers"]["cover.a"].update({
            "status": "locked", "pause_until": 5.0, "last_position_change": 6.0,
            "measured_travel_time": 3.0,
        })
        data["evil"] = {"x": 1}
        data["wind_protected_state"] = True
        await storage.async_import_data(data)
        raw = storage._data["covers"]["cover.a"]
        assert raw["status"] == "paused"
        assert raw["pause_until"] == 1234.0
        assert raw["last_position_change"] == 99.0
        assert raw["measured_travel_time"] == 21.5
        assert "evil" not in storage._data
        assert "wind_protected_state" not in storage._data

    @pytest.mark.asyncio
    async def test_local_internal_state_survives_import(self, storage) -> None:
        await storage.async_load()
        storage._data["wind_protected_state"] = {"active": True}
        await storage.async_import_data({**_base_config(), "wind_protected_state": None})
        assert storage._data["wind_protected_state"] == {"active": True}

    @pytest.mark.asyncio
    async def test_new_cover_gets_auto_status(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"]["status"] = "locked"
        await storage.async_import_data(data)
        assert storage._data["covers"]["cover.a"]["status"] == "auto"


# ---------------------------------------------------------------------------
# 6. Coordinator reconciliation after import
# ---------------------------------------------------------------------------

class TestImportReconcile:
    @pytest.mark.asyncio
    async def test_reconcile_called(self) -> None:
        storage = _make_storage()
        storage.async_import_data = AsyncMock()
        coordinator = _make_coordinator()
        coordinator.reconcile_after_import = MagicMock()
        conn = _make_connection()
        await ws_import_config(_make_hass(), conn, {"id": 1, "data": {"covers": {}}},
                               storage, coordinator)
        coordinator.reconcile_after_import.assert_called_once_with()
        conn.send_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_coordinator_without_method(self) -> None:
        storage = _make_storage()
        storage.async_import_data = AsyncMock()
        coordinator = _make_coordinator()
        coordinator.reconcile_after_import = None
        conn = _make_connection()
        await ws_import_config(_make_hass(), conn, {"id": 1, "data": {"covers": {}}},
                               storage, coordinator)
        conn.send_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_called_on_invalid_data(self) -> None:
        storage = _make_storage()
        storage.async_import_data = AsyncMock(side_effect=ValueError("bad"))
        coordinator = _make_coordinator()
        coordinator.reconcile_after_import = MagicMock()
        conn = _make_connection()
        await ws_import_config(_make_hass(), conn, {"id": 1, "data": {}}, storage, coordinator)
        coordinator.reconcile_after_import.assert_not_called()
        assert conn.send_error.call_args.args[1] == "invalid_data"


# ---------------------------------------------------------------------------
# 7. Export
# ---------------------------------------------------------------------------

class TestExport:
    @pytest.mark.asyncio
    async def test_runtime_and_internal_state_not_exported(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_status("cover.a", "paused", 1234.0)
        storage.update_cover_measured_travel("cover.a", 20.0)
        storage._data["wind_protected_state"] = True
        storage._data["some_internal"] = 1
        data = storage.get_export_data()
        cover = data["covers"]["cover.a"]
        for key in ("status", "pause_until", "last_position_change"):
            assert key not in cover
        # The learned travel time is exported
        assert cover["measured_travel_time"] == 20.0
        assert "wind_protected_state" not in data
        assert "some_internal" not in data
        assert data["migrations"] == list(_ALL_MIGRATIONS)

    @pytest.mark.asyncio
    async def test_roundtrip_does_not_replay_migrations(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"].update({"pause_duration": 120, "preemptive_shading": True})
        await storage.async_import_data(data)
        exported = json.loads(json.dumps(storage.get_export_data()))
        await storage.async_import_data(exported)
        assert storage.covers["cover.a"].pause_duration == 120
        assert storage.covers["cover.a"].preemptive_shading is True


# ---------------------------------------------------------------------------
# 8. Migration replay on import
# ---------------------------------------------------------------------------

class TestImportMigrations:
    @pytest.mark.asyncio
    async def test_missing_markers_replayed(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data.pop("migrations")
        data["covers"]["cover.a"].update({"pause_duration": 120, "preemptive_shading": True})
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].pause_duration is None
        assert storage.covers["cover.a"].preemptive_shading is None
        assert set(storage._data["migrations"]) == set(_ALL_MIGRATIONS)

    @pytest.mark.asyncio
    async def test_only_missing_ones(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["migrations"] = [MIGRATION_PREEMPTIVE_TRISTATE, "future_migration"]
        data["covers"]["cover.a"].update({"pause_duration": 120, "preemptive_shading": True})
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].pause_duration is None
        assert storage.covers["cover.a"].preemptive_shading is True
        assert MIGRATION_PAUSE_DURATION_120 in storage._data["migrations"]
        assert "future_migration" in storage._data["migrations"]

    @pytest.mark.asyncio
    async def test_idempotent(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["migrations"] = "garbage"
        await storage.async_import_data(data)
        first = list(storage._data["migrations"])
        await storage.async_import_data(storage.get_raw_data())
        assert storage._data["migrations"] == first
        assert len(first) == len(set(first))


# ---------------------------------------------------------------------------
# 9. Scenario deletion
# ---------------------------------------------------------------------------

class TestScenarioDeletion:
    @pytest.mark.asyncio
    async def test_rule_without_scenario_is_disabled(self, storage, caplog) -> None:
        await storage.async_load()
        data = _base_config()
        data["scenarios"]["summer"] = {"id": "summer", "name": "Summer"}
        data["rules"]["only_summer"] = {"id": "only_summer", "name": "OS", "cover_ids": ["cover.a"],
                                        "scenario_ids": ["summer"]}
        data["rules"]["both"] = {"id": "both", "name": "B", "cover_ids": ["cover.a"],
                                 "scenario_ids": ["summer", "everyday"]}
        await storage.async_import_data(data)
        await storage.async_remove_scenario("summer")
        assert storage.rules["only_summer"].enabled is False
        assert storage.rules["only_summer"].scenario_ids == []
        assert storage.rules["both"].enabled is True
        assert "no scenario left" in caplog.text


# ---------------------------------------------------------------------------
# 10/11. WS entity fields and per-cover pause
# ---------------------------------------------------------------------------

class TestWsEntityFields:
    @pytest.mark.parametrize("key", [
        "outdoor_temp_sensor", "indoor_temp_sensor", "weather_entity", "workday_sensor",
        "wind_sensor", "solar_sensor",
    ])
    def test_settings_entities(self, key) -> None:
        assert _valid("settings/update", **{key: ""})[key] is None
        assert _valid("settings/update", **{key: None})[key] is None
        assert _valid("settings/update", **{key: "sensor.x"})[key] == "sensor.x"
        _invalid("settings/update", **{key: "nodot"})

    @pytest.mark.parametrize("key", ["lock_sensor", "vent_sensor", "indoor_temp_sensor",
                                     "occupancy_sensor"])
    def test_cover_entities(self, key) -> None:
        assert _valid("cover/update", entity_id="cover.a", **{key: ""})[key] is None
        assert _valid("cover/update", entity_id="cover.a", **{key: "binary_sensor.w"})[key] == "binary_sensor.w"
        _invalid("cover/update", entity_id="cover.a", **{key: "nodot"})

    def test_cover_pause_duration(self) -> None:
        _invalid("cover/update", entity_id="cover.a", pause_duration=0)
        assert _valid("cover/update", entity_id="cover.a", pause_duration=1)["pause_duration"] == 1
        assert _valid("cover/update", entity_id="cover.a", pause_duration=None)["pause_duration"] is None


# ---------------------------------------------------------------------------
# 12. Rule id kept when the name does not change
# ---------------------------------------------------------------------------

class TestRuleIdStable:
    @pytest.mark.asyncio
    async def test_same_name_keeps_id(self, storage) -> None:
        await storage.async_load()
        await storage.async_add_rule(Rule(id="custom", name="Night"), save=False)
        coordinator = _make_coordinator()
        coordinator.engine = None
        conn = _make_connection()
        await ws_rule_update(_make_hass(), conn,
                             {"id": 1, "rule_id": "custom", "name": "Night", "priority": 5},
                             storage, coordinator)
        assert list(storage.rules) == ["custom"]
        assert "renamed_rule" not in conn.send_result.call_args.args[1]
        coordinator.rename_rule_references.assert_not_called()

    @pytest.mark.asyncio
    async def test_changed_name_renames(self, storage) -> None:
        await storage.async_load()
        await storage.async_add_rule(Rule(id="custom", name="Night"), save=False)
        coordinator = _make_coordinator()
        coordinator.engine = None
        conn = _make_connection()
        await ws_rule_update(_make_hass(), conn, {"id": 1, "rule_id": "custom", "name": "Day"},
                             storage, coordinator)
        assert list(storage.rules) == ["day"]


# ---------------------------------------------------------------------------
# 13. Non-dict conditions
# ---------------------------------------------------------------------------

class TestParseConditions:
    def test_non_dict_conditions(self) -> None:
        conditions, errors = _parse_conditions(["sun_on_facade", 3, None,
                                                {"type": "sun_on_facade"}])
        assert len(conditions) == 1
        assert len(errors) == 3
        _, errors = _parse_conditions("text")
        assert errors

    @pytest.mark.asyncio
    async def test_ws_error(self) -> None:
        conn = _make_connection()
        await ws_rule_add(_make_hass(), conn, {"id": 1, "name": "R", "conditions": ["x"]},
                          _make_storage(), _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_conditions"

    @pytest.mark.asyncio
    async def test_ws_error_nan_param(self) -> None:
        conn = _make_connection()
        await ws_rule_add(_make_hass(), conn,
                          {"id": 1, "name": "R",
                           "conditions": [{"type": "sun_elevation_above", "params": {"value": "nan"}}]},
                          _make_storage(), _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_conditions"


# ---------------------------------------------------------------------------
# 14. Facade update refresh
# ---------------------------------------------------------------------------

class TestFacadeUpdateRefresh:
    @pytest.mark.asyncio
    async def test_refresh_and_entity_sync(self) -> None:
        storage = _make_storage(facades={"f": Facade(id="f", name="F", azimuth_start=0, azimuth_end=90)})
        coordinator = _make_coordinator()
        conn = _make_connection()
        await ws_facade_update(_make_hass(), conn,
                               {"id": 1, "facade_id": "f", "azimuth_start": 30, "name": "G"},
                               storage, coordinator)
        coordinator.async_request_refresh.assert_awaited_once()
        coordinator.async_sync_entities.assert_called_once()
        conn.send_result.assert_called_once()


def test_condition_type_still_parsed() -> None:
    cond = Condition.from_dict({"type": "sun_elevation_above", "params": {"value": 10}})
    assert cond.type is ConditionType.SUN_ELEVATION_ABOVE
    assert math.isfinite(cond.params["value"])

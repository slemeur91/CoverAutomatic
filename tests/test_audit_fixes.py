"""Regression tests for audit fixes (engine, storage, models, API, services)."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cover_automatic import engine as engine_mod
from custom_components.cover_automatic import ha_condition as hac
from custom_components.cover_automatic.models import (
    ComfortMode,
    Condition,
    ConditionType,
    CoverConfig,
    Facade,
    Rule,
    Scenario,
)
from custom_components.cover_automatic.storage import (
    _ALL_MIGRATIONS,
    MIGRATION_PAUSE_DURATION_120,
    resolve_active_scenario,
)
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_engine import MockState, engine, mock_hass, mock_storage  # noqa: F401
from tests.test_storage import mock_store, storage  # noqa: F401

COVER = CoverConfig(entity_id="cover.a", name="A", facade_id="south")


def _states(mock_hass, mapping: dict[str, str]) -> None:
    mock_hass.states.get = MagicMock(
        side_effect=lambda eid: MockState(mapping[eid]) if eid in mapping else None
    )


# ---------------------------------------------------------------------------
# 1. Removing the last cover/facade of a rule disables it
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 4. Negated conditions are never met with an unknown input
# ---------------------------------------------------------------------------

class TestNegationUnknown:
    def test_state_is_unavailable_is_unknown(self, engine, mock_hass) -> None:
        _states(mock_hass, {"binary_sensor.rain": "unavailable"})
        cond = Condition(
            type=ConditionType.STATE_IS,
            params={"entity_id": "binary_sensor.rain", "state": "on"}, negate=True,
        )
        assert engine._evaluate_final(cond, COVER) is False
        _states(mock_hass, {"binary_sensor.rain": "off"})
        assert engine._evaluate_final(cond, COVER) is True

    def test_state_is_expecting_unavailable_stays_known(self, engine, mock_hass) -> None:
        _states(mock_hass, {"sensor.x": "unavailable"})
        cond = Condition(
            type=ConditionType.STATE_IS,
            params={"entity_id": "sensor.x", "state": "unavailable"}, negate=True,
        )
        assert engine._evaluate_final(cond, COVER) is False
        _states(mock_hass, {"sensor.x": "on"})
        assert engine._evaluate_final(cond, COVER) is True

    def test_ha_condition_error_is_unknown(self, engine) -> None:
        def raiser(hass, variables):
            raise ValueError("no numeric state")

        cond = Condition(type=ConditionType.HA_CONDITION, params={"config": {"condition": "x"}}, negate=True)
        engine._ha_compiled[hac.config_key(cond.params["config"])] = hac.CompiledCondition(checker=raiser)
        assert engine._evaluate_final(cond, COVER) is False
        # Non-negated behaviour unchanged
        cond.negate = False
        assert engine._evaluate_final(cond, COVER) is False

    def test_ha_condition_tristate(self, engine) -> None:
        compiled = hac.CompiledCondition(checker=lambda h, v: False)
        assert hac.evaluate_tristate(engine.hass, compiled) is False
        assert hac.evaluate_tristate(engine.hass, None) is None
        assert hac.evaluate(engine.hass, None) is False
        cond = Condition(type=ConditionType.HA_CONDITION, params={"config": {"condition": "y"}}, negate=True)
        engine._ha_compiled[hac.config_key(cond.params["config"])] = compiled
        assert engine._evaluate_final(cond, COVER) is True

    def test_sun_on_facade_missing_facade_is_unknown(self, engine, mock_storage) -> None:
        mock_storage.facades = {}
        cond = Condition(type=ConditionType.SUN_ON_FACADE, negate=True)
        with patch.object(engine_mod, "get_sun_position", return_value=(180.0, 30.0)):
            assert engine._evaluate_final(cond, COVER) is False

    def test_sun_on_facade_comfort_unknown(self, engine, mock_hass, mock_storage) -> None:
        mock_storage.facades = {"south": Facade(id="south", name="S", azimuth_start=90, azimuth_end=270)}
        _states(mock_hass, {})  # indoor sensor missing, no grace
        cond = Condition(type=ConditionType.SUN_ON_FACADE, negate=True)
        with (
            patch.object(engine_mod, "get_sun_position", return_value=(180.0, 30.0)),
            patch.object(engine_mod, "is_sun_on_facade", return_value=True),
        ):
            assert engine._evaluate_final(cond, COVER) is False
        # Sun not on the facade: comfort irrelevant, NOT is met
        with (
            patch.object(engine_mod, "get_sun_position", return_value=(10.0, 30.0)),
            patch.object(engine_mod, "is_sun_on_facade", return_value=False),
        ):
            assert engine._evaluate_final(cond, COVER) is True

    def test_evaluator_exception_is_unknown(self, engine) -> None:
        cond = Condition(type=ConditionType.WORKDAY, negate=True)
        with patch.object(engine, "_eval_workday", side_effect=RuntimeError("boom")):
            assert engine._evaluate_final(cond, COVER) is False

    def test_polar_sun_event_is_unknown(self, engine) -> None:
        cond = Condition(type=ConditionType.TIME_BEFORE_SUNSET, params={"offset": 0}, negate=True)
        with patch.object(engine_mod, "get_sunset_time", return_value=None):
            assert engine._evaluate_final(cond, COVER) is False


# ---------------------------------------------------------------------------
# 6. Unknown/empty active scenario
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 5. pause_duration 120 migration runs once
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 7. Import robustness
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 8. time_between with start == end
# ---------------------------------------------------------------------------

class TestTimeBetweenAllDay:
    @pytest.mark.parametrize("now", [time(0, 0), time(8, 0, 30), time(12, 0), time(23, 59, 59)])
    def test_same_start_end_is_all_day(self, engine, now) -> None:
        cond = Condition(type=ConditionType.TIME_BETWEEN, params={"start": "08:00", "end": "08:00"})
        with patch.object(engine_mod, "dt_util") as mock_dt:
            mock_dt.now.return_value.time.return_value = now
            assert engine._eval_time_between(cond) is True


# ---------------------------------------------------------------------------
# 9. Hysteresis state of all conditions is updated (no short-circuit)
# ---------------------------------------------------------------------------

class TestNoShortCircuit:
    @pytest.mark.parametrize("operator", ["and", "or"])
    def test_later_threshold_state_updated(self, engine, mock_hass, mock_storage, operator) -> None:
        # First condition decides the result (False for AND, True for OR)
        first_state = "off" if operator == "and" else "on"
        _states(mock_hass, {"binary_sensor.x": first_state, "sensor.out": "30"})
        rule = Rule(
            id="r", name="R", condition_operator=operator, cover_ids=["cover.a"],
            conditions=[
                Condition(type=ConditionType.STATE_IS, params={"entity_id": "binary_sensor.x", "state": "on"}),
                Condition(type=ConditionType.TEMPERATURE_ABOVE, params={"sensor": "sensor.out", "temperature": 25}),
            ],
        )
        engine._evaluate_conditions(rule, COVER)
        assert engine._threshold_states[("sensor.out", 25.0, True, 0.5)] is True

    def test_groups_semantics_kept(self, engine, mock_hass) -> None:
        _states(mock_hass, {"a": "on", "b": "off", "c": "off", "d": "on"})

        def st(entity, group, negate=False):
            return Condition(type=ConditionType.STATE_IS, params={"entity_id": entity, "state": "on"},
                             group=group, negate=negate)

        rule = Rule(id="r", name="R", condition_operator="and", group_operators=["or", "or"],
                    conditions=[st("a", 0), st("b", 0), st("c", 1), st("d", 1)])
        assert engine._evaluate_conditions(rule, COVER) is True
        rule.group_operators = ["or", "and"]
        assert engine._evaluate_conditions(rule, COVER) is False
        rule.condition_operator = "or"
        assert engine._evaluate_conditions(rule, COVER) is True
        rule.conditions = [st("a", 0, negate=True), st("c", 1)]
        assert engine._evaluate_conditions(rule, COVER) is False


# ---------------------------------------------------------------------------
# 10. Failed ha_condition compilations are retried
# ---------------------------------------------------------------------------

class TestHaConditionRetry:
    @pytest.mark.asyncio
    async def test_failed_compile_retried(self, engine, mock_storage) -> None:
        config = {"condition": "state", "entity_id": "person.a", "state": "home"}
        cond = Condition(type=ConditionType.HA_CONDITION, params={"config": config})
        mock_storage.rules = {"r": Rule(id="r", name="R", conditions=[cond])}
        failed = hac.CompiledCondition(error="not loaded", error_code="invalid")
        ok = hac.CompiledCondition(checker=lambda h, v: True, entities={"person.a"})
        compile_mock = AsyncMock(side_effect=[failed, ok])
        clock = [1000.0]
        with (
            patch.object(engine_mod.hac, "async_compile", compile_mock),
            patch.object(engine_mod, "monotonic", side_effect=lambda: clock[0]),
        ):
            await engine.async_prepare_ha_conditions()
            status = engine.ha_condition_status(cond)
            assert status["valid"] is False and status["error"] == "not loaded"
            # Within the retry interval: no recompilation
            await engine.async_prepare_ha_conditions()
            assert compile_mock.await_count == 1
            clock[0] += engine_mod.HA_CONDITION_RETRY_INTERVAL
            assert await engine.async_prepare_ha_conditions() is True
        assert compile_mock.await_count == 2
        assert engine.ha_condition_status(cond)["valid"] is True
        # A valid compilation stays cached
        with patch.object(engine_mod.hac, "async_compile", compile_mock):
            await engine.async_prepare_ha_conditions()
        assert compile_mock.await_count == 2


# ---------------------------------------------------------------------------
# 11. Invalid effective comfort range falls back to the global pair
# ---------------------------------------------------------------------------

class TestComfortRangeFallback:
    def test_invalid_override_uses_global(self, engine, mock_hass, mock_storage, caplog) -> None:
        mock_storage.comfort_temp_min = 26.0
        mock_storage.comfort_temp_max = 30.0
        cover = CoverConfig(entity_id="cover.a", name="A", comfort_temp_max=24.0)
        _states(mock_hass, {"sensor.indoor_temp": "31"})
        assert engine._get_comfort_mode(cover) == ComfortMode.COOLING
        _states(mock_hass, {"sensor.indoor_temp": "25"})
        assert engine._get_comfort_mode(cover) == ComfortMode.HEATING
        warnings = [r for r in caplog.records if "Invalid comfort range" in r.message]
        assert len(warnings) == 1

    def test_valid_override_unchanged(self, engine, mock_hass) -> None:
        cover = CoverConfig(entity_id="cover.a", name="A", comfort_temp_min=18.0, comfort_temp_max=20.0)
        _states(mock_hass, {"sensor.indoor_temp": "20.5"})
        assert engine._get_comfort_mode(cover) == ComfortMode.COOLING


# ---------------------------------------------------------------------------
# 12. import_config: filesystem access runs in the executor
# ---------------------------------------------------------------------------

class TestServicesExecutor:
    @pytest.mark.asyncio
    async def test_import_checks_run_in_executor(self) -> None:
        from custom_components.cover_automatic.services import async_setup_services

        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        handlers: dict = {}
        hass.services.async_register = lambda d, s, h, **kw: handlers.__setitem__(s, h)
        hass.config.config_dir = "/config"
        jobs: list = []

        async def executor(fn):
            jobs.append(fn)  # not run: nothing may touch the filesystem inline
            return {"rules": {}}

        hass.async_add_executor_job = executor
        entry = MagicMock()
        entry.runtime_data.storage.async_import_data = AsyncMock()
        entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
        hass.config_entries.async_entries = MagicMock(return_value=[entry])
        await async_setup_services(hass)

        call = MagicMock()
        call.data = {"path": "/config/x.yaml"}
        call.context.user_id = None
        path = MagicMock()
        path.exists.return_value = True
        path.stat.return_value.st_size = 10
        with patch(
            "custom_components.cover_automatic.services._validate_config_path",
            return_value=path,
        ) as validate:
            await handlers["import_config"](call)
            # resolve/exists/stat did not run on the event loop
            validate.assert_not_called()
            path.exists.assert_not_called()
            path.stat.assert_not_called()
            entry.runtime_data.storage.async_import_data.assert_awaited_once()
            # ... they run inside the executor job
            with patch("builtins.open", MagicMock()), patch(
                "custom_components.cover_automatic.services.yaml.safe_load", return_value={}
            ):
                jobs[0]()
            validate.assert_called_once()
            path.exists.assert_called_once()
            path.stat.assert_called_once()

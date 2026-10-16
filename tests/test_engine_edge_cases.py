"""Engine edge cases: unknown states, negation, caches, night spans, sun event gaps."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from custom_components.cover_automatic.models import ComfortMode, Condition, ConditionType, CoverConfig, Facade, Rule
from tests.test_engine import engine, mock_hass, mock_storage, test_cover, MockState  # noqa: F401
from datetime import time
from custom_components.cover_automatic import engine as engine_mod, ha_condition as hac
from tests.test_storage import mock_store, storage  # noqa: F401
from tests.test_engine_robustness import DAWN, DUSK, MIDNIGHT, SUNRISE, SUNSET, H, _sun_eval


class TestEngineCaches:
    def test_forget_deleted_covers(self, engine) -> None:
        engine._last_comfort_mode = {"a": ComfortMode.HEATING, "b": ComfortMode.COOLING}
        engine._last_comfort_read = {"a": 1.0, "b": 2.0}
        engine._comfort_range_warned = {"a", "b"}
        engine.forget_covers_except({"a"})
        assert set(engine._last_comfort_mode) == {"a"} and set(engine._last_comfort_read) == {"a"}
        assert engine._comfort_range_warned == {"a"}

    def test_no_sensor_clears_stale_mode(self, engine, mock_storage, test_cover) -> None:
        mock_storage.indoor_temp_sensor = None
        test_cover.indoor_temp_sensor = None
        engine._last_comfort_mode[test_cover.entity_id] = ComfortMode.COOLING
        assert engine._get_comfort_mode(test_cover) is None
        assert test_cover.entity_id not in engine._last_comfort_mode

    def test_condition_error_logged_once(self, engine, test_cover, caplog) -> None:
        cond = Condition(type=ConditionType.STATE_IS, params={"entity_id": "x", "state": "on"})
        with patch.object(engine, "_dispatch_condition", side_effect=RuntimeError("boom")):
            for _ in range(3):
                engine._evaluate_condition(cond, test_cover)
        assert sum(1 for r in caplog.records if r.levelname == "ERROR") == 1


class TestSolarUnknown:
    def test_not_sun_on_facade_unknown_when_solar_unreadable(self, engine, mock_storage, test_cover) -> None:
        mock_storage.solar_sensor = "sensor.lux"
        mock_storage.sun_neutral_ignore = True
        mock_storage.preemptive_shading = True
        engine._last_comfort_mode[test_cover.entity_id] = ComfortMode.NEUTRAL
        with (
            patch.object(engine, "effective_solar_threshold", return_value=1000),
            patch.object(engine, "_read_float_state", return_value=None),
        ):
            assert engine._solar_known() is False
        with (
            patch.object(engine, "effective_solar_threshold", return_value=1000),
            patch.object(engine, "_read_float_state", return_value=5000.0),
        ):
            assert engine._solar_known() is True
        mock_storage.solar_sensor = None
        assert engine._solar_known() is True


class TestBeforeSunriseSpansNight:
    def test_evening_counts_as_before_sunrise(self, engine) -> None:
        cond = Condition(type=ConditionType.TIME_BEFORE_SUNRISE, params={"offset": 0})
        mod = "custom_components.cover_automatic.engine"
        with patch(f"{mod}.dt_util") as dt:
            now = dt.now.return_value
            now.timestamp.return_value = 80000.0  # evening
            assert engine._eval_time_before_morning_event(cond, lambda h: 25000.0, lambda h: 70000.0) is True
            now.timestamp.return_value = 50000.0  # afternoon
            assert engine._eval_time_before_morning_event(cond, lambda h: 25000.0, lambda h: 70000.0) is False
            now.timestamp.return_value = 20000.0  # before dawn
            assert engine._eval_time_before_morning_event(cond, lambda h: 25000.0, lambda h: 70000.0) is True


COVER = CoverConfig(entity_id="cover.a", name="A", facade_id="south")


def _states(mock_hass, mapping: dict[str, str]) -> None:
    mock_hass.states.get = MagicMock(
        side_effect=lambda eid: MockState(mapping[eid]) if eid in mapping else None
    )


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


class TestTimeBetweenAllDay:
    @pytest.mark.parametrize("now", [time(0, 0), time(8, 0, 30), time(12, 0), time(23, 59, 59)])
    def test_same_start_end_is_all_day(self, engine, now) -> None:
        cond = Condition(type=ConditionType.TIME_BETWEEN, params={"start": "08:00", "end": "08:00"})
        with patch.object(engine_mod, "dt_util") as mock_dt:
            mock_dt.now.return_value.time.return_value = now
            assert engine._eval_time_between(cond) is True


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


def _rule(conditions, **extra) -> dict:
    return {"id": "r", "name": "Night", "cover_ids": ["cover.a"], "conditions": conditions,
            "scenario_ids": ["everyday"], **extra}


def _time_rule(rule_id: str, ctype: ConditionType, offset: int, *, enabled: bool = True) -> Rule:
    return Rule(id=rule_id, name=rule_id, enabled=enabled,
                conditions=[Condition(type=ctype, params={"offset": offset})])


# (daytime condition, night condition whose offset joins it, evening side?)
JOINED = [
    (ConditionType.TIME_AFTER_SUNRISE, ConditionType.TIME_AFTER_SUNSET, True),
    (ConditionType.TIME_AFTER_DAWN, ConditionType.TIME_AFTER_DUSK, True),
    (ConditionType.TIME_BEFORE_SUNSET, ConditionType.TIME_BEFORE_SUNRISE, False),
    (ConditionType.TIME_BEFORE_DUSK, ConditionType.TIME_BEFORE_DAWN, False),
]


def _scan(engine, day, night, night_offset):
    """Every minute over a day: (day, night) results."""
    for minute in range(0, 24 * 60):
        now = MIDNIGHT + minute * 60 + 1
        yield (
            now,
            _sun_eval(engine, day, now),
            _sun_eval(engine, night, now, offset=night_offset),
        )


class TestNoGapWithOffsets:
    @pytest.mark.parametrize(("day", "night", "_evening"), JOINED)
    def test_default_complementary_without_offsets(self, engine, mock_storage,
                                                   day, night, _evening) -> None:
        mock_storage.rules = {"n": _time_rule("n", night, 0), "d": _time_rule("d", day, 0)}
        for now, a, b in _scan(engine, day, night, 0):
            assert a != b, (day, night, (now - MIDNIGHT) / H)

    @pytest.mark.parametrize(("day", "night", "evening"), JOINED)
    def test_no_gap_with_offset(self, engine, mock_storage, day, night, evening) -> None:
        offset = 15 if evening else -15
        mock_storage.rules = {"n": _time_rule("n", night, offset), "d": _time_rule("d", day, 0)}
        for now, a, b in _scan(engine, day, night, offset):
            assert a or b, (day, night, (now - MIDNIGHT) / H)

    def test_after_dusk_plus_15_example(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "close": _time_rule("close", ConditionType.TIME_AFTER_DUSK, 15),
            "open": _time_rule("open", ConditionType.TIME_AFTER_DAWN, 0),
        }
        now = DUSK + 10 * 60
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DUSK, now, offset=15) is False
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DAWN, now) is True
        # ends exactly when the closing rule starts
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DAWN, DUSK + 15 * 60) is False
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DUSK, DUSK + 15 * 60, offset=15) is True

    def test_largest_positive_offset_wins(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, 10),
            "b": _time_rule("b", ConditionType.TIME_AFTER_SUNSET, 40),
            "c": _time_rule("c", ConditionType.TIME_AFTER_SUNSET, -20),
        }
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 39 * 60) is True
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 41 * 60) is False

    def test_negative_offsets_do_not_shorten(self, engine, mock_storage) -> None:
        mock_storage.rules = {"a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, -30)}
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET - 10 * 60) is True
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 1) is False

    def test_disabled_rules_ignored(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, 30, enabled=False),
        }
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 10 * 60) is False

    def test_morning_lead_from_negative_before_sunrise(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "a": _time_rule("a", ConditionType.TIME_BEFORE_SUNRISE, -30),
            "b": _time_rule("b", ConditionType.TIME_BEFORE_SUNRISE, 20),
        }
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_SUNSET, SUNRISE - 20 * 60) is True
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_SUNSET, SUNRISE - 40 * 60) is False
        # dawn side is independent
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_DUSK, DAWN - 20 * 60) is False

    def test_offset_does_not_extend_daytime_window_start(self, engine, mock_storage) -> None:
        # the evening extension does not change the morning start
        mock_storage.rules = {"a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, 30)}
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNRISE - 60) is False
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNRISE + 60) is True

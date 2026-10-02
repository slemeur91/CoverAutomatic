"""Engine fixes (sun-time windows, stale hysteresis, NOT on bad config, ...)."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

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
)
from custom_components.cover_automatic.sun import _azimuth_in_facade, is_sun_on_facade
from tests.test_engine import MockState, engine, mock_hass, mock_storage  # noqa: F401
from tests.test_ha_condition import hass  # noqa: F401
from tests.test_sun import MockState as SunState

MOD = "custom_components.cover_automatic.engine"
COVER = CoverConfig(entity_id="cover.a", name="A", facade_id="south")

H = 3600
MIDNIGHT = 1_000_000.0
DAWN = MIDNIGHT + 5.5 * H
SUNRISE = MIDNIGHT + 6 * H
SUNSET = MIDNIGHT + 21 * H
DUSK = MIDNIGHT + 21.5 * H


def _states(mock_hass, mapping: dict[str, str]) -> None:
    mock_hass.states.get = MagicMock(
        side_effect=lambda eid: MockState(mapping[eid]) if eid in mapping else None
    )


def _sun_eval(engine, ctype, now, *, offset=0, negate=False, events=None):
    """Evaluate a sun-time condition at `now` with fixed events of the day."""
    ev = {"dawn": DAWN, "sunrise": SUNRISE, "sunset": SUNSET, "dusk": DUSK}
    ev.update(events or {})
    cond = Condition(type=ctype, params={"offset": offset}, negate=negate)

    def yesterday(_hass, event, _offset):
        base = ev["sunset"] if event == "sunset" else ev["dusk"]
        return None if base is None else base - 24 * H

    with (
        patch(f"{MOD}.get_dawn_time", return_value=ev["dawn"]),
        patch(f"{MOD}.get_sunrise_time", return_value=ev["sunrise"]),
        patch(f"{MOD}.get_sunset_time", return_value=ev["sunset"]),
        patch(f"{MOD}.get_dusk_time", return_value=ev["dusk"]),
        patch(f"{MOD}.get_sun_event_time", side_effect=yesterday),
        patch(f"{MOD}.dt_util.now") as mock_now,
    ):
        mock_now.return_value.timestamp.return_value = now
        return engine._evaluate_final(cond, None)


# ---------------------------------------------------------------------------
# 1. Sun-time pairs are complementary (no night overlap)
# ---------------------------------------------------------------------------

PAIRS = [
    (ConditionType.TIME_AFTER_SUNSET, ConditionType.TIME_BEFORE_SUNSET),
    (ConditionType.TIME_BEFORE_SUNRISE, ConditionType.TIME_AFTER_SUNRISE),
    (ConditionType.TIME_AFTER_DUSK, ConditionType.TIME_BEFORE_DUSK),
    (ConditionType.TIME_BEFORE_DAWN, ConditionType.TIME_AFTER_DAWN),
]


class TestSunTimeWindows:
    @pytest.mark.parametrize(("night", "day"), PAIRS)
    @pytest.mark.parametrize("offset", [0, -30, 45])
    def test_pairs_are_complementary(self, engine, night, day, offset) -> None:
        # every 15 min over a whole day: exactly one of the pair is true
        for step in range(0, 24 * 4):
            now = MIDNIGHT + step * 900 + 1
            a = _sun_eval(engine, night, now, offset=offset)
            b = _sun_eval(engine, day, now, offset=offset)
            assert a != b, (night, day, offset, (now - MIDNIGHT) / H)

    @pytest.mark.parametrize(
        ("ctype", "hour", "expected"),
        [
            # before_sunset: from sunrise until sunset (no longer from midnight)
            (ConditionType.TIME_BEFORE_SUNSET, 2, False),
            (ConditionType.TIME_BEFORE_SUNSET, 12, True),
            (ConditionType.TIME_BEFORE_SUNSET, 22, False),
            # after_sunrise: from sunrise until sunset (no longer until midnight)
            (ConditionType.TIME_AFTER_SUNRISE, 2, False),
            (ConditionType.TIME_AFTER_SUNRISE, 12, True),
            (ConditionType.TIME_AFTER_SUNRISE, 22, False),
            (ConditionType.TIME_BEFORE_DUSK, 5, False),
            (ConditionType.TIME_BEFORE_DUSK, 21.25, True),
            (ConditionType.TIME_AFTER_DAWN, 21.25, True),
            (ConditionType.TIME_AFTER_DAWN, 23, False),
        ],
    )
    def test_daytime_windows(self, engine, ctype, hour, expected) -> None:
        assert _sun_eval(engine, ctype, MIDNIGHT + hour * H) is expected

    def test_offsets_kept(self, engine) -> None:
        # before_sunset offset -60: until one hour before sunset
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_SUNSET, SUNSET - 30 * 60, offset=-60) is False
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_SUNSET, SUNSET - 90 * 60, offset=-60) is True
        # after_sunrise offset 30: from half an hour after sunrise
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNRISE + 20 * 60, offset=30) is False
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNRISE + 40 * 60, offset=30) is True

    @pytest.mark.parametrize(
        "ctype",
        [ConditionType.TIME_BEFORE_SUNSET, ConditionType.TIME_AFTER_SUNRISE,
         ConditionType.TIME_BEFORE_DUSK, ConditionType.TIME_AFTER_DAWN],
    )
    def test_polar_missing_event_false_and_unknown(self, engine, ctype) -> None:
        none_events = {"dawn": None, "sunrise": None}
        now = MIDNIGHT + 12 * H
        assert _sun_eval(engine, ctype, now, events=none_events) is False
        # missing morning event: NOT is not met either (unknown)
        assert _sun_eval(engine, ctype, now, negate=True, events=none_events) is False


# ---------------------------------------------------------------------------
# 2. Stale threshold hysteresis state is ignored and purged
# ---------------------------------------------------------------------------

class TestStaleThresholdState:
    def test_old_state_ignored(self, engine, mock_storage) -> None:
        clock = [1000.0]
        with patch.object(engine_mod, "monotonic", side_effect=lambda: clock[0]):
            assert engine._threshold_with_hysteresis(
                "sensor.t", 26.0, 25.0, above=True, update_state=True, hysteresis=2.0
            ) is True
            # inside the band: held while fresh
            clock[0] += 60
            assert engine._threshold_with_hysteresis(
                "sensor.t", 24.0, 25.0, above=True, update_state=True, hysteresis=2.0
            ) is True
            # not evaluated for a long time: hard boundary decides
            clock[0] += engine_mod.HYSTERESIS_STATE_MAX_AGE + 1
            assert engine._threshold_with_hysteresis(
                "sensor.t", 24.0, 25.0, above=True, update_state=True, hysteresis=2.0
            ) is False

    def test_old_keys_purged(self, engine) -> None:
        clock = [1000.0]
        with patch.object(engine_mod, "monotonic", side_effect=lambda: clock[0]):
            engine._threshold_with_hysteresis(
                "sensor.old", 26.0, 25.0, above=True, update_state=True, hysteresis=1.0
            )
            clock[0] += 2 * engine_mod.HYSTERESIS_STATE_MAX_AGE
            engine._threshold_with_hysteresis(
                "sensor.new", 26.0, 25.0, above=True, update_state=True, hysteresis=1.0
            )
        keys = {k[0] for k in engine._threshold_states}
        assert keys == {"sensor.new"}
        assert set(engine._threshold_stamps) == set(engine._threshold_states)


# ---------------------------------------------------------------------------
# 3. Stale previous comfort mode is dropped
# ---------------------------------------------------------------------------

class TestStaleComfortMode:
    def test_stale_prev_uses_hard_boundaries(self, engine, mock_hass) -> None:
        # range 21-25, hysteresis 1
        cover = CoverConfig(entity_id="cover.a", name="A")
        clock = [1000.0]
        with patch.object(engine_mod, "monotonic", side_effect=lambda: clock[0]):
            _states(mock_hass, {"sensor.indoor_temp": "26"})
            assert engine._get_comfort_mode(cover) == ComfortMode.COOLING
            # fresh: 24.5 is inside the band -> stays COOLING
            clock[0] += 60
            _states(mock_hass, {"sensor.indoor_temp": "24.5"})
            assert engine._get_comfort_mode(cover) == ComfortMode.COOLING
            # hours later (sun was off the facade, mode not recomputed)
            clock[0] += 3 * H
            assert engine._get_comfort_mode(cover) == ComfortMode.NEUTRAL


# ---------------------------------------------------------------------------
# 4. NOT on a misconfigured condition is not met
# ---------------------------------------------------------------------------

class TestNotMisconfigured:
    @pytest.mark.parametrize(
        ("ctype", "params"),
        [
            (ConditionType.NUMERIC_STATE, {"entity_id": "sensor.x"}),
            (ConditionType.NUMERIC_STATE, {"entity_id": "sensor.x", "value": "abc"}),
            (ConditionType.TEMPERATURE_ABOVE, {"sensor": "sensor.x", "temperature": "hot"}),
            (ConditionType.TEMPERATURE_BELOW, {"sensor": "sensor.x", "value": "cold"}),
            (ConditionType.SUN_ELEVATION_ABOVE, {"elevation": "high"}),
            (ConditionType.SUN_ELEVATION_BELOW, {"value": None}),
            (ConditionType.TIME_AFTER_SUNSET, {"offset": "later"}),
            (ConditionType.TIME_BEFORE_DAWN, {"offset": None}),
            (ConditionType.TIME_BEFORE_SUNRISE, {"offset": "early"}),
            (ConditionType.STATE_IS, {"entity_id": "sensor.x"}),
        ],
    )
    def test_negated_invalid_is_not_met(self, engine, mock_hass, ctype, params) -> None:
        mock_hass.states.get = MagicMock()
        mock_hass.states.get.side_effect = lambda eid: (
            MockState("10") if eid == "sensor.x"
            else SunState("above_horizon", {"azimuth": 180, "elevation": 30}) if eid == "sun.sun"
            else None
        )
        cond = Condition(type=ctype, params=params)
        assert engine._evaluate_final(cond, COVER) is False
        assert engine._evaluate_tristate(cond, COVER) is None
        cond.negate = True
        assert engine._evaluate_final(cond, COVER) is False

    def test_valid_negated_still_met(self, engine, mock_hass) -> None:
        _states(mock_hass, {"sensor.x": "10"})
        cond = Condition(
            type=ConditionType.NUMERIC_STATE,
            params={"entity_id": "sensor.x", "value": "20"}, negate=True,
        )
        assert engine._evaluate_final(cond, COVER) is True


# ---------------------------------------------------------------------------
# 5. Facade full circle and min_elevation bound
# ---------------------------------------------------------------------------

def _sun_hass(azimuth: float, elevation: float) -> MagicMock:
    hass = MagicMock()
    hass.states.get.return_value = SunState(
        "above_horizon", {"azimuth": azimuth, "elevation": elevation}
    )
    return hass


class TestFacadeRange:
    @pytest.mark.parametrize("azimuth", [0.0, 90.0, 180.0, 359.9])
    def test_start_equals_end_is_full_circle(self, azimuth) -> None:
        assert _azimuth_in_facade(azimuth, 0.0, 0.0) is True
        facade = Facade(id="f", name="F", azimuth_start=0.0, azimuth_end=0.0)
        assert is_sun_on_facade(_sun_hass(azimuth, 20.0), facade) is True

    def test_regular_ranges_unchanged(self) -> None:
        assert _azimuth_in_facade(100.0, 135.0, 225.0) is False
        assert _azimuth_in_facade(10.0, 300.0, 30.0) is True
        assert _azimuth_in_facade(200.0, 300.0, 30.0) is False

    def test_negative_min_elevation_bounded_at_horizon(self) -> None:
        facade = Facade(id="f", name="F", azimuth_start=90.0, azimuth_end=270.0,
                        min_elevation=-5.0)
        assert is_sun_on_facade(_sun_hass(180.0, -2.0), facade) is False
        assert is_sun_on_facade(_sun_hass(180.0, 0.5), facade) is True


# ---------------------------------------------------------------------------
# 6. Compilation errors never escape / never block other conditions
# ---------------------------------------------------------------------------

class TestCompileRobust:
    @pytest.mark.asyncio
    async def test_unexpected_exception_reported_invalid(self) -> None:
        with patch.object(
            hac.ha_condition, "async_from_config", AsyncMock(side_effect=RuntimeError("boom"))
        ), patch.object(hac.ha_condition, "async_validate_condition_config",
                        AsyncMock(side_effect=lambda h, c: c)):
            compiled = await hac.async_compile(
                MagicMock(), {"condition": "state", "entity_id": "person.a", "state": "home"}
            )
        assert compiled.valid is False
        assert compiled.error_code == "invalid" and "boom" in compiled.error

    @pytest.mark.asyncio
    async def test_one_failure_does_not_stop_others(self, engine, mock_storage) -> None:
        bad = Condition(type=ConditionType.HA_CONDITION, params={"config": {"condition": "x"}})
        good_cfg = {"condition": "state", "entity_id": "person.a", "state": "home"}
        good = Condition(type=ConditionType.HA_CONDITION, params={"config": good_cfg})
        mock_storage.rules = {"r": Rule(id="r", name="R", conditions=[bad, good])}
        ok = hac.CompiledCondition(checker=lambda h, v: True, entities={"person.a"})
        compile_mock = AsyncMock(side_effect=[RuntimeError("boom"), ok])
        with patch.object(engine_mod.hac, "async_compile", compile_mock):
            assert await engine.async_prepare_ha_conditions() is True
        assert engine.ha_condition_status(good)["valid"] is True
        status = engine.ha_condition_status(bad)
        assert status["valid"] is False and status["error_code"] == "invalid"


# ---------------------------------------------------------------------------
# 7. Template entities are refreshed before each cycle
# ---------------------------------------------------------------------------

class TestTemplateEntitiesRefresh:
    @pytest.mark.asyncio
    async def test_dynamic_template_entities(self, hass) -> None:
        hass.states.async_set("input_text.target", "sensor.lux")
        config = {
            "condition": "template",
            "value_template": "{{ states(states('input_text.target')) | float(0) > 1 }}",
        }
        cond = Condition(type=ConditionType.HA_CONDITION, params={"config": config})
        storage = MagicMock()
        storage.rules = {"r": Rule(id="r", name="R", conditions=[cond])}
        eng = engine_mod.RuleEngine(hass, storage)
        await eng.async_prepare_ha_conditions()
        assert "sensor.lux" in eng.ha_condition_entities()
        hass.states.async_set("sensor.other", "5")
        hass.states.async_set("input_text.target", "sensor.other")
        # next cycle: entity set changed, coordinator is told to resubscribe
        assert await eng.async_prepare_ha_conditions() is True
        entities = eng.ha_condition_entities()
        assert "sensor.other" in entities and "sensor.lux" not in entities
        # unchanged afterwards
        assert await eng.async_prepare_ha_conditions() is False

    def test_refresh_without_templates_is_noop(self) -> None:
        compiled = hac.CompiledCondition(checker=lambda h, v: True, entities={"a.b"})
        assert hac.refresh_template_entities(MagicMock(), compiled) is False
        assert compiled.entities == {"a.b"}


# ---------------------------------------------------------------------------
# 8. Solar hysteresis >= threshold can still release
# ---------------------------------------------------------------------------

class TestSolarHysteresisClamp:
    def _check(self, engine, mock_hass, lux: str) -> bool:
        _states(mock_hass, {"sensor.lux": lux})
        with patch.object(engine, "_setting_entity", return_value=None):
            return engine._check_solar_intensity()

    def test_release_reachable(self, engine, mock_hass, mock_storage) -> None:
        mock_storage.solar_sensor = "sensor.lux"
        mock_storage.solar_threshold = 1000.0
        mock_storage.solar_hysteresis = 5000.0
        assert engine._solar_hysteresis(1000.0) == 500.0
        assert self._check(engine, mock_hass, "2000") is True
        assert self._check(engine, mock_hass, "600") is True   # inside clamped band
        assert self._check(engine, mock_hass, "400") is False  # released
        assert self._check(engine, mock_hass, "1400") is False  # not yet on again
        assert self._check(engine, mock_hass, "1600") is True

    def test_small_hysteresis_unchanged(self, engine, mock_storage) -> None:
        mock_storage.solar_hysteresis = 200.0
        assert engine._solar_hysteresis(1000.0) == 200.0

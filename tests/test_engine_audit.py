"""Engine audit fixes (comfort caches, error log, solar unknown, night spans)."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import patch

from custom_components.cover_automatic.models import ComfortMode, Condition, ConditionType
from tests.test_engine import engine, mock_hass, mock_storage, test_cover  # noqa: F401


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
        test_cover.sun_neutral_ignore = None
        test_cover.preemptive_shading = None
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

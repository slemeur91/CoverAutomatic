"""Conditions "outdoor vs indoor" and "room occupied", occupancy fields."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.cover_automatic.models import Condition, ConditionType, CoverConfig
from tests.test_engine import engine, mock_hass, mock_storage, test_cover  # noqa: F401


def _states(mock_hass, values: dict) -> None:
    def get(entity_id):
        if entity_id not in values:
            return None
        st = MagicMock()
        st.state = values[entity_id]
        return st
    mock_hass.states.get.side_effect = get


def _ovi(operator="cooler", delta=0, negate=False):
    return Condition(type=ConditionType.OUTDOOR_VS_INDOOR,
                     params={"operator": operator, "delta": delta}, negate=negate)


class TestOutdoorVsIndoor:
    def _setup(self, mock_hass, mock_storage, test_cover, ext, int_):
        mock_storage.outdoor_temp_sensor = "sensor.ext"
        test_cover.indoor_temp_sensor = "sensor.room"
        _states(mock_hass, {"sensor.ext": ext, "sensor.room": int_})

    def test_cooler_and_warmer(self, engine, mock_hass, mock_storage, test_cover) -> None:
        self._setup(mock_hass, mock_storage, test_cover, "18", "24")
        assert engine._evaluate_condition(_ovi("cooler"), test_cover) is True
        assert engine._evaluate_condition(_ovi("warmer"), test_cover) is False
        self._setup(mock_hass, mock_storage, test_cover, "30", "24")
        assert engine._evaluate_condition(_ovi("warmer"), test_cover) is True

    def test_delta(self, engine, mock_hass, mock_storage, test_cover) -> None:
        self._setup(mock_hass, mock_storage, test_cover, "22", "24")
        assert engine._evaluate_condition(_ovi("cooler", 3), test_cover) is False
        assert engine._evaluate_condition(_ovi("cooler", 1), test_cover) is True

    def test_hysteresis_on_difference(self, engine, mock_hass, mock_storage, test_cover) -> None:
        mock_storage.threshold_hysteresis = 0.5
        cond = _ovi("warmer")
        self._setup(mock_hass, mock_storage, test_cover, "25", "24")   # +1
        assert engine._evaluate_condition(cond, test_cover) is True
        self._setup(mock_hass, mock_storage, test_cover, "23.8", "24")  # -0.2: kept
        assert engine._evaluate_condition(cond, test_cover) is True
        self._setup(mock_hass, mock_storage, test_cover, "23.4", "24")  # -0.6: false
        assert engine._evaluate_condition(cond, test_cover) is False
        self._setup(mock_hass, mock_storage, test_cover, "24.3", "24")  # +0.3: stays false
        assert engine._evaluate_condition(cond, test_cover) is False

    def test_uses_global_indoor_sensor(self, engine, mock_hass, mock_storage, test_cover) -> None:
        mock_storage.outdoor_temp_sensor = "sensor.ext"
        mock_storage.indoor_temp_sensor = "sensor.global"
        test_cover.indoor_temp_sensor = None
        _states(mock_hass, {"sensor.ext": "10", "sensor.global": "20"})
        assert engine._evaluate_condition(_ovi("cooler"), test_cover) is True

    def test_unavailable_is_unknown_even_negated(self, engine, mock_hass, mock_storage, test_cover) -> None:
        self._setup(mock_hass, mock_storage, test_cover, "18", "unavailable")
        assert engine._evaluate_condition(_ovi("cooler"), test_cover) is False
        # NOT on an unreadable room temperature is not met either
        assert engine._evaluate_final(_ovi("warmer", negate=True), test_cover) is False

    def test_needs_a_cover_in_preview(self, engine) -> None:
        assert engine.preview_condition(_ovi()) == {"evaluable": False}


class TestRoomOccupied:
    def _cond(self, negate=False):
        return Condition(type=ConditionType.ROOM_OCCUPIED, params={}, negate=negate)

    def test_no_sensor_is_free(self, engine, mock_hass, test_cover) -> None:
        _states(mock_hass, {})
        assert engine._evaluate_condition(self._cond(), test_cover) is False
        assert engine._evaluate_final(self._cond(negate=True), test_cover) is True

    def test_default_states(self, engine, mock_hass, test_cover) -> None:
        test_cover.occupancy_sensor = "input_select.presence"
        for state, occupied in (("Présent", True), ("Absent", False), ("on", True), ("off", False), ("home", True)):
            _states(mock_hass, {"input_select.presence": state})
            assert engine._evaluate_condition(self._cond(), test_cover) is occupied, state

    def test_custom_states(self, engine, mock_hass, test_cover) -> None:
        test_cover.occupancy_sensor = "input_select.presence"
        test_cover.occupancy_states = "Sieste, Nuit"
        _states(mock_hass, {"input_select.presence": "nuit"})
        assert engine._evaluate_condition(self._cond(), test_cover) is True
        _states(mock_hass, {"input_select.presence": "Présent"})
        assert engine._evaluate_condition(self._cond(), test_cover) is False

    def test_unavailable_blocks_not_occupied(self, engine, mock_hass, test_cover) -> None:
        test_cover.occupancy_sensor = "input_select.presence"
        _states(mock_hass, {"input_select.presence": "unavailable"})
        assert engine._evaluate_condition(self._cond(), test_cover) is False
        assert engine._evaluate_final(self._cond(negate=True), test_cover) is False


class TestOccupancyFields:
    def test_roundtrip(self) -> None:
        c = CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                   "occupancy_sensor": "input_select.p", "occupancy_states": " Présent "})
        assert c.occupancy_sensor == "input_select.p" and c.occupancy_states == "Présent"
        d = c.to_dict()
        assert d["occupancy_sensor"] == "input_select.p" and d["occupancy_states"] == "Présent"
        empty = CoverConfig.from_dict({"entity_id": "cover.a", "name": "A", "occupancy_states": ""})
        assert empty.occupancy_states is None and empty.occupancy_sensor is None

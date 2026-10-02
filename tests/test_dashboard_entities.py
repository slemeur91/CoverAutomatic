"""Dashboard sensors (rule, positions, comfort, pause end, counts, wind)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from custom_components.cover_automatic.binary_sensor import WindProtectionBinarySensor
from custom_components.cover_automatic.models import CoverConfig, CoverStatus
from custom_components.cover_automatic.sensor import (
    CoverAutomaticStatusSensor,
    CoverComfortSensor,
    CoverPauseEndSensor,
    CoverPositionSensor,
    CoverRuleSensor,
    CoverTargetPositionSensor,
    CoversInStatusSensor,
)

EID = "cover.salon"
PAUSE_TS = 1790450000.0


@pytest.fixture
def coord():
    c = MagicMock()
    c.hass = MagicMock()
    c.hass.config.language = "fr"
    c.storage.covers = {
        EID: CoverConfig(entity_id=EID, name="Salon", inverted=True),
        "cover.b": CoverConfig(entity_id="cover.b", name="B"),
    }
    c.get_cover_status = MagicMock(return_value=CoverStatus.PAUSED)
    c.get_logical_position = MagicMock(return_value=0)
    c.get_cover_live = MagicMock(return_value={
        "target_position": 0, "rule_id": "nuit", "rule_name": "Fermer la Nuit",
        "safety": False, "pause_until": PAUSE_TS, "comfort_mode": "neutral",
        "last_change": None,
    })
    return c


def _mk(cls, coord):
    ent = cls(coord, EID, "Salon")
    ent.hass = coord.hass
    return ent


class TestCoverSensors:
    def test_unique_ids(self, coord) -> None:
        ids = {_mk(c, coord).unique_id for c in (
            CoverAutomaticStatusSensor, CoverRuleSensor, CoverTargetPositionSensor,
            CoverPositionSensor, CoverComfortSensor, CoverPauseEndSensor)}
        assert ids == {f"cover_automatic_{EID}_{s}" for s in
                       ("status", "rule", "target", "position", "comfort", "pause_end")}

    def test_rule_sensor(self, coord) -> None:
        ent = _mk(CoverRuleSensor, coord)
        assert ent.native_value == "Fermer la Nuit"
        assert ent.extra_state_attributes["rule_id"] == "nuit"
        coord.get_cover_live.return_value = {}
        assert ent.native_value == "Aucune règle"

    def test_positions(self, coord) -> None:
        assert _mk(CoverTargetPositionSensor, coord).native_value == 0
        assert _mk(CoverPositionSensor, coord).native_value == 0
        coord.get_logical_position.assert_called_with(EID)

    def test_comfort(self, coord) -> None:
        ent = _mk(CoverComfortSensor, coord)
        assert ent.native_value == "neutral"
        assert set(ent.options) == {"heating", "neutral", "cooling"}

    def test_pause_end_only_while_paused(self, coord) -> None:
        ent = _mk(CoverPauseEndSensor, coord)
        assert ent.native_value == datetime.fromtimestamp(PAUSE_TS, tz=timezone.utc)
        coord.get_cover_status.return_value = CoverStatus.AUTO
        assert ent.native_value is None

    def test_status_attributes_for_card(self, coord) -> None:
        ent = _mk(CoverAutomaticStatusSensor, coord)
        reg = MagicMock()
        reg.async_get_entity_id.return_value = "switch.salon_auto"
        with patch("custom_components.cover_automatic.sensor.er.async_get", return_value=reg):
            attrs = ent.extra_state_attributes
        assert attrs["cover_entity_id"] == EID
        assert attrs["auto_switch"] == "switch.salon_auto"
        assert attrs["rule"] == "Fermer la Nuit"
        # upstream 1.62.0 attribute names
        assert attrs["rule_name"] == "Fermer la Nuit"
        assert attrs["rule_id"] == "nuit"
        assert attrs["position"] == 0 and attrs["target_position"] == 0
        assert attrs["inverted"] is True and attrs["auto_enabled"] is True
        assert attrs["pause_until"].startswith("2026-")
        assert ent.native_value == "paused"
        assert "wind_protected" in ent.options


class TestGlobal:
    def test_counts(self, coord) -> None:
        coord.get_cover_status = MagicMock(
            side_effect=lambda eid: CoverStatus.PAUSED if eid == EID else CoverStatus.AUTO)
        ent = CoversInStatusSensor(coord, "e1", CoverStatus.PAUSED)
        assert ent.native_value == 1
        assert ent.extra_state_attributes == {"covers": ["Salon"], "entity_ids": [EID]}
        assert ent.unique_id == "cover_automatic_e1_covers_paused"
        assert CoversInStatusSensor(coord, "e1", CoverStatus.LOCKED).native_value == 0

    def test_wind(self, coord) -> None:
        coord.wind_protected = True
        coord.get_wind_speed.return_value = 72.0
        coord.storage.wind_speed_threshold = 70
        ent = WindProtectionBinarySensor(coord, "e1")
        assert ent.is_on is True
        assert ent.extra_state_attributes["wind_speed"] == 72.0
        assert ent.unique_id == "cover_automatic_e1_wind_protection"


class TestCoordinatorAccessors:
    def test_get_cover_live(self) -> None:
        from custom_components.cover_automatic.coordinator import CoverAutomaticCoordinator

        c = MagicMock()
        c.data = {"covers": {EID: {"target_position": 30, "matching_rule_id": "r", "safety": True}}}
        c.storage.get_cover_raw.return_value = {"pause_until": 5.0, "last_position_change": 3.0}
        c.storage.rules = {"r": MagicMock(name_attr=None)}
        c.storage.rules["r"].name = "Ombre"
        c.engine._last_comfort_mode.get.return_value = None
        live = CoverAutomaticCoordinator.get_cover_live(c, EID)
        assert live == {"target_position": 30, "rule_id": "r", "rule_name": "Ombre", "safety": True,
                        "pause_until": 5.0, "comfort_mode": None, "last_change": 3.0}
        c.data = None
        assert CoverAutomaticCoordinator.get_cover_live(c, EID)["rule_id"] is None

"""Pending rule: the rule a cover the automation does not drive would follow.

Manual, paused, window-locked and wind-protected covers (and every cover
with the global automation off) show it greyed in the panel and in the
active rule sensor attributes. Display only: nothing is commanded.
"""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cover_automatic.models import CoverConfig, CoverStatus, CoverTarget
from tests.test_coordinator import (  # noqa: F401 -- pytest fixtures
    coordinator,
    mock_hass,
    mock_storage,
)

COVER = "cover.salon"
NIGHT = CoverTarget(position=0, rule_id="nuit", rule_name="Fermer la Nuit")


def _engine(full=NIGHT, safety=None):
    engine = MagicMock()
    engine.evaluate_cover.side_effect = lambda cover, safety_only=False: safety if safety_only else full
    return engine


@pytest.mark.parametrize("status", [
    CoverStatus.MANUAL, CoverStatus.PAUSED, CoverStatus.LOCKED, CoverStatus.WIND_PROTECTED,
])
def test_pending_rule_for_undriven_status(coordinator, mock_storage, status) -> None:
    mock_storage.enabled = True
    coordinator.engine = _engine()
    cover = CoverConfig(entity_id=COVER, name="Salon")
    assert coordinator._pending_rule(cover, status, None) == {
        "pending_rule_id": "nuit", "pending_target_position": 0,
    }


def test_none_in_auto(coordinator, mock_storage) -> None:
    mock_storage.enabled = True
    coordinator.engine = _engine()
    cover = CoverConfig(entity_id=COVER, name="Salon")
    assert coordinator._pending_rule(cover, CoverStatus.AUTO, NIGHT) == {}
    assert coordinator._pending_rule(cover, CoverStatus.VENTING, None) == {}


def test_global_automation_off(coordinator, mock_storage) -> None:
    mock_storage.enabled = False
    coordinator.engine = _engine()
    cover = CoverConfig(entity_id=COVER, name="Salon")
    assert coordinator._pending_rule(cover, CoverStatus.AUTO, None)["pending_rule_id"] == "nuit"


def test_none_when_a_safety_rule_drives(coordinator, mock_storage) -> None:
    mock_storage.enabled = True
    coordinator.engine = _engine()
    safety = CoverTarget(position=100, rule_id="feu", rule_name="Feu", safety=True)
    cover = CoverConfig(entity_id=COVER, name="Salon")
    assert coordinator._pending_rule(cover, CoverStatus.PAUSED, safety) == {}


def test_none_when_no_rule_matches(coordinator, mock_storage) -> None:
    mock_storage.enabled = True
    coordinator.engine = _engine(full=None)
    cover = CoverConfig(entity_id=COVER, name="Salon")
    assert coordinator._pending_rule(cover, CoverStatus.MANUAL, None) == {}


def test_pending_do_nothing_rule(coordinator, mock_storage) -> None:
    mock_storage.enabled = True
    coordinator.engine = _engine(full=CoverTarget(position=None, rule_id="hold", rule_name="Hold"))
    cover = CoverConfig(entity_id=COVER, name="Salon")
    assert coordinator._pending_rule(cover, CoverStatus.MANUAL, None) == {
        "pending_rule_id": "hold", "pending_target_position": None,
    }


@pytest.mark.asyncio
async def test_update_cycle_shows_but_does_not_command(coordinator, mock_storage, mock_hass) -> None:
    """Manual cover: no target, no active rule, no log, no command; pending rule in the data."""
    mock_storage.enabled = True
    mock_storage.covers = {COVER: CoverConfig(entity_id=COVER, name="Salon", auto_enabled=False)}
    mock_storage.get_cover_raw.return_value = {"auto_enabled": False}
    mock_storage.rules = {"nuit": SimpleNamespace(name="Fermer la Nuit")}
    coordinator._cover_states[COVER] = CoverStatus.MANUAL
    coordinator.engine = _engine()
    coordinator.engine.async_prepare_ha_conditions = AsyncMock(return_value=False)
    coordinator.log_storage = MagicMock()
    with patch.object(coordinator, "_sync_cover_statuses"), \
            patch.object(coordinator, "_log_scenario_change"), \
            patch.object(coordinator, "async_apply_positions", AsyncMock()):
        result = await coordinator._async_update_data()
    data = result["covers"][COVER]
    assert data["target_position"] is None and data["matching_rule_id"] is None
    assert data["pending_rule_id"] == "nuit" and data["pending_target_position"] == 0
    assert result["active_rules"] == {}
    coordinator.log_storage.add_entry.assert_not_called()
    mock_hass.services.async_call.assert_not_called()
    live = coordinator.get_cover_live(COVER)
    assert live["pending_rule_name"] == "Fermer la Nuit" and live["pending_target_position"] == 0
    assert coordinator.get_live_cover_data()[COVER]["pending_rule_id"] == "nuit"


def test_sensor_attributes(coordinator) -> None:
    from custom_components.cover_automatic.sensor import CoverRuleSensor
    sensor = CoverRuleSensor.__new__(CoverRuleSensor)
    with patch.object(CoverRuleSensor, "_live", new={
        "rule_id": None, "target_position": None, "safety": False,
        "pending_rule_name": "Fermer la Nuit", "pending_target_position": 0,
    }):
        attrs = sensor.extra_state_attributes
    assert attrs["pending_rule"] == "Fermer la Nuit" and attrs["pending_target_position"] == 0

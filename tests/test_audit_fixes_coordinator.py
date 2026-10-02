"""Regression tests for audit fixes in the coordinator."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cover_automatic.models import CoverStatus
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401


def _cover(**extra) -> dict:
    return {
        "auto_enabled": True, "lock_sensor": "binary_sensor.window", "lock_position": 100,
        "vent_sensor": None, "vent_position": 30, "inverted": False, **extra,
    }


def _setup(mock_hass, mock_storage, cover_raw: dict, states: dict[str, str]) -> None:
    mock_storage._data = {"covers": {"cover.test": cover_raw}, "rules": {}}
    mock_storage.get_cover_raw = MagicMock(return_value=cover_raw)
    mock_hass.states.get = MagicMock(
        side_effect=lambda eid: MockState(states[eid], {"current_position": 100}) if eid in states else None
    )


# ---------------------------------------------------------------------------
# 2. Unavailable lock/vent sensor keeps the protective status
# ---------------------------------------------------------------------------

class TestUnavailableContactSensor:
    @pytest.mark.parametrize("sensor_state", ["unavailable", "unknown", None])
    def test_locked_cover_not_unlocked(self, coordinator, mock_hass, mock_storage, sensor_state) -> None:
        states = {"binary_sensor.window": sensor_state} if sensor_state else {}
        _setup(mock_hass, mock_storage, _cover(), states)
        if sensor_state is None:
            # A missing entity is only "unknown" during the startup
            # grace period (afterwards: no sensor, see test_coordinator_fixes)
            import time
            coordinator._startup_time = time.monotonic()
        coordinator._cover_states["cover.test"] = CoverStatus.LOCKED
        with patch.object(coordinator, "_unlock_cover") as unlock:
            coordinator._sync_cover_statuses()
        unlock.assert_not_called()
        assert coordinator._cover_states["cover.test"] == CoverStatus.LOCKED

    def test_locked_cover_not_moved_to_venting(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(mock_hass, mock_storage, _cover(vent_sensor="binary_sensor.vent"),
               {"binary_sensor.window": "unavailable", "binary_sensor.vent": "on"})
        coordinator._cover_states["cover.test"] = CoverStatus.LOCKED
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.test"] == CoverStatus.LOCKED

    def test_venting_cover_kept(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(mock_hass, mock_storage, _cover(lock_sensor=None, vent_sensor="binary_sensor.vent"),
               {"binary_sensor.vent": "unavailable"})
        coordinator._cover_states["cover.test"] = CoverStatus.VENTING
        with patch.object(coordinator, "_unlock_cover") as unlock:
            coordinator._sync_cover_statuses()
        unlock.assert_not_called()
        assert coordinator._cover_states["cover.test"] == CoverStatus.VENTING

    def test_auto_cover_not_locked(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(mock_hass, mock_storage, _cover(), {"binary_sensor.window": "unavailable"})
        coordinator._cover_states["cover.test"] = CoverStatus.AUTO
        with patch.object(coordinator, "_lock_cover") as lock:
            coordinator._sync_cover_statuses()
        lock.assert_not_called()
        assert coordinator._cover_states["cover.test"] == CoverStatus.AUTO

    def test_closed_sensor_still_unlocks(self, coordinator, mock_hass, mock_storage) -> None:
        _setup(mock_hass, mock_storage, _cover(), {"binary_sensor.window": "off"})
        coordinator._cover_states["cover.test"] = CoverStatus.LOCKED
        with patch.object(coordinator, "_unlock_cover") as unlock:
            coordinator._sync_cover_statuses()
        unlock.assert_called_once_with("cover.test")


# ---------------------------------------------------------------------------
# 3. Status re-checked after the stagger sleep
# ---------------------------------------------------------------------------

class TestStaggerRecheck:
    def _prepare(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage.command_stagger = 0.5
        mock_storage.enabled = True
        mock_storage.get_cover_raw = MagicMock(side_effect=lambda eid: {
            "entity_id": eid, "inverted": False, "supports_tilt": False,
            "min_position_change": 0, "min_time_between_changes": 0,
        })
        mock_hass.states.get = MagicMock(return_value=MockState("open", {"current_position": 100}))
        coordinator.data = {"covers": {"cover.a": {"target_position": 50}, "cover.b": {"target_position": 50}}}
        coordinator._cover_states = {"cover.a": CoverStatus.AUTO, "cover.b": CoverStatus.AUTO}

    @pytest.mark.asyncio
    async def test_paused_during_stagger_skipped(self, coordinator, mock_hass, mock_storage) -> None:
        self._prepare(coordinator, mock_hass, mock_storage)

        async def sleep(_delay):
            coordinator._cover_states["cover.b"] = CoverStatus.PAUSED

        with patch("asyncio.sleep", side_effect=sleep):
            await coordinator.async_apply_positions()
        assert mock_hass.services.async_call.call_count == 1
        assert mock_hass.services.async_call.call_args[0][2]["entity_id"] == "cover.a"
        assert "cover.b" not in coordinator._last_positions
        assert "cover.b" not in coordinator._pending_settle

    @pytest.mark.asyncio
    async def test_wind_during_stagger_skipped(self, coordinator, mock_hass, mock_storage) -> None:
        self._prepare(coordinator, mock_hass, mock_storage)

        async def sleep(_delay):
            coordinator._wind_protected = True

        with patch("asyncio.sleep", side_effect=sleep):
            await coordinator.async_apply_positions()
        assert mock_hass.services.async_call.call_count == 1

    @pytest.mark.asyncio
    async def test_unchanged_status_still_sent(self, coordinator, mock_hass, mock_storage) -> None:
        self._prepare(coordinator, mock_hass, mock_storage)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await coordinator.async_apply_positions()
        assert mock_hass.services.async_call.call_count == 2


# ---------------------------------------------------------------------------
# 13. A managed cover used by a rule condition triggers a refresh
# ---------------------------------------------------------------------------

class TestManagedCoverRuleEntity:
    def _event(self, entity_id: str):
        event = MagicMock()
        event.data = {"entity_id": entity_id, "old_state": MockState("open"), "new_state": MockState("closed")}
        return event

    def test_refresh_when_referenced(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage._data = {
            "covers": {"cover.a": {}},
            "rules": {"r": {"conditions": [{"type": "state_is", "params": {"entity_id": "cover.a"}}]}},
        }
        coordinator.engine = MagicMock()
        coordinator.engine.ha_condition_entities.return_value = set()
        with patch.object(coordinator, "_handle_cover_state_change") as handler:
            coordinator._async_on_state_change(self._event("cover.a"))
        handler.assert_called_once()
        mock_hass.async_create_task.assert_called_once()
        coordinator.async_request_refresh.assert_called_once()

    def test_refresh_when_in_ha_condition(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage._data = {"covers": {"cover.a": {}}, "rules": {}}
        coordinator.engine = MagicMock()
        coordinator.engine.ha_condition_entities.return_value = {"cover.a"}
        with patch.object(coordinator, "_handle_cover_state_change"):
            coordinator._async_on_state_change(self._event("cover.a"))
        mock_hass.async_create_task.assert_called_once()

    def test_no_refresh_when_not_referenced(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage._data = {"covers": {"cover.a": {}}, "rules": {}}
        coordinator.engine = MagicMock()
        coordinator.engine.ha_condition_entities.return_value = set()
        with patch.object(coordinator, "_handle_cover_state_change"):
            coordinator._async_on_state_change(self._event("cover.a"))
        mock_hass.async_create_task.assert_not_called()

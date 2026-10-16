"""Coordinator edge cases: unavailable sensors, stagger, tilt, wind exit, cover attributes."""
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


class TestUnavailableContactSensor:
    @pytest.mark.parametrize("sensor_state", ["unavailable", "unknown", None])
    def test_locked_cover_not_unlocked(self, coordinator, mock_hass, mock_storage, sensor_state) -> None:
        states = {"binary_sensor.window": sensor_state} if sensor_state else {}
        _setup(mock_hass, mock_storage, _cover(), states)
        if sensor_state is None:
            # A missing entity is only "unknown" during the startup
            # grace period (afterwards: no sensor, see test_coordinator_status)
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


class TestTiltBelowHysteresis:
    @pytest.mark.asyncio
    async def test_tilt_sent_when_position_within_min_change(self, coordinator, mock_hass, mock_storage) -> None:
        coordinator.data = {"covers": {"cover.t": {"status": "auto", "target_position": 50,
                                                   "target_tilt_position": 80, "matching_rule_id": "b"}}}
        mock_storage.get_cover_raw.return_value = {"min_position_change": 5, "min_time_between_changes": 0,
                                                   "inverted": False, "supports_tilt": True}
        mock_hass.states.get.return_value = MockState("open", {"current_position": 49, "current_tilt_position": 0,
                                                               "supported_features": 255})
        coordinator._last_positions["cover.t"] = 49
        coordinator._last_tilt_positions["cover.t"] = 0
        with patch.object(coordinator, "_schedule_tilt") as st:
            await coordinator.async_apply_positions()
        st.assert_called_once_with("cover.t", 80, 0)
        assert coordinator._hysteresis_info["cover.t"] == "position"
        mock_hass.services.async_call.assert_not_called()  # no position command

    @pytest.mark.asyncio
    async def test_tilt_not_resent_when_already_there(self, coordinator, mock_hass, mock_storage) -> None:
        coordinator.data = {"covers": {"cover.t": {"status": "auto", "target_position": 50,
                                                   "target_tilt_position": 80, "matching_rule_id": "b"}}}
        mock_storage.get_cover_raw.return_value = {"min_position_change": 5, "min_time_between_changes": 0,
                                                   "inverted": False, "supports_tilt": True}
        mock_hass.states.get.return_value = MockState("open", {"current_position": 49, "current_tilt_position": 80,
                                                               "supported_features": 255})
        coordinator._last_positions["cover.t"] = 49
        with patch.object(coordinator, "_schedule_tilt") as st:
            await coordinator.async_apply_positions()
        st.assert_not_called()


class TestWindExit:
    def test_wind_exit_bypasses_min_time(self, coordinator, mock_hass, mock_storage) -> None:
        raw = {"auto_enabled": True, "inverted": False}
        mock_storage._data = {"covers": {"cover.t": raw}}
        mock_storage.get_cover_raw.return_value = raw
        coordinator._cover_states["cover.t"] = CoverStatus.WIND_PROTECTED
        mock_hass.states.get.side_effect = lambda e: MockState("open", {"current_position": 100})
        coordinator._deactivate_wind_protection()
        assert "cover.t" in coordinator._post_protective_exit


class TestStatusOfDisabledCover:
    @pytest.mark.parametrize("live", [CoverStatus.LOCKED, CoverStatus.WIND_PROTECTED])
    def test_protective_status_shown(self, coordinator, mock_storage, live) -> None:
        mock_storage.get_cover_raw.return_value = {"auto_enabled": False}
        coordinator._cover_states["cover.t"] = live
        assert coordinator.get_cover_status("cover.t") == live

    @pytest.mark.parametrize("live", [CoverStatus.AUTO, CoverStatus.PAUSED, CoverStatus.VENTING])
    def test_otherwise_manual(self, coordinator, mock_storage, live) -> None:
        mock_storage.get_cover_raw.return_value = {"auto_enabled": False}
        coordinator._cover_states["cover.t"] = live
        assert coordinator.get_cover_status("cover.t") == CoverStatus.MANUAL


class TestPositionWithoutAttribute:
    @pytest.mark.parametrize(("state", "expected"), [("open", 100), ("closed", 0), ("opening", None)])
    def test_open_close_only_cover(self, coordinator, mock_hass, mock_storage, state, expected) -> None:
        mock_storage.get_cover_raw.return_value = {"inverted": False}
        mock_hass.states.get.return_value = MockState(state, {})
        assert coordinator._get_current_position("cover.t") == expected

    def test_inverted(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage.get_cover_raw.return_value = {"inverted": True}
        mock_hass.states.get.return_value = MockState("open", {})
        assert coordinator._get_current_position("cover.t") == 0


class TestInfiniteWindSpeed:
    @pytest.mark.parametrize("value", ["inf", "-inf", "nan"])
    def test_not_a_reading(self, coordinator, mock_hass, mock_storage, value) -> None:
        mock_storage.wind_sensor = "sensor.wind"
        mock_hass.states.get.return_value = MockState(value, {})
        assert coordinator._get_wind_speed() is None


class TestScheduleRefresh:
    def test_task_owned_by_entry(self, coordinator, mock_hass) -> None:
        entry = MagicMock()
        coordinator.config_entry = entry
        coordinator._schedule_refresh()
        entry.async_create_background_task.assert_called_once()
        assert entry.async_create_background_task.call_args.args[0] is mock_hass
        entry.async_create_background_task.call_args.args[1].close()
        mock_hass.async_create_task.assert_not_called()

    def test_without_entry(self, coordinator, mock_hass) -> None:
        coordinator.config_entry = None
        coordinator._schedule_refresh()
        mock_hass.async_create_task.assert_called_once()
        mock_hass.async_create_task.call_args.args[0].close()


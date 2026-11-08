"""Home Assistant shutdown: no cover command while integrations disconnect.

While Home Assistant stops, the other integrations disconnect and report
false states (an Apple TV "off" while it is still playing). A rule that
stops matching must not move a cover during those last seconds.
"""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from custom_components.cover_automatic.models import CoverStatus
from tests.test_coordinator import (  # noqa: F401 -- pytest fixtures
    MockState,
    coordinator,
    mock_hass,
    mock_storage,
)

COVER = "cover.salon"


class TestStopListener:
    @pytest.mark.asyncio
    async def test_setup_listens_for_the_stop(self, coordinator, mock_hass) -> None:
        with patch.object(coordinator, "_restore_cover_states"), \
                patch.object(coordinator, "_async_setup_default_scenarios", AsyncMock()), \
                patch.object(coordinator, "_setup_state_tracking"):
            await coordinator.async_setup()
        mock_hass.bus.async_listen_once.assert_called_once_with(
            EVENT_HOMEASSISTANT_STOP, coordinator._async_on_ha_stop)
        assert coordinator._unsub_ha_stop is mock_hass.bus.async_listen_once.return_value

    def test_stop_suspends_and_logs(self, coordinator) -> None:
        coordinator.log_storage = MagicMock()
        tilt = MagicMock()
        tilt.done.return_value = False
        coordinator._tilt_tasks = {COVER: tilt}
        coordinator._unsub_ha_stop = MagicMock()
        with patch.object(coordinator, "_cancel_wind_tasks") as wind:
            coordinator._async_on_ha_stop(SimpleNamespace())
        assert coordinator._ha_stopping is True
        assert coordinator._unsub_ha_stop is None
        wind.assert_called_once()
        tilt.cancel.assert_called_once()
        args = coordinator.log_storage.add_entry.call_args.args
        assert args[1] is None and args[3] == {"key": "ha_stopping"}


class TestWhileStopping:
    def test_state_changes_are_ignored(self, coordinator, mock_storage) -> None:
        """The Apple TV reported "off" by its disconnecting integration."""
        mock_storage._data["covers"] = {COVER: {}}
        coordinator._ha_stopping = True
        event = SimpleNamespace(data={
            "entity_id": "media_player.apple_tv",
            "old_state": MockState("playing"), "new_state": MockState("off"),
        })
        with patch.object(coordinator, "_schedule_refresh") as refresh:
            coordinator._async_on_state_change(event)
        refresh.assert_not_called()

    def test_cover_reports_are_ignored(self, coordinator, mock_storage) -> None:
        mock_storage._data["covers"] = {COVER: {}}
        coordinator._ha_stopping = True
        event = SimpleNamespace(data={
            "entity_id": COVER,
            "old_state": MockState("closed", {"current_position": 0}),
            "new_state": MockState("unavailable"),
        })
        with patch.object(coordinator, "_handle_cover_state_change") as handle:
            coordinator._async_on_state_change(event)
        handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_neither_evaluates_nor_applies(self, coordinator) -> None:
        coordinator._ha_stopping = True
        coordinator.data = {"covers": {COVER: {"status": "auto", "target_position": 0}}}
        coordinator.engine = MagicMock()
        with patch.object(coordinator, "async_apply_positions", AsyncMock()) as apply:
            result = await coordinator._async_update_data()
        apply.assert_not_awaited()
        coordinator.engine.evaluate_cover.assert_not_called()
        assert result is coordinator.data

    @pytest.mark.asyncio
    async def test_no_position_command(self, coordinator, mock_hass) -> None:
        coordinator._ha_stopping = True
        await coordinator._position_call(COVER, 100)
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_delayed_tilt(self, coordinator, mock_hass) -> None:
        coordinator._ha_stopping = True
        await coordinator._send_tilt_delayed(COVER, 50, 0)
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_integration_reload(self, coordinator, mock_hass) -> None:
        coordinator._ha_stopping = True
        coordinator._reload_waiting = {COVER: "velux1"}
        mock_hass.config_entries.async_reload = AsyncMock()
        with patch("custom_components.cover_automatic.reload.RELOAD_GATHER_DELAY", 0):
            await coordinator._async_reload_integration("velux1")
        mock_hass.config_entries.async_reload.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_apply_cycle_sends_nothing(self, coordinator, mock_storage, mock_hass) -> None:
        """A cycle already running when the stop begins sends no command."""
        mock_storage.get_cover_raw.return_value = {
            "min_position_change": 1, "min_time_between_changes": 0, "inverted": False,
        }
        coordinator._cover_states[COVER] = CoverStatus.AUTO
        coordinator._last_positions[COVER] = 0
        coordinator.data = {"covers": {COVER: {"status": "auto", "target_position": 100,
                                               "matching_rule_id": "jour"}}}
        mock_hass.states.get.return_value = MockState("closed", {"current_position": 0})
        coordinator._ha_stopping = True
        await coordinator.async_apply_positions()
        await asyncio.sleep(0)
        mock_hass.services.async_call.assert_not_called()

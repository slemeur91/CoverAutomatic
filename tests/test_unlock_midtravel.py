"""Window closed while the cover is still moving to its lock position.

Real case (office cover): window opened -> lock command to 100 %; window
closed 20 s later while the cover was at 34 %; the cover reached 100 % and
the next cycle paused it as a "manual command".
"""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.cover_automatic.models import CoverStatus
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401
from tests.test_coordinator_robustness import TIME, _cover, _raw, _states, _use_covers


def _locked_mid_travel(coordinator, mock_hass, mock_storage, position: int) -> None:
    _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
    mock_storage.covers = {"cover.t": _cover()}
    coordinator._cover_states["cover.t"] = CoverStatus.LOCKED
    coordinator._pre_lock_states["cover.t"] = CoverStatus.AUTO
    # Lock command sent at t=1000 s towards 100 %
    coordinator._last_positions["cover.t"] = 100
    coordinator._last_command_time["cover.t"] = 1000.0
    coordinator._pending_settle.add("cover.t")
    mock_hass.states.get.side_effect = _states({
        "binary_sensor.w": MockState("off"),
        "cover.t": MockState("open", {"current_position": position}),
    })


class TestUnlockDuringLockMove:
    def test_expected_position_stays_commanded(self, coordinator, mock_hass, mock_storage) -> None:
        _locked_mid_travel(coordinator, mock_hass, mock_storage, 34)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 1020.0  # still settling
            coordinator._unlock_cover("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        assert coordinator._last_positions["cover.t"] == 100

    def test_settled_unlock_takes_current_position(self, coordinator, mock_hass, mock_storage) -> None:
        _locked_mid_travel(coordinator, mock_hass, mock_storage, 100)
        coordinator._last_positions["cover.t"] = 100
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("off"),
            "cover.t": MockState("open", {"current_position": 80}),
        })
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 5000.0  # long after the command
            coordinator._unlock_cover("cover.t")
        assert coordinator._last_positions["cover.t"] == 80

    @pytest.mark.asyncio
    async def test_end_of_lock_move_is_not_manual(self, coordinator, mock_hass, mock_storage) -> None:
        _locked_mid_travel(coordinator, mock_hass, mock_storage, 34)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 1020.0
            coordinator._unlock_cover("cover.t")
        # The cover finishes its lock move, the rule wants 0 %
        coordinator.data = {"covers": {"cover.t": {"target_position": 0}}}
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("off"),
            "cover.t": MockState("open", {"current_position": 100}),
        })
        with patch(TIME) as mock_time, patch.object(coordinator, "pause_cover") as pause:
            mock_time.monotonic.return_value = 1031.0  # just after the settle time
            await coordinator.async_apply_positions()
        pause.assert_not_called()
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        mock_hass.services.async_call.assert_called_once_with(
            "cover", "set_cover_position", {"entity_id": "cover.t", "position": 0}, blocking=False)

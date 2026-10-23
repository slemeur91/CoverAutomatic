"""Covers behind a gateway with sparse reports (Velux KLF 200).

Such gateways report neither opening/closing for moves started elsewhere
(remote, vendor app) nor regular positions, and queue the commands of
several covers. Sequences taken from real histories.
"""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.cover_automatic.models import CoverConfig, CoverStatus
from tests.test_coordinator import (  # noqa: F401 -- pytest fixtures
    MockState,
    coordinator,
    mock_hass,
    mock_storage,
)

MOD = "custom_components.cover_automatic.coordinator_common"
ID = "cover.cuisine"


def _cover(coordinator, mock_storage, *, expected, travel=None, safety=False, target=None):
    cover = CoverConfig(entity_id=ID, name="Cuisine")
    mock_storage.covers = {ID: cover}
    mock_storage.get_cover_raw.return_value = {
        "min_position_change": 1, "min_time_between_changes": 180, "inverted": False,
        "last_position_change": None, "measured_travel_time": travel,
    }
    coordinator._cover_states[ID] = CoverStatus.AUTO
    coordinator._last_positions[ID] = expected
    if target is not None:
        coordinator.data = {"covers": {ID: {
            "status": "auto", "target_position": target, "matching_rule_id": "nuit", "safety": safety}}}
    return cover


def _state(state, position):
    return MockState(state, {"current_position": position})


class TestManualMoveFromEndStop:
    """05:01:57: remote opening, the gateway first reports 'open' at 2 %."""

    def test_closed_to_open_at_two_percent_pauses(self, coordinator, mock_storage) -> None:
        _cover(coordinator, mock_storage, expected=0)
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 5000.0
            coordinator._handle_cover_state_change(ID, _state("closed", 0), _state("open", 2))
        pause.assert_called_once()

    def test_closed_to_open_even_at_one_percent(self, coordinator, mock_storage) -> None:
        """The state change alone tells the move, whatever the first position."""
        _cover(coordinator, mock_storage, expected=0)
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 5000.0
            coordinator._handle_cover_state_change(ID, _state("closed", 0), _state("open", 1))
        pause.assert_called_once()

    def test_open_to_closed_pauses(self, coordinator, mock_storage) -> None:
        _cover(coordinator, mock_storage, expected=100)
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 5000.0
            coordinator._handle_cover_state_change(ID, _state("open", 100), _state("closed", 99))
        pause.assert_called_once()

    def test_own_move_arriving_after_settle_is_not_manual(self, coordinator, mock_storage) -> None:
        """Our closed -> open move reported at its target: no pause."""
        _cover(coordinator, mock_storage, expected=100)
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 5000.0
            coordinator._handle_cover_state_change(ID, _state("closed", 0), _state("open", 100))
        pause.assert_not_called()


class TestTolerance:
    """A 2 % deviation is now a manual move (it was ignored before)."""

    @pytest.mark.parametrize(("position", "paused"), [(52, True), (48, True), (51, False), (50, False)])
    def test_two_percent_counts(self, coordinator, mock_storage, position, paused) -> None:
        _cover(coordinator, mock_storage, expected=50)
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 5000.0
            coordinator._handle_cover_state_change(ID, _state("open", 50), _state("open", position))
        assert pause.called is paused

    @pytest.mark.asyncio
    async def test_apply_cycle_uses_the_same_tolerance(self, coordinator, mock_storage, mock_hass) -> None:
        _cover(coordinator, mock_storage, expected=50, target=50)
        mock_hass.states.get.return_value = _state("open", 52)
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 5000.0
            await coordinator.async_apply_positions()
        pause.assert_called_once()


class TestNoCommandWhileMovingOnItsOwn:
    """Never send a cover back while it is moving without us."""

    @pytest.mark.asyncio
    async def test_waits_after_an_unexplained_move(self, coordinator, mock_storage, mock_hass) -> None:
        _cover(coordinator, mock_storage, expected=0, target=0)
        mock_hass.states.get.return_value = _state("open", 1)
        coordinator._position_changed_at = {ID: 4992.0}  # moved 8 s ago
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 5000.0
            await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_not_awaited()
        pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_commands_once_still(self, coordinator, mock_storage, mock_hass) -> None:
        _cover(coordinator, mock_storage, expected=0, target=0)
        mock_hass.states.get.return_value = _state("open", 1)
        coordinator._position_changed_at = {ID: 4950.0}  # still for 50 s (> 30 s settle)
        with patch(f"{MOD}.time_mod") as t:
            t.monotonic.return_value = 5000.0
            await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_awaited_once()
        assert mock_hass.services.async_call.await_args.args[2]["position"] == 0

    @pytest.mark.asyncio
    async def test_safety_rule_does_not_wait(self, coordinator, mock_storage, mock_hass) -> None:
        _cover(coordinator, mock_storage, expected=0, target=100, safety=True)
        mock_hass.states.get.return_value = _state("open", 1)
        coordinator._position_changed_at = {ID: 4992.0}
        with patch(f"{MOD}.time_mod") as t:
            t.monotonic.return_value = 5000.0
            await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_awaited_once()
        assert mock_hass.services.async_call.await_args.args[2]["position"] == 100


class TestSlowQueuedMove:
    """22/10 08:42: the gateway moves this cover after two others (69 s instead
    of the learned 37 s) and reports a single position on the way."""

    def _setup(self, coordinator, mock_storage, mock_hass):
        _cover(coordinator, mock_storage, expected=100, travel=36.6, target=100)
        coordinator._pending_settle.add(ID)
        coordinator._last_command_time[ID] = 1000.0
        coordinator._last_sent_target[ID] = 100
        coordinator._move_start[ID] = (1000.0, 0, 100)

    @pytest.mark.asyncio
    async def test_no_false_pause(self, coordinator, mock_storage, mock_hass) -> None:
        self._setup(coordinator, mock_storage, mock_hass)
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            # 31 s: first report, on the way to our target (no 'opening')
            t.monotonic.return_value = 1031.0
            coordinator._handle_cover_state_change(ID, _state("closed", 0), _state("open", 87))
            assert coordinator._last_command_time[ID] == 1031.0  # settle restarted
            # 50 s: the old settle time (41.6 s) is over, the cover still at 87 %
            mock_hass.states.get.return_value = _state("open", 87)
            t.monotonic.return_value = 1050.0
            await coordinator.async_apply_positions()
            # 69 s: arrival
            t.monotonic.return_value = 1069.0
            coordinator._handle_cover_state_change(ID, _state("open", 87), _state("open", 100))
            mock_hass.states.get.return_value = _state("open", 100)
            t.monotonic.return_value = 1120.0
            await coordinator.async_apply_positions()
        pause.assert_not_called()
        mock_hass.services.async_call.assert_not_awaited()
        assert ID not in coordinator._pending_settle

    def test_report_moving_away_does_not_extend(self, coordinator, mock_storage, mock_hass) -> None:
        """A counter-order (moving away from our target) keeps the settle time."""
        self._setup(coordinator, mock_storage, mock_hass)
        with patch(f"{MOD}.time_mod") as t:
            t.monotonic.return_value = 1020.0
            coordinator._handle_cover_state_change(ID, _state("open", 60), _state("open", 40))
        assert coordinator._last_command_time[ID] == 1000.0


class TestPauseDiagnostics:
    """19/10 08:18: the gateway announces the target 2 s after the command,
    then reports the cover closed. The pause says what was seen."""

    def test_details_in_activity_log_and_logbook(self, coordinator, mock_storage, mock_hass) -> None:
        from unittest.mock import MagicMock

        cover = _cover(coordinator, mock_storage, expected=100, travel=31.5)
        coordinator.log_storage = MagicMock()
        mock_storage.pause_duration = 90
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "_logbook") as logbook:
            t.monotonic.return_value = 1000.0
            coordinator._position_call(ID, 100).close()
            coordinator._last_command_time[ID] = 1000.0
            t.monotonic.return_value = 1002.0
            coordinator._handle_cover_state_change(ID, _state("closed", 0), _state("open", 100))
            t.monotonic.return_value = 1040.0
            coordinator._handle_cover_state_change(ID, _state("open", 100), _state("closed", 0))
        assert coordinator._cover_states[ID] == CoverStatus.PAUSED
        data = coordinator.log_storage.add_entry.call_args.args[3]
        assert data["to"] == "paused"
        assert (data["expected"], data["actual"]) == (100, 0)
        assert (data["first_position"], data["first_after"]) == (100, 2.0)
        assert "first report 100 % 2.0 s after the last command" in logbook.call_args.args[0]
        assert cover.entity_id == ID

    def test_new_command_resets_the_first_report(self, coordinator, mock_storage) -> None:
        _cover(coordinator, mock_storage, expected=0)
        with patch(f"{MOD}.time_mod") as t:
            t.monotonic.return_value = 1000.0
            coordinator._position_call(ID, 100).close()
            t.monotonic.return_value = 1005.0
            coordinator._record_motion(ID, _state("closed", 0), _state("open", 40))
            assert coordinator._first_report[ID] == {"position": 40, "after": 5.0}
            t.monotonic.return_value = 2000.0
            coordinator._position_call(ID, 0).close()
        assert ID not in coordinator._first_report

    def test_logbook_suffix_french(self) -> None:
        from unittest.mock import MagicMock

        from custom_components.cover_automatic import i18n

        hass = MagicMock()
        hass.config.language = "fr"
        text = i18n.pause_details(hass, {"expected": 100, "actual": 0, "first_position": 100, "first_after": 2.5})
        assert text == " : attendu 100 %, lu 0 % ; première position annoncée 100 % 2,5 s après le dernier ordre"
        assert i18n.pause_details(hass, None) == ""

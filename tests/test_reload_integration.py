"""Integration reload for covers that no longer react (cover option reload_on_no_move).

The integration stops executing commands without any error: the cover
neither moves nor changes state. The first ignored command reloads the
integration once for all its covers, then they are commanded again.
"""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cover_automatic.models import CoverConfig, CoverStatus
from tests.test_coordinator import (  # noqa: F401 -- pytest fixtures
    MockState,
    coordinator,
    mock_hass,
    mock_storage,
)

MOD = "custom_components.cover_automatic.coordinator_common"
RELOAD = "custom_components.cover_automatic.reload"
A, B, OTHER = "cover.cuisine", "cover.salon", "cover.garage"


def _setup(coordinator, mock_storage, mock_hass, *, option=True, reloadable=True):
    raw = {
        "min_position_change": 1, "min_time_between_changes": 180, "inverted": False,
        "last_position_change": None, "measured_travel_time": 20, "reload_on_no_move": option,
    }
    mock_storage.covers = {e: CoverConfig(entity_id=e, name=e.split(".")[1].title()) for e in (A, B, OTHER)}
    mock_storage.get_cover_raw.side_effect = lambda e: dict(raw)
    mock_storage.enabled = True
    for e in (A, B, OTHER):
        coordinator._cover_states[e] = CoverStatus.AUTO
    coordinator.data = {"covers": {e: {"status": "auto", "target_position": 100, "matching_rule_id": "jour"}
                                   for e in (A, B, OTHER)}}
    entry = SimpleNamespace(entry_id="velux1", domain="velux", title="Velux", supports_unload=reloadable)
    mock_hass.config_entries.async_get_entry.side_effect = lambda eid: entry if eid == "velux1" else None
    mock_hass.config_entries.async_reload = AsyncMock(return_value=True)
    registry = MagicMock()
    registry.async_get.side_effect = lambda e: SimpleNamespace(config_entry_id="velux1" if e in (A, B) else "zw")
    mock_hass.states.get.side_effect = lambda e: MockState("closed", {"current_position": 0})
    coordinator.log_storage = MagicMock()
    return registry


def _commanded(coordinator, entity_id, at=1000.0):
    """Our command 0 -> 100 % sent at `at`, still pending its settle time."""
    coordinator._last_positions[entity_id] = 100
    coordinator._last_sent_target[entity_id] = 100
    coordinator._last_command_time[entity_id] = at
    coordinator._move_start[entity_id] = (at, 0, 100)
    coordinator._pending_settle.add(entity_id)


class TestRequest:
    @pytest.mark.asyncio
    async def test_first_ignored_command_requests_a_reload(self, coordinator, mock_storage, mock_hass) -> None:
        registry = _setup(coordinator, mock_storage, mock_hass)
        coordinator.data["covers"] = {A: coordinator.data["covers"][A]}
        _commanded(coordinator, A)
        with patch(f"{RELOAD}.er.async_get", return_value=registry), \
                patch(f"{MOD}.time_mod") as t, \
                patch.object(coordinator, "_async_reload_integration", MagicMock()) as run, \
                patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 1100.0  # settle time over, still at 0 %
            await coordinator.async_apply_positions()
            # Next cycles: neither paused nor commanded while waiting
            t.monotonic.return_value = 1160.0
            await coordinator.async_apply_positions()
        run.assert_called_once_with("velux1")
        assert coordinator._reload_waiting == {A: "velux1"}
        pause.assert_not_called()
        mock_hass.services.async_call.assert_not_awaited()
        data = coordinator.log_storage.add_entry.call_args.args[3]
        assert data == {"key": "reload_requested", "integration": "Velux"}

    @pytest.mark.asyncio
    async def test_option_off_resends_as_before(self, coordinator, mock_storage, mock_hass) -> None:
        registry = _setup(coordinator, mock_storage, mock_hass, option=False)
        _commanded(coordinator, A)
        with patch(f"{RELOAD}.er.async_get", return_value=registry), patch(f"{MOD}.time_mod") as t:
            t.monotonic.return_value = 1100.0
            await coordinator.async_apply_positions()
        assert not getattr(coordinator, "_reload_waiting", None)
        mock_hass.config_entries.async_reload.assert_not_called()
        assert coordinator._lost_command_retries == {A: 1}

    @pytest.mark.asyncio
    async def test_not_reloadable_resends(self, coordinator, mock_storage, mock_hass) -> None:
        registry = _setup(coordinator, mock_storage, mock_hass, reloadable=False)
        _commanded(coordinator, A)
        with patch(f"{RELOAD}.er.async_get", return_value=registry), patch(f"{MOD}.time_mod") as t:
            t.monotonic.return_value = 1100.0
            await coordinator.async_apply_positions()
        assert not getattr(coordinator, "_reload_waiting", None)
        assert coordinator._lost_command_retries == {A: 1}

    @pytest.mark.asyncio
    async def test_cooldown_resends(self, coordinator, mock_storage, mock_hass) -> None:
        registry = _setup(coordinator, mock_storage, mock_hass)
        _commanded(coordinator, A)
        coordinator._reload_last = {"velux1": 900.0}  # reloaded 200 s ago
        with patch(f"{RELOAD}.er.async_get", return_value=registry), patch(f"{MOD}.time_mod") as t:
            t.monotonic.return_value = 1100.0
            await coordinator.async_apply_positions()
        assert not getattr(coordinator, "_reload_waiting", None)
        assert coordinator._lost_command_retries == {A: 1}

    @pytest.mark.asyncio
    async def test_cover_moved_by_someone_is_not_reloaded(self, coordinator, mock_storage, mock_hass) -> None:
        """A counter-order back to the start position is no ignored command."""
        registry = _setup(coordinator, mock_storage, mock_hass)
        _commanded(coordinator, A)
        coordinator._moved_since_command = {A}
        with patch(f"{RELOAD}.er.async_get", return_value=registry), patch(f"{MOD}.time_mod") as t, \
                patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 1100.0
            await coordinator.async_apply_positions()
        assert not getattr(coordinator, "_reload_waiting", None)
        pause.assert_called_once()


class TestWhileWaiting:
    def test_reports_without_move_are_ignored(self, coordinator, mock_storage, mock_hass) -> None:
        _setup(coordinator, mock_storage, mock_hass)
        _commanded(coordinator, A)
        coordinator._reload_waiting = {A: "velux1"}
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 1110.0
            coordinator._handle_cover_state_change(
                A, MockState("closed", {"current_position": 0}), MockState("closed", {"current_position": 0}))
        pause.assert_not_called()
        assert A in coordinator._reload_waiting

    def test_cover_moved_leaves_the_request(self, coordinator, mock_storage, mock_hass) -> None:
        """Someone opens it with the remote: handled as a manual move."""
        _setup(coordinator, mock_storage, mock_hass)
        _commanded(coordinator, A)
        coordinator._pending_settle.discard(A)
        coordinator._reload_waiting = {A: "velux1"}
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 1110.0
            coordinator._handle_cover_state_change(
                A, MockState("closed", {"current_position": 0}), MockState("open", {"current_position": 40}))
        assert A not in coordinator._reload_waiting
        pause.assert_called_once()

    def test_reports_during_the_reload_are_ignored(self, coordinator, mock_storage, mock_hass) -> None:
        _setup(coordinator, mock_storage, mock_hass)
        coordinator._last_positions[A] = 100
        coordinator._reload_running = {A}
        with patch(f"{MOD}.time_mod") as t, patch.object(coordinator, "pause_cover") as pause:
            t.monotonic.return_value = 1110.0
            coordinator._handle_cover_state_change(
                A, MockState("unavailable"), MockState("closed", {"current_position": 0}))
        pause.assert_not_called()


class TestReload:
    @pytest.mark.asyncio
    async def test_one_reload_for_the_integration(self, coordinator, mock_storage, mock_hass) -> None:
        registry = _setup(coordinator, mock_storage, mock_hass)
        for e in (A, B, OTHER):
            _commanded(coordinator, e)
        coordinator._reload_waiting = {A: "velux1", B: "velux1"}
        coordinator._lost_command_retries = {}
        with patch(f"{RELOAD}.er.async_get", return_value=registry), \
                patch(f"{RELOAD}.RELOAD_GATHER_DELAY", 0), \
                patch(f"{MOD}.time_mod") as t, \
                patch.object(coordinator, "_schedule_refresh") as refresh, \
                patch.object(coordinator, "_logbook") as logbook:
            t.monotonic.return_value = 1120.0
            await coordinator._async_reload_integration("velux1")
        mock_hass.config_entries.async_reload.assert_awaited_once_with("velux1")
        refresh.assert_called_once()
        # Both covers of the integration start again from the read position
        for e in (A, B):
            assert coordinator._last_positions[e] == 0
            assert e not in coordinator._pending_settle and e not in coordinator._move_start
            assert e in coordinator._post_protective_exit
        # The cover of another integration is left alone
        assert coordinator._last_positions[OTHER] == 100 and OTHER in coordinator._pending_settle
        assert coordinator._reload_waiting == {} and coordinator._reload_running == set()
        assert coordinator._reload_last == {"velux1": 1120.0}
        data = coordinator.log_storage.add_entry.call_args.args[3]
        assert data["key"] == "reload_done" and data["count"] == 2 and data["covers"] == "Cuisine, Salon"
        assert "Velux" in logbook.call_args.args[0]

    @pytest.mark.asyncio
    async def test_dropped_when_every_cover_moved(self, coordinator, mock_storage, mock_hass) -> None:
        registry = _setup(coordinator, mock_storage, mock_hass)
        coordinator._reload_waiting = {}
        with patch(f"{RELOAD}.er.async_get", return_value=registry), patch(f"{RELOAD}.RELOAD_GATHER_DELAY", 0):
            await coordinator._async_reload_integration("velux1")
        mock_hass.config_entries.async_reload.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_reload_is_logged(self, coordinator, mock_storage, mock_hass) -> None:
        registry = _setup(coordinator, mock_storage, mock_hass)
        _commanded(coordinator, A)
        coordinator._reload_waiting = {A: "velux1"}
        mock_hass.config_entries.async_reload.side_effect = RuntimeError("boom")
        with patch(f"{RELOAD}.er.async_get", return_value=registry), \
                patch(f"{RELOAD}.RELOAD_GATHER_DELAY", 0), \
                patch.object(coordinator, "_schedule_refresh"), patch.object(coordinator, "_logbook"):
            await coordinator._async_reload_integration("velux1")
        assert coordinator.log_storage.add_entry.call_args.args[3]["key"] == "reload_failed"
        assert coordinator._reload_running == set()

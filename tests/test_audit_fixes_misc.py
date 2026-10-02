"""Audit fixes (tilt below hysteresis, wind exit, statuses, engine caches...)."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.cover_automatic.models import (
    CoverConfig,
    CoverStatus,
    Rule,
)
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401


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


class TestRuleOrderingApi:
    @pytest.mark.asyncio
    async def test_new_rule_goes_to_bottom_with_own_priority(self) -> None:
        from custom_components.cover_automatic.api import ws_rule_add
        from tests.test_api import _real_rule_ordering

        storage = _make_storage()
        storage._data = {"rules": {"a": {"id": "a", "priority": 20}, "b": {"id": "b", "priority": 10}}}
        _real_rule_ordering(storage)

        async def add(rule, save=True):
            storage._data["rules"][rule.id] = rule.to_dict()
        storage.async_add_rule.side_effect = add
        await ws_rule_add(_make_hass(), _make_connection(), {"id": 1, "name": "Zz"}, storage, _make_coordinator())
        prios = {k: v["priority"] for k, v in storage._data["rules"].items()}
        assert prios == {"a": 30, "b": 20, "zz": 10}

    def test_rule_name_length_limited(self) -> None:
        import voluptuous as vol

        from custom_components.cover_automatic.api import _RULE_NAME
        _RULE_NAME("x" * 100)
        with pytest.raises(vol.Invalid):
            _RULE_NAME("x" * 101)

    @pytest.mark.asyncio
    async def test_duplicate_truncates_long_name(self) -> None:
        from unittest.mock import AsyncMock

        from custom_components.cover_automatic.api import ws_rule_duplicate
        storage = _make_storage(rules={"r": Rule(id="r", name="R")})
        storage.async_duplicate_rule = AsyncMock(return_value=True)
        await ws_rule_duplicate(_make_hass(), _make_connection(), {"id": 1, "rule_id": "r", "name": "y" * 150},
                                storage, _make_coordinator())
        assert len(storage.async_duplicate_rule.call_args[0][2]) <= 97


class TestUnloadedEntry:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("state_name", "refused"), [("NOT_LOADED", True), ("LOADED", False)])
    async def test_commands_refused_after_unload(self, state_name, refused) -> None:
        from homeassistant.config_entries import ConfigEntryState

        from custom_components.cover_automatic import api

        registered = {}
        coord = _make_coordinator()
        coord.config_entry = MagicMock(state=getattr(ConfigEntryState, state_name))
        with (
            patch.object(api.websocket_api, "async_response", lambda fn: fn),
            patch.object(api.websocket_api, "require_admin", lambda fn: fn),
            patch.object(api.websocket_api, "async_register_command",
                         side_effect=lambda h, ct, fn, schema=None: registered.__setitem__(ct, fn)),
            patch.object(api, "ws_get_config") as get_config,
        ):
            api.async_setup_api(MagicMock(), _make_storage(), coord)
            conn = _make_connection()
            await registered["cover_automatic/config"](MagicMock(), conn, {"id": 5})
        assert conn.send_error.called is refused
        assert get_config.called is not refused


def test_sensor_rule_state_truncated() -> None:
    from custom_components.cover_automatic.sensor import CoverRuleSensor

    coord = MagicMock()
    coord.storage.covers = {"cover.a": CoverConfig(entity_id="cover.a", name="A")}
    coord.get_cover_live.return_value = {"rule_name": "n" * 400}
    ent = CoverRuleSensor(coord, "cover.a", "A")
    ent.hass = MagicMock()
    assert len(ent.native_value) == 255

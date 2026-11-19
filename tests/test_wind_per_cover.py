"""Wind protection per cover (cover option wind_protection, on by default).

Only the covers with the option on take the wind status and position; the
others keep following their rules during a storm.
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

PERGOLA, SALON = "cover.pergola", "cover.salon"
WIND = "sensor.wind_speed"


def _setup(coordinator, mock_storage, mock_hass, speed="55", salon_option=False):
    mock_storage.wind_sensor = WIND
    mock_storage.wind_speed_threshold = 50.0
    mock_storage.wind_speed_hysteresis = 10.0
    mock_storage.wind_position = 100
    raw = {
        PERGOLA: {"entity_id": PERGOLA, "name": "Pergola", "auto_enabled": True, "inverted": False,
                  "lock_sensor": None, "vent_sensor": None},
        SALON: {"entity_id": SALON, "name": "Salon", "auto_enabled": True, "inverted": False,
                "lock_sensor": None, "vent_sensor": None, "wind_protection": salon_option},
    }
    mock_storage._data["covers"] = raw
    mock_storage.get_cover_raw.side_effect = lambda e: raw.get(e)
    for e in raw:
        coordinator._cover_states[e] = CoverStatus.AUTO
    states = {WIND: MockState(speed)}
    mock_hass.states.get.side_effect = lambda e: states.get(e, MockState("open", {"current_position": 50}))
    return raw, states


class TestActivation:
    def test_only_protected_covers_take_the_wind_status(self, coordinator, mock_storage, mock_hass) -> None:
        _setup(coordinator, mock_storage, mock_hass)
        with patch.object(coordinator, "_start_wind_commands") as send:
            coordinator._check_wind_protection()
        assert coordinator._wind_protected is True
        assert coordinator._cover_states[PERGOLA] == CoverStatus.WIND_PROTECTED
        assert coordinator._cover_states[SALON] == CoverStatus.AUTO
        assert [e for e, _ in send.call_args.args[0]] == [PERGOLA]

    def test_missing_option_means_protected(self, coordinator, mock_storage, mock_hass) -> None:
        """Configurations from before the option: every cover is protected."""
        raw, _ = _setup(coordinator, mock_storage, mock_hass)
        del raw[SALON]["wind_protection"]
        with patch.object(coordinator, "_start_wind_commands"):
            coordinator._check_wind_protection()
        assert coordinator._cover_states[SALON] == CoverStatus.WIND_PROTECTED

    def test_sync_leaves_excluded_cover_alone(self, coordinator, mock_storage, mock_hass) -> None:
        _setup(coordinator, mock_storage, mock_hass)
        with patch.object(coordinator, "_start_wind_commands"), \
                patch.object(coordinator, "_send_wind_position") as one:
            coordinator._sync_cover_statuses()
            coordinator._sync_cover_statuses()
        assert coordinator._cover_states[SALON] == CoverStatus.AUTO
        assert all(c.args[0] != SALON for c in one.call_args_list)


class TestExcludedCoverDuringWind:
    def test_wind_applies_per_cover(self, coordinator, mock_storage, mock_hass) -> None:
        _setup(coordinator, mock_storage, mock_hass)
        coordinator._wind_protected = True
        assert coordinator._wind_applies_to(SALON) is False
        assert coordinator._wind_applies_to(PERGOLA) is True

    def test_resume_allowed_on_excluded_cover(self, coordinator, mock_storage, mock_hass) -> None:
        _setup(coordinator, mock_storage, mock_hass)
        coordinator._wind_protected = True
        coordinator._cover_states[SALON] = CoverStatus.PAUSED
        coordinator._cover_states[PERGOLA] = CoverStatus.WIND_PROTECTED
        coordinator.resume_cover(SALON)
        coordinator.resume_cover(PERGOLA)
        assert coordinator._cover_states[SALON] == CoverStatus.AUTO
        assert coordinator._cover_states[PERGOLA] == CoverStatus.WIND_PROTECTED

    @pytest.mark.asyncio
    async def test_excluded_cover_follows_its_rule(self, coordinator, mock_storage, mock_hass) -> None:
        raw, _ = _setup(coordinator, mock_storage, mock_hass)
        for r in raw.values():
            r.update({"min_position_change": 1, "min_time_between_changes": 0, "last_position_change": None})
        mock_storage.covers = {e: CoverConfig(entity_id=e, name=e) for e in raw}
        coordinator._wind_protected = True
        coordinator._cover_states[PERGOLA] = CoverStatus.WIND_PROTECTED
        coordinator._last_positions[SALON] = 50
        coordinator.data = {"covers": {
            SALON: {"status": "auto", "target_position": 0, "matching_rule_id": "nuit"},
            PERGOLA: {"status": "wind_protected", "target_position": 0, "matching_rule_id": "nuit"},
        }}
        await coordinator.async_apply_positions()
        commanded = [c.args[2]["entity_id"] for c in mock_hass.services.async_call.call_args_list]
        assert commanded == [SALON]


class TestOptionChangedDuringWind:
    def test_excluding_a_protected_cover_releases_it(self, coordinator, mock_storage, mock_hass) -> None:
        raw, _ = _setup(coordinator, mock_storage, mock_hass, salon_option=True)
        with patch.object(coordinator, "_start_wind_commands"):
            coordinator._check_wind_protection()
        assert coordinator._cover_states[SALON] == CoverStatus.WIND_PROTECTED
        raw[SALON]["wind_protection"] = False
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states[SALON] == CoverStatus.AUTO
        assert SALON in coordinator._post_protective_exit
        assert coordinator._cover_states[PERGOLA] == CoverStatus.WIND_PROTECTED

    def test_including_a_cover_protects_it(self, coordinator, mock_storage, mock_hass) -> None:
        raw, _ = _setup(coordinator, mock_storage, mock_hass)
        with patch.object(coordinator, "_start_wind_commands"):
            coordinator._check_wind_protection()
        raw[SALON]["wind_protection"] = True
        with patch.object(coordinator, "_send_wind_position") as one:
            coordinator._sync_cover_statuses()
        assert coordinator._cover_states[SALON] == CoverStatus.WIND_PROTECTED
        one.assert_called_once_with(SALON)

    def test_excluded_cover_with_open_window_gets_locked(self, coordinator, mock_storage, mock_hass) -> None:
        raw, states = _setup(coordinator, mock_storage, mock_hass, salon_option=True)
        with patch.object(coordinator, "_start_wind_commands"):
            coordinator._check_wind_protection()
        raw[SALON]["wind_protection"] = False
        raw[SALON]["lock_sensor"] = "binary_sensor.fenetre"
        raw[SALON]["lock_hold_position"] = True
        states["binary_sensor.fenetre"] = MockState("on")
        coordinator._release_one_from_wind(SALON, raw[SALON])
        assert coordinator._cover_states[SALON] == CoverStatus.LOCKED


class TestModel:
    def test_round_trip(self) -> None:
        cover = CoverConfig.from_dict({"entity_id": SALON, "name": "Salon", "wind_protection": False})
        assert cover.wind_protection is False
        assert cover.to_dict()["wind_protection"] is False
        assert CoverConfig.from_dict({"entity_id": SALON, "name": "Salon"}).wind_protection is True


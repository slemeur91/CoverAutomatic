"""A manual pause ends once the cover is back at its rule's position."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.cover_automatic.coordinator import RESUME_MATCH_GRACE
from custom_components.cover_automatic.models import CoverConfig, CoverStatus
from homeassistant.util import dt as dt_util
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401
from tests.test_storage import mock_store, storage  # noqa: F401
from tests.test_coordinator_robustness import TIME, _raw, _states, _use_covers

LOGBOOK = "custom_components.cover_automatic.coordinator.i18n.text"


def _setup(coordinator, mock_hass, mock_storage, *, position=100, target=100, own=None,
           global_on=True, still=True, raw=None, tilt=None, rule_tilt=None):
    _use_covers(mock_storage, {"cover.t": raw or _raw(min_position_change=1)})
    mock_storage.enabled = True
    mock_storage.pause_resume_on_match = global_on
    mock_storage.rules = {"r": SimpleNamespace(name="Ouvrir Bureau")}
    cover = CoverConfig(entity_id="cover.t", name="t", pause_resume_on_match=own)
    mock_storage.covers = {"cover.t": cover}
    coordinator._cover_states["cover.t"] = CoverStatus.PAUSED
    coordinator._paused_at = {"cover.t": 0.0}
    attrs = {"current_position": position}
    if tilt is not None:
        attrs["current_tilt_position"] = tilt
    state = MockState("open", attrs)
    state.last_updated = dt_util.utcnow() - timedelta(seconds=300 if still else 5)
    # Stillness uses the last position change (fallback last_changed)
    state.last_changed = state.last_updated
    mock_hass.states.get.side_effect = _states({"cover.t": state})
    coordinator.engine = MagicMock()
    coordinator.engine.evaluate_cover.return_value = (
        None if target is None
        else SimpleNamespace(position=target, tilt_position=rule_tilt, rule_id="r")
    )
    return cover


def _run(coordinator, cover, now=1000.0):
    with patch(TIME) as mock_time, patch(LOGBOOK, return_value="txt"):
        mock_time.monotonic.return_value = now
        return coordinator._resume_on_match(cover)


class TestResumeOnMatch:
    def test_resumes_when_position_matches(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage)
        assert _run(coordinator, cover) is True
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        assert "cover.t" not in coordinator._paused_at

    def test_within_tolerance(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage, position=99, target=100)
        assert _run(coordinator, cover) is True

    def test_no_resume_when_position_differs(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage, position=0, target=100)
        assert _run(coordinator, cover) is False
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED

    def test_grace_period(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage)
        assert _run(coordinator, cover, now=RESUME_MATCH_GRACE - 1) is False
        assert _run(coordinator, cover, now=RESUME_MATCH_GRACE + 1) is True

    def test_not_while_moving_or_just_reported(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage, still=False)
        assert _run(coordinator, cover) is False
        cover = _setup(coordinator, mock_hass, mock_storage)
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("opening", {"current_position": 100})})
        assert _run(coordinator, cover) is False

    def test_no_rule_keeps_pause(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage, target=None)
        assert _run(coordinator, cover) is False

    @pytest.mark.parametrize("status", [CoverStatus.MANUAL, CoverStatus.LOCKED, CoverStatus.AUTO])
    def test_only_paused_covers(self, coordinator, mock_hass, mock_storage, status) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage)
        coordinator._cover_states["cover.t"] = status
        assert _run(coordinator, cover) is False
        assert coordinator._cover_states["cover.t"] == status

    def test_global_and_cover_options(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage, global_on=False)
        assert _run(coordinator, cover) is False
        cover = _setup(coordinator, mock_hass, mock_storage, global_on=False, own=True)
        assert _run(coordinator, cover) is True
        cover = _setup(coordinator, mock_hass, mock_storage, global_on=True, own=False)
        assert _run(coordinator, cover) is False

    def test_inverted_cover(self, coordinator, mock_hass, mock_storage) -> None:
        # Rule 100 (open) on an inverted cover = raw position 0
        cover = _setup(coordinator, mock_hass, mock_storage, position=0, target=100,
                       raw=_raw(min_position_change=1, inverted=True))
        assert _run(coordinator, cover) is True

    def test_tilt_must_match(self, coordinator, mock_hass, mock_storage) -> None:
        raw = _raw(min_position_change=1, supports_tilt=True)
        cover = _setup(coordinator, mock_hass, mock_storage, raw=raw, tilt=20, rule_tilt=60)
        assert _run(coordinator, cover) is False
        cover = _setup(coordinator, mock_hass, mock_storage, raw=raw, tilt=60, rule_tilt=60)
        assert _run(coordinator, cover) is True

    def test_wind_protection_refuses(self, coordinator, mock_hass, mock_storage) -> None:
        cover = _setup(coordinator, mock_hass, mock_storage)
        coordinator._wind_protected = True
        assert _run(coordinator, cover) is False
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED

    def test_pause_records_start(self, coordinator, mock_storage) -> None:
        mock_storage.pause_duration = 90
        cover = CoverConfig(entity_id="cover.t", name="t")
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        with patch(TIME) as mock_time, patch(LOGBOOK, return_value="txt"):
            mock_time.monotonic.return_value = 42.0
            coordinator.pause_cover(cover)
        assert coordinator._paused_at["cover.t"] == 42.0


class TestStorageAndModel:
    def test_cover_roundtrip(self) -> None:
        for value in (None, True, False):
            cover = CoverConfig(entity_id="cover.t", name="t", pause_resume_on_match=value)
            assert CoverConfig.from_dict(cover.to_dict()).pause_resume_on_match is value

    @pytest.mark.asyncio
    async def test_global_default_on(self, storage, mock_store) -> None:
        from custom_components.cover_automatic.storage import GLOBAL_SETTING_KEYS
        assert "pause_resume_on_match" in GLOBAL_SETTING_KEYS
        mock_store.async_load.return_value = None
        await storage.async_load()
        assert storage.pause_resume_on_match is True
        storage.pause_resume_on_match = False
        assert storage.pause_resume_on_match is False
        await storage.async_import_data({"covers": {}, "pause_resume_on_match": "true"})
        assert storage.pause_resume_on_match is True

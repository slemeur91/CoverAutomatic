"""Backups hold every setting and field, and restore them."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import json

import pytest

from custom_components.cover_automatic.models import CoverConfig
from custom_components.cover_automatic.storage import GLOBAL_SETTING_KEYS
from tests.test_storage import mock_hass, mock_store, storage  # noqa: F401 -- pytest fixtures


def _minimal() -> dict:
    return {
        "facades": {}, "rules": {}, "scenarios": {"everyday": {"id": "everyday", "name": "E"}},
        "covers": {"cover.a": {"entity_id": "cover.a", "name": "A"}},
        "active_scenario": "everyday",
    }


class TestExport:
    def test_every_setting_is_exported_with_its_default(self, storage) -> None:
        storage._data = _minimal()
        data = storage.get_export_data()
        for key in GLOBAL_SETTING_KEYS:
            assert key in data, key
        assert data["sun_heating_ignore"] is True
        assert data["sun_neutral_ignore"] is True
        assert data["preemptive_shading"] is True
        assert data["solar_threshold_entity"] is None

    def test_cover_has_every_field(self, storage) -> None:
        storage._data = _minimal()
        cover = storage.get_export_data()["covers"]["cover.a"]
        # Runtime state is not exported (the learned travel time is)
        runtime = {"status", "pause_until", "last_position_change"}
        assert set(cover) == set(CoverConfig(entity_id="x", name="x").to_dict()) - runtime
        assert cover["sun_heating_ignore"] is None

    def test_export_is_json_serialisable_and_does_not_touch_store(self, storage) -> None:
        storage._data = _minimal()
        json.dumps(storage.get_export_data())
        assert "sun_heating_ignore" not in storage._data


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_unchecked_switches_survive_export_import(self, storage) -> None:
        storage._data = _minimal()
        storage.sun_heating_ignore = False
        storage.sun_neutral_ignore = False
        storage.preemptive_shading = False
        storage.solar_threshold_entity = "input_number.seuil"
        storage.wind_position = 30
        storage._data["covers"]["cover.a"]["sun_neutral_ignore"] = True
        storage._invalidate_cache()
        exported = json.loads(json.dumps(storage.get_export_data()))

        # Restore onto an installation with other values
        storage._data = _minimal()
        storage.sun_heating_ignore = True
        storage.wind_position = 100
        await storage.async_import_data(exported)

        assert storage.sun_heating_ignore is False
        assert storage.sun_neutral_ignore is False
        assert storage.preemptive_shading is False
        assert storage.solar_threshold_entity == "input_number.seuil"
        assert storage.wind_position == 30
        assert storage.covers["cover.a"].sun_neutral_ignore is True
        again = storage.get_export_data()
        again.pop("migrations", None)
        exported.pop("migrations", None)
        assert again == exported

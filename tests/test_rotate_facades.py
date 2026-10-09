"""House rotation option for the existing facades, and card temperature attributes."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.cover_automatic.const import DOMAIN
from custom_components.cover_automatic.models import CoverConfig
from custom_components.cover_automatic.sensor import CoverAutomaticStatusSensor
from custom_components.cover_automatic.storage import GLOBAL_SETTING_KEYS
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_engine import mock_hass  # noqa: F401
from tests.test_storage import mock_store, storage  # noqa: F401

EID = "cover.salon"


def _facades() -> dict:
    return {"facades": {"south": {"azimuth_start": 135.0, "azimuth_end": 225.0}}}


class TestRotateFacadesSetting:
    @pytest.mark.asyncio
    async def test_default_is_on_and_setter(self, storage, mock_store) -> None:
        mock_store.async_load.return_value = None
        await storage.async_load()
        assert storage.rotate_facades_with_house is True
        storage.rotate_facades_with_house = False
        assert storage.rotate_facades_with_house is False

    @pytest.mark.asyncio
    async def test_import_export(self, storage, mock_store) -> None:
        mock_store.async_load.return_value = None
        await storage.async_load()
        assert "rotate_facades_with_house" in GLOBAL_SETTING_KEYS
        assert storage.get_export_data()["rotate_facades_with_house"] is True
        await storage.async_import_data({"covers": {}, "rotate_facades_with_house": "false"})
        assert storage.rotate_facades_with_house is False

    @pytest.mark.asyncio
    async def test_off_keeps_existing_facades(self) -> None:
        from custom_components.cover_automatic.api import ws_settings_update

        storage = _make_storage()
        storage.house_rotation = 0.0
        storage.rotate_facades_with_house = False
        storage._data = _facades()
        msg = {"id": 1, "type": f"{DOMAIN}/settings/update", "house_rotation": 10.0}
        await ws_settings_update(_make_hass(), _make_connection(), msg, storage, _make_coordinator())
        assert storage._data["facades"]["south"] == {"azimuth_start": 135.0, "azimuth_end": 225.0}

    @pytest.mark.asyncio
    async def test_unchecked_in_the_same_save_applies_at_once(self) -> None:
        from custom_components.cover_automatic.api import ws_settings_update

        storage = _make_storage()
        storage.house_rotation = 0.0
        storage.rotate_facades_with_house = True
        storage._data = _facades()
        msg = {"id": 1, "type": f"{DOMAIN}/settings/update", "house_rotation": 10.0,
               "rotate_facades_with_house": False}
        await ws_settings_update(_make_hass(), _make_connection(), msg, storage, _make_coordinator())
        assert storage._data["facades"]["south"] == {"azimuth_start": 135.0, "azimuth_end": 225.0}

    @pytest.mark.asyncio
    async def test_on_rotates_existing_facades(self) -> None:
        from custom_components.cover_automatic.api import ws_settings_update

        storage = _make_storage()
        storage.house_rotation = 0.0
        storage.rotate_facades_with_house = True
        storage._data = _facades()
        msg = {"id": 1, "type": f"{DOMAIN}/settings/update", "house_rotation": 10.0}
        await ws_settings_update(_make_hass(), _make_connection(), msg, storage, _make_coordinator())
        assert storage._data["facades"]["south"] == {"azimuth_start": 145.0, "azimuth_end": 235.0}


class TestCardTemperatureAttributes:
    def _attrs(self, cover: CoverConfig, global_sensor: str | None) -> dict:
        coord = MagicMock()
        coord.hass = MagicMock()
        coord.storage.covers = {EID: cover}
        coord.storage.indoor_temp_sensor = global_sensor
        coord.storage.temp_color_thermometer = True
        coord.get_cover_live = MagicMock(return_value={})
        coord.get_logical_position = MagicMock(return_value=0)
        ent = CoverAutomaticStatusSensor(coord, EID, "Salon")
        ent.hass = coord.hass
        with patch("custom_components.cover_automatic.sensor.er.async_get", return_value=MagicMock()):
            return ent.extra_state_attributes

    def test_cover_sensor_wins_over_the_global_one(self) -> None:
        cover = CoverConfig(entity_id=EID, name="Salon", indoor_temp_sensor="sensor.salon")
        attrs = self._attrs(cover, "sensor.maison")
        assert attrs["room_temp_sensor"] == "sensor.salon"
        assert attrs["temp_color_thermometer"] is True

    def test_global_sensor_is_the_fallback(self) -> None:
        cover = CoverConfig(entity_id=EID, name="Salon")
        assert self._attrs(cover, "sensor.maison")["room_temp_sensor"] == "sensor.maison"

    def test_sun_on_the_cover_facade(self) -> None:
        cover = CoverConfig(entity_id=EID, name="Salon", facade_id="south")
        coord = MagicMock()
        coord.hass = MagicMock()
        coord.storage.covers = {EID: cover}
        coord.get_cover_live = MagicMock(return_value={})
        coord.get_live_facade_data = MagicMock(return_value={"south": {"sun_on_facade": True}})
        ent = CoverAutomaticStatusSensor(coord, EID, "Salon")
        ent.hass = coord.hass
        with patch("custom_components.cover_automatic.sensor.er.async_get", return_value=MagicMock()):
            assert ent.extra_state_attributes["sun_on_facade"] is True
            coord.get_live_facade_data.return_value = {"south": {"sun_on_facade": False}}
            assert ent.extra_state_attributes["sun_on_facade"] is False

    def test_no_facade_means_no_sun(self) -> None:
        cover = CoverConfig(entity_id=EID, name="Salon")
        assert self._attrs(cover, None)["sun_on_facade"] is False

    def test_no_sensor(self) -> None:
        cover = CoverConfig(entity_id=EID, name="Salon")
        assert self._attrs(cover, None)["room_temp_sensor"] is None

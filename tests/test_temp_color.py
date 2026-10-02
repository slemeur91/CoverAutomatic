"""Display option for the room temperature colours."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import pytest

from custom_components.cover_automatic.storage import GLOBAL_SETTING_KEYS
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_engine import mock_hass  # noqa: F401
from tests.test_storage import mock_store, storage  # noqa: F401


class TestTempColorSetting:
    @pytest.mark.asyncio
    async def test_default_is_action_and_setter(self, storage, mock_store) -> None:
        mock_store.async_load.return_value = None
        await storage.async_load()
        assert storage.temp_color_thermometer is False
        storage.temp_color_thermometer = True
        assert storage.temp_color_thermometer is True

    @pytest.mark.asyncio
    async def test_import_export(self, storage, mock_store) -> None:
        mock_store.async_load.return_value = None
        await storage.async_load()
        assert "temp_color_thermometer" in GLOBAL_SETTING_KEYS
        await storage.async_import_data({"covers": {}, "temp_color_thermometer": "true"})
        assert storage.temp_color_thermometer is True
        assert storage.get_raw_data()["temp_color_thermometer"] is True

    @pytest.mark.asyncio
    async def test_ws_update(self) -> None:
        from custom_components.cover_automatic.api import _build_config_response, ws_settings_update

        storage = _make_storage()
        conn = _make_connection()
        msg = {"id": 1, "type": "cover_automatic/settings/update", "temp_color_thermometer": True}
        await ws_settings_update(_make_hass(), conn, msg, storage, _make_coordinator())
        assert storage.temp_color_thermometer is True
        conn.send_result.assert_called_once()
        assert _build_config_response(storage, None, None)["settings"]["temp_color_thermometer"] is True

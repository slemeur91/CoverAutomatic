"""Dashboard card registered as a Lovelace resource; scenario names."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection

from custom_components.cover_automatic import _async_register_card_resource
from custom_components.cover_automatic.models import Scenario

URL = "/cover_automatic/cover-automatic-card.js?v=1.83.0"


def _hass_with(items: list[dict], *, loaded: bool = True):
    res = MagicMock(spec=ResourceStorageCollection)
    res.loaded = loaded
    res.async_load = AsyncMock()
    res.async_items.return_value = items
    res.async_create_item = AsyncMock()
    res.async_update_item = AsyncMock()
    hass = MagicMock()
    hass.data = {LOVELACE_DATA: MagicMock(resources=res)}
    return hass, res


@pytest.mark.asyncio
async def test_created_when_missing() -> None:
    hass, res = _hass_with([], loaded=False)
    assert await _async_register_card_resource(hass, URL)
    res.async_load.assert_awaited_once()
    res.async_create_item.assert_awaited_once_with({"res_type": "module", "url": URL})


@pytest.mark.asyncio
async def test_updated_on_new_version() -> None:
    hass, res = _hass_with([{"id": "x", "type": "module", "url": "/cover_automatic/cover-automatic-card.js?v=1.79.0"}])
    assert await _async_register_card_resource(hass, URL)
    res.async_update_item.assert_awaited_once_with("x", {"res_type": "module", "url": URL})
    res.async_create_item.assert_not_called()


@pytest.mark.asyncio
async def test_unchanged_when_current() -> None:
    hass, res = _hass_with([{"id": "x", "type": "module", "url": URL}])
    assert await _async_register_card_resource(hass, URL)
    res.async_update_item.assert_not_called()
    res.async_create_item.assert_not_called()


@pytest.mark.asyncio
async def test_yaml_mode_or_no_lovelace_falls_back() -> None:
    hass = MagicMock()
    hass.data = {}
    assert not await _async_register_card_resource(hass, URL)
    hass.data = {LOVELACE_DATA: MagicMock(resources=object())}
    assert not await _async_register_card_resource(hass, URL)


@pytest.mark.asyncio
async def test_errors_do_not_break_setup() -> None:
    hass, res = _hass_with([])
    res.async_create_item.side_effect = RuntimeError("boom")
    assert not await _async_register_card_resource(hass, URL)


def test_scenario_names_attribute() -> None:
    from custom_components.cover_automatic.select import ScenarioSelect

    coord = MagicMock()
    coord.storage.scenarios = {"everyday": Scenario(id="everyday", name="Quotidien"),
                               "summer": Scenario(id="summer", name="Été")}
    ent = ScenarioSelect(coord, "e1")
    assert ent.extra_state_attributes == {"scenario_names": {"everyday": "Quotidien", "summer": "Été"}}

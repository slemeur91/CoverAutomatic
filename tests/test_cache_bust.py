"""Cache busting of the panel/card files also follows their modification time."""
from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.cover_automatic import _asset_mtime, _async_asset_stamp


@pytest.mark.asyncio
async def test_stamp_from_mtime() -> None:
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(return_value=1790529519)
    assert await _async_asset_stamp(hass, pathlib.Path("x.js")) == "-1790529519"


@pytest.mark.asyncio
async def test_stamp_unreadable_file_falls_back_to_version_only() -> None:
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=OSError)
    assert await _async_asset_stamp(hass, pathlib.Path("missing.js")) == ""


def test_asset_mtime_reads_file(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "a.js"
    f.write_text("x")
    assert _asset_mtime(f) == int(f.stat().st_mtime)

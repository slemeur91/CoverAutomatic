"""Cache busting of the panel folder and card file also follows their modification time."""
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


def test_asset_mtime_folder_uses_newest_module(tmp_path: pathlib.Path) -> None:
    """The panel folder stamp follows its most recently changed module."""
    import os

    old, new = tmp_path / "core.js", tmp_path / "rules.js"
    old.write_text("x")
    new.write_text("y")
    (tmp_path / "notes.txt").write_text("ignored")
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))
    assert _asset_mtime(tmp_path) == 2_000_000

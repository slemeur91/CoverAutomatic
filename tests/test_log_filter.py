"""Activity log filtered on one cover (with the global events)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.cover_automatic.storage import ActivityLogStorage
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage


def _log() -> ActivityLogStorage:
    log = ActivityLogStorage.__new__(ActivityLogStorage)
    log._store = MagicMock()
    log._entries = []
    for entity_id, msg in (("cover.a", "a1"), (None, "wind"), ("cover.b", "b1"), ("cover.a", "a2")):
        log.add_entry("status", entity_id, msg)
    return log


class TestLogFilter:
    def test_entity_only(self) -> None:
        assert [e["message"] for e in _log().get_entries(entity_id="cover.a")] == ["a2", "a1"]

    def test_entity_with_global(self) -> None:
        entries = _log().get_entries(entity_id="cover.a", include_global=True)
        assert [e["message"] for e in entries] == ["a2", "wind", "a1"]

    def test_no_filter_ignores_include_global(self) -> None:
        assert len(_log().get_entries(include_global=True)) == 4

    @pytest.mark.asyncio
    async def test_ws_passes_include_global(self) -> None:
        from custom_components.cover_automatic.api import ws_get_log

        conn = _make_connection()
        coordinator = _make_coordinator()
        coordinator.log_storage = _log()
        msg = {"id": 1, "type": "cover_automatic/log", "entity_id": "cover.b",
               "include_global": True, "limit": 1000}
        await ws_get_log(_make_hass(), conn, msg, _make_storage(), coordinator)
        entries = conn.send_result.call_args[0][1]["entries"]
        assert [e["message"] for e in entries] == ["b1", "wind"]

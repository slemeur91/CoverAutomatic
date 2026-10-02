"""Duplicating a rule."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.cover_automatic.api import _copy_name, ws_rule_duplicate
from custom_components.cover_automatic.models import Rule
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_storage import mock_hass, mock_store, storage  # noqa: F401 -- pytest fixtures


def _raw(rule_id: str, priority: int, **extra) -> dict:
    return {
        "id": rule_id, "name": rule_id.upper(), "priority": priority, "enabled": True,
        "conditions": [{"type": "state_is", "params": {"entity_id": "a", "state": "on"}, "group": 0}],
        "target_position": 40, "scenario_ids": ["everyday"], "safety": True, **extra,
    }


def _setup(storage) -> None:
    storage._data = {
        "facades": {}, "covers": {},
        "rules": {"a": _raw("a", 30), "b": _raw("b", 20), "c": _raw("c", 10)},
        "scenarios": {
            "everyday": {"id": "everyday", "name": "E", "rules_disabled": ["b"]},
            "night": {"id": "night", "name": "N", "rules_disabled": []},
        },
        "active_scenario": "everyday",
    }


class TestStorage:
    @pytest.mark.asyncio
    async def test_copy_is_right_below_and_active(self, storage) -> None:
        _setup(storage)
        assert await storage.async_duplicate_rule("b", "b_copy", "B - copie")
        assert storage.rule_order() == ["a", "b", "b_copy", "c"]
        copy = storage.rules["b_copy"]
        assert copy.enabled is True
        assert copy.name == "B - copie"
        assert copy.target_position == 40 and copy.safety is True
        assert copy.scenario_ids == ["everyday"]
        assert len(copy.conditions) == 1
        # Original untouched
        assert storage.rules["b"].enabled is True and storage.rules["b"].name == "B"

    @pytest.mark.asyncio
    async def test_copy_of_last_rule(self, storage) -> None:
        _setup(storage)
        await storage.async_duplicate_rule("c", "c2", "C2")
        assert storage.rule_order() == ["a", "b", "c", "c2"]

    @pytest.mark.asyncio
    async def test_scenario_switch_off_follows(self, storage) -> None:
        _setup(storage)
        await storage.async_duplicate_rule("b", "b_copy", "B - copie")
        assert storage.scenarios["everyday"].rules_disabled == ["b", "b_copy"]
        assert storage.scenarios["night"].rules_disabled == []

    @pytest.mark.asyncio
    async def test_conditions_are_independent(self, storage) -> None:
        _setup(storage)
        await storage.async_duplicate_rule("a", "a_copy", "A - copie")
        storage._data["rules"]["a_copy"]["conditions"][0]["params"]["state"] = "off"
        assert storage._data["rules"]["a"]["conditions"][0]["params"]["state"] == "on"

    @pytest.mark.asyncio
    async def test_refuses_unknown_or_taken(self, storage) -> None:
        _setup(storage)
        assert not await storage.async_duplicate_rule("zz", "x", "X")
        assert not await storage.async_duplicate_rule("a", "b", "B")


class TestApi:
    def test_copy_name_uniqueness(self) -> None:
        rules = {"a": Rule(id="a", name="R - copie"), "b": Rule(id="b", name="R - copie 2")}
        assert _copy_name("R - copie", rules) == "R - copie 3"
        assert _copy_name("Other", rules) == "Other"

    @pytest.mark.asyncio
    async def test_duplicate_returns_new_id(self) -> None:
        storage = _make_storage(rules={"r": Rule(id="r", name="Fermer la Nuit")})
        storage.async_duplicate_rule = AsyncMock(return_value=True)
        conn = _make_connection()
        msg = {"id": 1, "rule_id": "r", "name": "Fermer la Nuit - copie"}
        await ws_rule_duplicate(_make_hass(), conn, msg, storage, _make_coordinator())
        storage.async_duplicate_rule.assert_awaited_once_with(
            "r", "fermer_la_nuit_copie", "Fermer la Nuit - copie"
        )
        assert conn.send_result.call_args[0][1]["new_rule_id"] == "fermer_la_nuit_copie"

    @pytest.mark.asyncio
    async def test_default_name_and_unknown_rule(self) -> None:
        storage = _make_storage(rules={"r": Rule(id="r", name="R")})
        storage.async_duplicate_rule = AsyncMock(return_value=True)
        await ws_rule_duplicate(_make_hass(), _make_connection(), {"id": 1, "rule_id": "r"}, storage, _make_coordinator())
        assert storage.async_duplicate_rule.call_args[0][2] == "R - copy"
        conn = _make_connection()
        await ws_rule_duplicate(_make_hass(), conn, {"id": 2, "rule_id": "nope"}, storage, _make_coordinator())
        assert conn.send_error.call_args[0][1] == "not_found"

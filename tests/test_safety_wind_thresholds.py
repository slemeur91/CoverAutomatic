"""Tests for safety rules, threshold entities, wind position and rule renames."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.cover_automatic.api import (
    _optional_entity_id,
    _rule_id_for_name,
    _build_config_response,
    ws_rule_add,
    ws_rule_update,
    ws_settings_update,
)
from custom_components.cover_automatic.models import (
    ComfortMode,
    Condition,
    ConditionType,
    CoverConfig,
    Rule,
    Scenario,
)
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_engine import (  # noqa: F401 -- pytest fixtures
    MockState,
    engine,
    mock_hass,
    mock_storage,
    test_cover,
)
from tests.test_storage import mock_store, storage  # noqa: F401 -- pytest fixtures


def _states(mock_hass, values: dict[str, str]) -> None:
    mock_hass.states.get = MagicMock(
        side_effect=lambda eid: MockState(values[eid]) if eid in values else None
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_rule_safety_roundtrip(self) -> None:
        rule = Rule(id="r", name="R", safety=True)
        assert rule.to_dict()["safety"] is True
        assert Rule.from_dict(rule.to_dict()).safety is True

    @pytest.mark.parametrize(("raw", "expected"), [(None, False), ("false", False), ("true", True), (1, True)])
    def test_rule_safety_coerced(self, raw, expected) -> None:
        data = {"id": "r", "name": "R"}
        if raw is not None:
            data["safety"] = raw
        assert Rule.from_dict(data).safety is expected

    def test_cover_threshold_entities_roundtrip(self) -> None:
        cover = CoverConfig(entity_id="cover.a", name="A", comfort_temp_min_entity="input_number.x")
        data = cover.to_dict()
        assert data["comfort_temp_min_entity"] == "input_number.x"
        assert data["comfort_temp_max_entity"] is None
        assert CoverConfig.from_dict({**data, "comfort_temp_max_entity": ""}).comfort_temp_max_entity is None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TestEngineSafety:
    def _rules(self, mock_storage) -> None:
        mock_storage.rules = {
            "normal": Rule(id="normal", name="Normal", priority=50, target_position=80),
            "storm": Rule(id="storm", name="Storm", priority=5, target_position=0, safety=True),
        }
        for rule in mock_storage.rules.values():
            rule.cover_ids = ["cover.living_room"]

    def test_normal_priority_applies(self, engine, mock_storage, test_cover) -> None:
        self._rules(mock_storage)
        result = engine.evaluate_cover(test_cover)
        assert result.rule_id == "normal" and result.safety is False

    def test_safety_only(self, engine, mock_storage, test_cover) -> None:
        self._rules(mock_storage)
        result = engine.evaluate_cover(test_cover, safety_only=True)
        assert result.rule_id == "storm" and result.safety is True and result.position == 0

    def test_safety_rule_respects_scenario(self, engine, mock_storage, test_cover) -> None:
        self._rules(mock_storage)
        mock_storage.scenarios = {"everyday": Scenario(id="everyday", name="E", rules_disabled=["storm"])}
        assert engine.evaluate_cover(test_cover, safety_only=True) is None


class TestThresholdEntities:
    def test_global_entity_overrides_number(self, engine, mock_hass, mock_storage, test_cover) -> None:
        mock_storage.comfort_temp_min_entity = "input_number.cmin"
        mock_storage.comfort_temp_max_entity = "input_number.cmax"
        _states(mock_hass, {"input_number.cmin": "18", "input_number.cmax": "22.5"})
        assert engine._comfort_range(test_cover) == (18.0, 22.5)

    def test_unavailable_entity_falls_back(self, engine, mock_hass, mock_storage, test_cover, caplog) -> None:
        mock_storage.comfort_temp_min_entity = "input_number.cmin"
        mock_storage.comfort_temp_max_entity = None
        _states(mock_hass, {"input_number.cmin": "unavailable"})
        with caplog.at_level(logging.WARNING):
            for _ in range(3):
                assert engine._comfort_range(test_cover) == (21.0, 25.0)
        assert sum("input_number.cmin" in r.message for r in caplog.records) == 1
        # Recovers once readable again
        _states(mock_hass, {"input_number.cmin": "19"})
        assert engine._comfort_range(test_cover) == (19.0, 25.0)

    def test_per_cover_order(self, engine, mock_hass, mock_storage, test_cover) -> None:
        mock_storage.comfort_temp_min_entity = "input_number.gmin"
        mock_storage.comfort_temp_max_entity = None
        _states(mock_hass, {"input_number.gmin": "17", "input_number.cmin": "20", "input_number.cmax": "abc"})
        # Global entity when the cover has nothing
        assert engine._comfort_range(test_cover)[0] == 17.0
        # Per-cover number beats the global entity
        test_cover.comfort_temp_min = 19.0
        assert engine._comfort_range(test_cover)[0] == 19.0
        # Per-cover entity beats the per-cover number
        test_cover.comfort_temp_min_entity = "input_number.cmin"
        assert engine._comfort_range(test_cover)[0] == 20.0
        # Non-numeric per-cover entity without number: global value
        test_cover.comfort_temp_max_entity = "input_number.cmax"
        assert engine._comfort_range(test_cover)[1] == 25.0

    def test_invalid_entity_pair_uses_static(self, engine, mock_hass, mock_storage, test_cover) -> None:
        mock_storage.comfort_temp_min_entity = "input_number.cmin"
        mock_storage.comfort_temp_max_entity = None
        _states(mock_hass, {"input_number.cmin": "30"})
        assert engine._comfort_range(test_cover) == (21.0, 25.0)

    def test_comfort_mode_uses_entity(self, engine, mock_hass, mock_storage, test_cover) -> None:
        mock_storage.comfort_temp_max_entity = "input_number.cmax"
        mock_storage.comfort_temp_min_entity = None
        _states(mock_hass, {"sensor.indoor_temp": "23", "input_number.cmax": "22"})
        assert engine._get_comfort_mode(test_cover) == ComfortMode.COOLING

    def test_solar_threshold_entity(self, engine, mock_hass, mock_storage) -> None:
        mock_storage.solar_sensor = "sensor.lux"
        mock_storage.solar_threshold = 50000.0
        mock_storage.solar_threshold_entity = "input_number.lux"
        _states(mock_hass, {"sensor.lux": "30000", "input_number.lux": "20000"})
        assert engine._check_solar_intensity() is True
        _states(mock_hass, {"sensor.lux": "30000", "input_number.lux": "unknown"})
        assert engine._check_solar_intensity() is False


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class TestStorage:
    @pytest.mark.asyncio
    async def test_settings_defaults_and_setters(self, storage) -> None:
        await storage.async_load()
        assert storage.wind_position == 100
        assert storage.solar_threshold_entity is None
        storage.wind_position = 140
        assert storage.wind_position == 100
        storage.wind_position = 40
        storage.comfort_temp_min_entity = "input_number.x"
        storage.comfort_temp_max_entity = ""
        assert storage.wind_position == 40
        assert storage.comfort_temp_min_entity == "input_number.x"
        assert storage.comfort_temp_max_entity is None

    @pytest.mark.asyncio
    async def test_rename_rule(self, storage) -> None:
        await storage.async_load()
        for rid in ("a", "old", "z"):
            await storage.async_add_rule(Rule(id=rid, name=rid), save=False)
        await storage.async_add_scenario(
            Scenario(id="s", name="S", rules_disabled=["old", "a"]), save=False
        )
        assert await storage.async_rename_rule("old", "new") is True
        assert list(storage._data["rules"]) == ["a", "new", "z"]
        assert storage.rules["new"].id == "new"
        assert storage.scenarios["s"].rules_disabled == ["new", "a"]
        # Unknown source or taken target: nothing changes
        assert await storage.async_rename_rule("missing", "x") is False
        assert await storage.async_rename_rule("a", "z") is False

    @pytest.mark.asyncio
    async def test_import_keeps_new_settings(self, storage) -> None:
        await storage.async_load()
        storage.wind_position = 60
        storage.solar_threshold_entity = "number.lux"
        await storage.async_import_data({"rules": {}})
        assert storage.wind_position == 60
        assert storage.solar_threshold_entity == "number.lux"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class TestApiHelpers:
    @pytest.mark.parametrize(("rule_id", "name", "expected"), [
        ("sun", "Sun", "sun"),
        ("sun_2", "Sun", "sun_2"),
        ("sun", "Sun shade", "sun_shade"),
        ("r1", "Other", "other_2"),
    ])
    def test_rule_id_for_name(self, rule_id, name, expected) -> None:
        rules = {rule_id: None, "other": None}
        assert _rule_id_for_name(rule_id, name, rules) == expected

    def test_optional_entity_id(self) -> None:
        assert _optional_entity_id(None) is None
        assert _optional_entity_id("") is None
        assert _optional_entity_id("input_number.x") == "input_number.x"
        for bad in ("nodot", ".x", "x.", 5):
            with pytest.raises(vol.Invalid):
                _optional_entity_id(bad)

    def test_settings_in_response(self) -> None:
        storage = _make_storage()
        storage.wind_position = 80
        storage.comfort_temp_min_entity = "input_number.a"
        storage.comfort_temp_max_entity = None
        storage.solar_threshold_entity = None
        settings = _build_config_response(storage)["settings"]
        assert settings["wind_position"] == 80
        assert settings["comfort_temp_min_entity"] == "input_number.a"
        assert "solar_threshold_entity" in settings and "comfort_temp_max_entity" in settings

    def test_schemas_registered(self) -> None:
        from custom_components.cover_automatic import api

        schemas = {}

        def capture(hass, command_type, handler=None, schema=None):
            schemas[command_type] = schema

        with patch.object(api.websocket_api, "async_register_command", side_effect=capture):
            api.async_setup_api(MagicMock(), MagicMock(), MagicMock())
        base = {"id": 1}
        settings = schemas["cover_automatic/settings/update"]
        settings({**base, "type": "cover_automatic/settings/update", "wind_position": 0,
                  "solar_threshold_entity": "sensor.x"})
        with pytest.raises(vol.Invalid):
            settings({**base, "type": "cover_automatic/settings/update", "wind_position": 101})
        with pytest.raises(vol.Invalid):
            settings({**base, "type": "cover_automatic/settings/update", "comfort_temp_min_entity": "bad"})
        cover = schemas["cover_automatic/cover/update"]
        cover({**base, "type": "cover_automatic/cover/update", "entity_id": "cover.a",
               "comfort_temp_max_entity": None})
        for cmd in ("rule/add", "rule/update"):
            msg = {**base, "type": f"cover_automatic/{cmd}", "safety": True}
            msg.update({"name": "R"} if cmd == "rule/add" else {"rule_id": "r"})
            assert schemas[f"cover_automatic/{cmd}"](msg)["safety"] is True


class TestApiHandlers:
    @pytest.mark.asyncio
    async def test_rule_add_safety(self) -> None:
        storage = _make_storage()
        conn = _make_connection()
        await ws_rule_add(_make_hass(), conn, {"id": 1, "name": "Storm", "safety": True},
                          storage, _make_coordinator())
        rule = storage.async_add_rule.call_args.args[0]
        assert rule.safety is True and rule.id == "storm"

    @pytest.mark.asyncio
    async def test_rule_update_renames(self) -> None:
        storage = _make_storage(rules={"old_name": Rule(id="old_name", name="Old name", safety=True)})
        coordinator = _make_coordinator()
        conn = _make_connection()
        await ws_rule_update(_make_hass(), conn,
                             {"id": 1, "rule_id": "old_name", "name": "New name"},
                             storage, coordinator)
        storage.async_rename_rule.assert_awaited_once_with("old_name", "new_name", save=False)
        coordinator.rename_rule_references.assert_called_once_with("old_name", "new_name")
        updated = storage.async_add_rule.call_args.args[0]
        assert updated.id == "new_name" and updated.safety is True
        assert conn.send_result.call_args.args[1]["renamed_rule"] == {"from": "old_name", "to": "new_name"}

    @pytest.mark.asyncio
    async def test_rule_update_keeps_matching_id(self) -> None:
        storage = _make_storage(rules={"sun_2": Rule(id="sun_2", name="Sun")})
        conn = _make_connection()
        await ws_rule_update(_make_hass(), conn, {"id": 1, "rule_id": "sun_2", "safety": True},
                             storage, _make_coordinator())
        storage.async_rename_rule.assert_not_awaited()
        assert storage.async_add_rule.call_args.args[0].safety is True
        assert "renamed_rule" not in conn.send_result.call_args.args[1]

    @pytest.mark.asyncio
    async def test_settings_entity_does_not_break_static_validation(self) -> None:
        storage = _make_storage()
        conn = _make_connection()
        await ws_settings_update(
            _make_hass(), conn,
            {"id": 1, "comfort_temp_min_entity": "input_number.x", "wind_position": 30},
            storage, _make_coordinator(),
        )
        conn.send_error.assert_not_called()
        assert storage.comfort_temp_min_entity == "input_number.x"
        assert storage.wind_position == 30


class TestRenameIntegration:
    """Real storage + coordinator-like references through the handler."""

    @pytest.mark.asyncio
    async def test_rename_with_real_storage(self, storage) -> None:
        await storage.async_load()
        await storage.async_add_rule(Rule(
            id="r1", name="Night", conditions=[Condition(type=ConditionType.DAY_OF_WEEK, params={})],
        ), save=False)
        await storage.async_add_scenario(Scenario(id="s", name="S", rules_disabled=["r1"]), save=False)
        coordinator = _make_coordinator()
        coordinator.engine = None
        conn = _make_connection()
        storage.async_save = AsyncMock()
        # The id only follows an actually changed name
        await ws_rule_update(_make_hass(), conn, {"id": 1, "rule_id": "r1", "name": "Night mode"},
                             storage, coordinator)
        assert list(storage.rules) == ["night_mode"]
        assert storage.scenarios["s"].rules_disabled == ["night_mode"]
        assert conn.send_result.call_args.args[1]["renamed_rule"] == {"from": "r1", "to": "night_mode"}


def test_sanitize_id_strips_accents() -> None:
    from custom_components.cover_automatic.api import _sanitize_id

    assert _sanitize_id("Alerte Météo") == "alerte_meteo"
    assert _sanitize_id("Ouvrir Bureau en Télétravail") == "ouvrir_bureau_en_teletravail"
    assert _sanitize_id("Küche") == "kueche"

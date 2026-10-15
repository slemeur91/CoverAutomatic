"""Tests for the comfort profiles A/B (setpoints, hysteresis and sun switches per scenario)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.cover_automatic.api import _build_config_response, ws_settings_update
from custom_components.cover_automatic.engine import RuleEngine
from custom_components.cover_automatic.models import ComfortMode, CoverConfig, Scenario
from custom_components.cover_automatic.number import _NUMBERS, CoverAutomaticComfortNumber
from custom_components.cover_automatic.storage import (
    MIGRATION_COMFORT_PROFILES,
    MIGRATION_PAUSE_DURATION_120,
    MIGRATION_PREEMPTIVE_TRISTATE,
)
from tests.test_api import _make_connection, _make_coordinator, _make_hass
from tests.test_engine import MockState
from tests.test_storage import mock_hass, mock_store, storage  # noqa: F401

COVER = "cover.chambre"


async def _loaded(storage, mock_store, data=None):  # noqa: F811
    mock_store.async_load.return_value = data
    await storage.async_load()
    for sid in ("everyday", "summer", "winter"):
        if sid not in storage._data.get("scenarios", {}):
            await storage.async_add_scenario(Scenario(id=sid, name=sid), save=False)
    return storage


def _legacy_install() -> dict:
    """Configuration of 2.0.5: comfort band from entities, per-cover sun switches."""
    return {
        "facades": {}, "rules": {},
        "scenarios": {sid: {"id": sid, "name": sid} for sid in ("everyday", "summer", "winter")},
        "covers": {
            COVER: {
                "entity_id": COVER, "name": "Chambre", "comfort_temp_min": 20.0,
                "comfort_temp_min_entity": "input_number.room", "preemptive_shading": False,
                "sun_heating_ignore": True, "sun_neutral_ignore": None,
            },
        },
        "active_scenario": "winter",
        "comfort_temp_min": 21.0, "comfort_temp_max": 25.0, "comfort_hysteresis": 0.5,
        "comfort_temp_min_entity": "input_number.volet_consigne_froid",
        "comfort_temp_max_entity": "input_number.volet_consigne_chaud",
        "sun_heating_ignore": False, "sun_neutral_ignore": True, "preemptive_shading": True,
        "migrations": [MIGRATION_PAUSE_DURATION_120, MIGRATION_PREEMPTIVE_TRISTATE],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class TestStorageDefaults:
    @pytest.mark.asyncio
    async def test_new_install(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        assert storage.comfort_settings("a") == (21.0, 23.0, 1.0)
        assert storage.comfort_settings("b") == (22.0, 24.0, 1.0)
        assert storage.sun_settings("b") == (True, True, True)
        assert storage.profile_b_scenarios == []
        assert storage.active_profile == "a"

    @pytest.mark.asyncio
    async def test_active_profile_follows_scenario(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        storage.active_scenario = "summer"
        assert storage.active_profile == "b"
        storage.active_scenario = "winter"
        assert storage.active_profile == "a"
        assert storage.scenario_profile("summer") == "b"

    @pytest.mark.asyncio
    async def test_unknown_scenarios_ignored(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer", "ghost", "summer"]
        assert storage.profile_b_scenarios == ["summer"]

    @pytest.mark.asyncio
    async def test_scenario_without_profile(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_a_scenarios = ["summer"]
        storage.profile_b_scenarios = ["winter"]
        assert storage.scenario_profile("summer") == "a"
        assert storage.scenario_profile("winter") == "b"
        assert storage.scenario_profile("everyday") is None
        storage.active_scenario = "everyday"
        assert storage.active_profile is None

    @pytest.mark.asyncio
    async def test_profile_a_unset_means_every_other_scenario(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        assert "profile_a_scenarios" not in storage._data
        storage.profile_b_scenarios = ["winter"]
        assert storage.profile_a_scenarios == ["everyday", "summer"]

    @pytest.mark.asyncio
    async def test_scenario_moving_to_b_leaves_a(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_a_scenarios = ["summer", "winter"]
        storage.profile_b_scenarios = ["winter"]
        assert storage.profile_a_scenarios == ["summer"]
        storage.profile_a_scenarios = ["summer", "winter"]
        assert storage.profile_b_scenarios == []

    @pytest.mark.asyncio
    async def test_new_scenario_joins_explicit_a(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_a_scenarios = ["summer"]
        await storage.async_add_scenario(Scenario(id="autumn", name="Autumn"), save=False)
        assert storage.profile_a_scenarios == ["summer", "autumn"]
        await storage.async_remove_scenario("autumn")
        assert storage.profile_a_scenarios == ["summer"]

    @pytest.mark.asyncio
    async def test_removed_scenario_leaves_profile_b(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        await storage.async_remove_scenario("summer")
        assert storage._data["profile_b_scenarios"] == []

    @pytest.mark.asyncio
    async def test_new_scenario_goes_to_a(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        await storage.async_add_scenario(Scenario(id="autumn", name="Autumn"), save=False)
        assert storage.scenario_profile("autumn") == "a"


class TestMigration:
    @pytest.mark.asyncio
    async def test_legacy_install_converted(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store, _legacy_install())
        data = storage._data
        # The band came from entities: profile A gets its defaults
        assert (storage.comfort_temp_min, storage.comfort_temp_max) == (21.0, 23.0)
        assert "comfort_temp_min_entity" not in data and "comfort_temp_max_entity" not in data
        # Profile B: defaults, hysteresis and sun switches copied from A
        assert storage.comfort_settings("b") == (22.0, 24.0, 0.5)
        # The only cover forced two switches: they become the global values
        assert storage.sun_settings("b") == storage.sun_settings("a") == (True, True, False)
        assert storage.profile_b_scenarios == []
        cover = data["covers"][COVER]
        for legacy in ("comfort_temp_min_entity", "preemptive_shading",
                       "sun_heating_ignore", "sun_neutral_ignore"):
            assert legacy not in cover
        assert cover["comfort_temp_min"] == 20.0  # own number kept (profile A)
        assert MIGRATION_COMFORT_PROFILES in data["migrations"]

    @pytest.mark.asyncio
    async def test_unanimous_cover_override_becomes_global(self, storage, mock_store) -> None:  # noqa: F811
        legacy = _legacy_install()
        legacy["covers"]["cover.two"] = {"entity_id": "cover.two", "name": "Two",
                                         "preemptive_shading": False, "sun_heating_ignore": False}
        await _loaded(storage, mock_store, legacy)
        # Every cover forced preemptive shading off: kept as the global value
        assert storage.preemptive_shading is False
        assert storage.preemptive_shading_b is False
        # Overrides that differ between covers: global value unchanged
        assert storage.sun_heating_ignore is False  # global of the legacy install
        assert storage.sun_neutral_ignore is True

    @pytest.mark.asyncio
    async def test_static_band_kept_without_entities(self, storage, mock_store) -> None:  # noqa: F811
        legacy = _legacy_install()
        del legacy["comfort_temp_min_entity"], legacy["comfort_temp_max_entity"]
        legacy["comfort_temp_max"] = 26.0
        await _loaded(storage, mock_store, legacy)
        assert (storage.comfort_temp_min, storage.comfort_temp_max) == (21.0, 26.0)

    @pytest.mark.asyncio
    async def test_import_of_old_export(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        await storage.async_import_data(_legacy_install())
        assert "comfort_temp_min_entity" not in storage._data
        assert (storage.comfort_temp_min, storage.comfort_temp_max) == (21.0, 23.0)
        assert "sun_heating_ignore" not in storage._data["covers"][COVER]

    @pytest.mark.asyncio
    async def test_export_import_roundtrip(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        storage.comfort_temp_min_b, storage.comfort_temp_max_b = 23.0, 26.0
        storage.sun_neutral_ignore_b = False
        exported = storage.get_export_data()
        assert exported["profile_b_scenarios"] == ["summer"]
        storage.profile_b_scenarios = []
        storage.comfort_temp_min_b = 18.0
        await storage.async_import_data(exported)
        assert storage.profile_b_scenarios == ["summer"]
        assert storage.comfort_settings("b")[:2] == (23.0, 26.0)
        assert storage.sun_neutral_ignore_b is False

    @pytest.mark.asyncio
    async def test_import_drops_unknown_profile_scenarios(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        exported = storage.get_export_data()
        exported["profile_b_scenarios"] = ["summer", "ghost"]
        await storage.async_import_data(exported)
        assert storage._data["profile_b_scenarios"] == ["summer"]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _engine(storage, temp: str) -> RuleEngine:  # noqa: F811
    hass = MagicMock()
    states = {"sensor.room": MockState(temp)}
    hass.states.get = lambda eid: states.get(eid)
    return RuleEngine(hass, storage)


def _cover(**kw) -> CoverConfig:
    return CoverConfig(entity_id=COVER, name="Chambre", indoor_temp_sensor="sensor.room", **kw)


class TestEngine:
    @pytest.mark.asyncio
    async def test_range_and_hysteresis_per_profile(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        storage.comfort_hysteresis_b = 0.3
        engine = _engine(storage, "22.5")
        cover = _cover()
        storage.active_scenario = "winter"
        assert engine._comfort_range(cover) == (21.0, 23.0)
        assert engine._comfort_hysteresis(cover) == 1.0
        storage.active_scenario = "summer"
        assert engine._comfort_range(cover) == (22.0, 24.0)
        assert engine._comfort_hysteresis(cover) == 0.3

    @pytest.mark.asyncio
    async def test_cover_overrides_its_profile_only(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        engine = _engine(storage, "22.5")
        cover = _cover(comfort_temp_max_b=25.5, comfort_hysteresis=0.2)
        storage.active_scenario = "winter"
        assert engine._comfort_range(cover) == (21.0, 23.0)
        assert engine._comfort_hysteresis(cover) == 0.2
        storage.active_scenario = "summer"
        assert engine._comfort_range(cover) == (22.0, 25.5)
        assert engine._comfort_hysteresis(cover) == 1.0

    @pytest.mark.asyncio
    async def test_comfort_mode_switches_with_scenario(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        engine = _engine(storage, "22.0")
        cover = _cover()
        storage.active_scenario = "winter"  # A: 21-23 -> comfortable
        assert engine._get_comfort_mode(cover) == ComfortMode.NEUTRAL
        storage.active_scenario = "summer"  # B: 22-24 -> cold
        assert engine._get_comfort_mode(cover) == ComfortMode.HEATING

    @pytest.mark.asyncio
    async def test_hysteresis_restarts_after_profile_change(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        storage.comfort_temp_min_b, storage.comfort_temp_max_b = 20.0, 21.5
        cover = _cover()
        storage.active_scenario = "winter"
        engine = _engine(storage, "20.5")  # A: cold (<= 21)
        assert engine._get_comfort_mode(cover) == ComfortMode.HEATING
        # Within A's hysteresis band, the previous mode would be kept
        storage.active_scenario = "summer"  # B: 20-21.5 -> comfortable
        assert engine._get_comfort_mode(cover) == ComfortMode.NEUTRAL

    @pytest.mark.asyncio
    async def test_no_profile_no_setpoints(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_a_scenarios = ["summer"]
        storage.profile_b_scenarios = ["winter"]
        storage.sun_heating_ignore = storage.sun_neutral_ignore = True
        engine = _engine(storage, "18.0")
        cover = _cover()
        storage.active_scenario = "summer"
        assert engine._get_comfort_mode(cover) == ComfortMode.HEATING
        storage.active_scenario = "everyday"
        assert engine._get_comfort_mode(cover) is None
        assert engine._comfort_known(cover) is False
        # Sun on facade: position only, the comfort switches no longer apply
        assert engine._sun_flags(cover) == (False, False, False)
        assert engine._sun_uses_comfort(cover) is False

    @pytest.mark.asyncio
    async def test_sun_switches_follow_profile(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["summer"]
        storage.sun_heating_ignore, storage.sun_neutral_ignore = False, False
        storage.sun_heating_ignore_b = True
        engine = _engine(storage, "22.0")
        storage.active_scenario = "winter"
        assert engine._sun_flags(_cover())[:2] == (False, False)
        storage.active_scenario = "summer"
        assert engine._sun_flags(_cover())[:2] == (True, True)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class TestApi:
    @pytest.mark.asyncio
    async def test_settings_update_profile_b(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        conn = _make_connection()
        msg = {"id": 1, "profile_b_scenarios": ["summer"], "comfort_temp_min_b": 22.5,
               "comfort_temp_max_b": 25.0, "sun_neutral_ignore_b": False}
        await ws_settings_update(_make_hass(), conn, msg, storage, _make_coordinator())
        conn.send_error.assert_not_called()
        settings = conn.send_result.call_args.args[1]["settings"]
        assert settings["profile_b_scenarios"] == ["summer"]
        assert settings["comfort_temp_max_b"] == 25.0
        assert settings["sun_neutral_ignore_b"] is False

    @pytest.mark.asyncio
    async def test_unknown_scenario_rejected(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, "profile_b_scenarios": ["ghost"]},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "not_found"
        assert storage.profile_b_scenarios == []

    @pytest.mark.asyncio
    async def test_scenario_in_both_profiles_rejected(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn,
                                 {"id": 1, "profile_a_scenarios": ["summer"], "profile_b_scenarios": ["summer"]},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_profiles"

    @pytest.mark.asyncio
    async def test_only_summer_in_a_and_winter_in_b(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn,
                                 {"id": 1, "profile_a_scenarios": ["summer"], "profile_b_scenarios": ["winter"]},
                                 storage, _make_coordinator())
        conn.send_error.assert_not_called()
        settings = conn.send_result.call_args.args[1]["settings"]
        assert settings["profile_a_scenarios"] == ["summer"]
        assert settings["profile_b_scenarios"] == ["winter"]
        assert storage.scenario_profile("everyday") is None

    @pytest.mark.asyncio
    async def test_invalid_band_b_rejected(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, "comfort_temp_min_b": 25.0},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_comfort_range"
        assert storage.comfort_temp_min_b == 22.0

    @pytest.mark.asyncio
    async def test_active_profile_in_response(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["winter"]
        storage.active_scenario = "winter"
        assert _build_config_response(storage)["settings"]["active_profile"] == "b"


# ---------------------------------------------------------------------------
# Number entities
# ---------------------------------------------------------------------------

def _number(storage, key: str) -> CoverAutomaticComfortNumber:  # noqa: F811
    coordinator = MagicMock()
    coordinator.storage = storage
    coordinator.async_request_refresh = AsyncMock()
    description = next(d for d in _NUMBERS if d.key == key)
    entity = CoverAutomaticComfortNumber(coordinator, "entry", description)
    entity.async_write_ha_state = MagicMock()
    return entity


class TestNumbers:
    def test_six_entities(self) -> None:
        assert [d.translation_key for d in _NUMBERS] == [
            "comfort_temp_min_a", "comfort_temp_max_a", "comfort_hysteresis_a",
            "comfort_temp_min_b", "comfort_temp_max_b", "comfort_hysteresis_b",
        ]

    @pytest.mark.asyncio
    async def test_set_value(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        entity = _number(storage, "comfort_temp_max_b")
        assert entity.native_value == 24.0
        with patch.object(storage, "async_save", AsyncMock()) as save:
            await entity.async_set_native_value(25.5)
        save.assert_awaited_once()
        assert storage.comfort_temp_max_b == 25.5
        entity.coordinator.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cold_above_hot_refused(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        entity = _number(storage, "comfort_temp_min")
        with pytest.raises(HomeAssistantError):
            await entity.async_set_native_value(23.0)
        assert storage.comfort_temp_min == 21.0

    @pytest.mark.asyncio
    async def test_hysteresis_has_no_temperature_class(self, storage, mock_store) -> None:  # noqa: F811
        await _loaded(storage, mock_store)
        assert _number(storage, "comfort_hysteresis_b").device_class is None
        assert _number(storage, "comfort_temp_min_b").device_class == "temperature"


# ---------------------------------------------------------------------------
# Activity log: scenario changes
# ---------------------------------------------------------------------------

class TestScenarioLog:
    @pytest.mark.asyncio
    async def test_change_logged_with_profile(self, storage, mock_store) -> None:  # noqa: F811
        from custom_components.cover_automatic.coordinator import CoverAutomaticCoordinator

        await _loaded(storage, mock_store)
        storage.profile_b_scenarios = ["winter"]
        coordinator = CoverAutomaticCoordinator.__new__(CoverAutomaticCoordinator)
        coordinator.storage = storage
        coordinator.hass = MagicMock()
        coordinator._last_scenario = None
        coordinator._log = MagicMock()
        coordinator._logbook = MagicMock()

        storage.active_scenario = "summer"
        coordinator._log_scenario_change()  # first update: only recorded
        coordinator._log.assert_not_called()

        storage.active_scenario = "winter"
        coordinator._log_scenario_change()
        event, entity, _message, data = coordinator._log.call_args.args
        assert (event, entity) == ("scenario", None)
        assert data["key"] == "scenario_change"
        assert (data["from_id"], data["to_id"]) == ("summer", "winter")
        assert "profile" not in data
        coordinator._logbook.assert_called_once()

        coordinator._log.reset_mock()
        coordinator._log_scenario_change()  # unchanged: nothing new
        coordinator._log.assert_not_called()


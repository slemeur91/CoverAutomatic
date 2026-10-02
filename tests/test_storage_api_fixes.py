"""Settings cross checks, invalid conditions, export, azimuth, pause, sun gaps."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import logging

import pytest

from custom_components.cover_automatic.api import ws_settings_update
from custom_components.cover_automatic.models import (
    Condition,
    ConditionType,
    CoverConfig,
    Rule,
)
from custom_components.cover_automatic.storage import _ALL_MIGRATIONS, settings_cross_error
from tests.test_api import _make_connection, _make_coordinator, _make_hass, _make_storage
from tests.test_engine import engine, mock_hass, mock_storage  # noqa: F401 -- fixtures
from tests.test_storage import mock_store, storage  # noqa: F401 -- fixtures
from tests.test_engine_robustness import DAWN, DUSK, MIDNIGHT, SUNRISE, SUNSET, H, _sun_eval
from tests.test_storage_api_robustness import _base_config, _invalid, _valid


# ---------------------------------------------------------------------------
# 1. settings/update: only the cross checks of the fields sent
# ---------------------------------------------------------------------------

class TestSettingsCrossChecks:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("fields", [{"enabled": False}, {"comfort_temp_min": 20}])
    async def test_legacy_invalid_pair_does_not_block_other_settings(self, fields) -> None:
        # solar_hysteresis >= solar_threshold was accepted before
        storage = _make_storage(solar_threshold=100.0, solar_hysteresis=150.0)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, **fields},
                                 storage, _make_coordinator())
        conn.send_error.assert_not_called()
        conn.send_result.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field", ["solar_threshold", "solar_hysteresis"])
    async def test_changing_a_related_field_is_still_checked(self, field) -> None:
        storage = _make_storage(solar_threshold=100.0, solar_hysteresis=150.0)
        conn = _make_connection()
        value = 120 if field == "solar_threshold" else 140
        await ws_settings_update(_make_hass(), conn, {"id": 1, field: value},
                                 storage, _make_coordinator())
        assert conn.send_error.call_args.args[1] == "invalid_solar_hysteresis"
        storage.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fixing_the_pair_is_accepted(self) -> None:
        storage = _make_storage(solar_threshold=100.0, solar_hysteresis=150.0)
        conn = _make_connection()
        await ws_settings_update(_make_hass(), conn, {"id": 1, "solar_hysteresis": 20},
                                 storage, _make_coordinator())
        conn.send_error.assert_not_called()
        assert storage.solar_hysteresis == 20

    def test_helper_without_changed_runs_all_checks(self) -> None:
        values = {"comfort_temp_min": 21, "comfort_temp_max": 25, "wind_speed_threshold": 0,
                  "wind_speed_hysteresis": 0, "solar_threshold": 100, "solar_hysteresis": 150}
        assert settings_cross_error(values.get)[0] == "invalid_solar_hysteresis"
        assert settings_cross_error(values.get, {"enabled"}) is None
        assert settings_cross_error(values.get, {"solar_threshold"})[0] == "invalid_solar_hysteresis"


# ---------------------------------------------------------------------------
# 2. A rule losing a condition is disabled, not made unconditional
# ---------------------------------------------------------------------------

def _rule(conditions, **extra) -> dict:
    return {"id": "r", "name": "Night", "cover_ids": ["cover.a"], "conditions": conditions,
            "scenario_ids": ["everyday"], **extra}


BAD_CONDITIONS = [
    {"type": "temperature_above", "params": {"temperature": "nan"}},
    {"type": "no_such_type", "params": {}},
    {"params": {}},
    "not a dict",
]


class TestInvalidConditionDisablesRule:
    @pytest.mark.parametrize("bad", BAD_CONDITIONS)
    def test_from_dict_disables_and_warns(self, bad, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            rule = Rule.from_dict(_rule([bad]))
        assert rule.enabled is False
        assert rule.conditions == []
        assert "Night" in caplog.text and "disabled" in caplog.text

    def test_partial_loss_also_disables(self) -> None:
        good = {"type": "time_after_sunset", "params": {"offset": 0}}
        rule = Rule.from_dict(_rule([good, BAD_CONDITIONS[0]]))
        assert rule.enabled is False
        assert [c.type for c in rule.conditions] == [ConditionType.TIME_AFTER_SUNSET]

    def test_rule_without_conditions_stays_enabled(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            assert Rule.from_dict(_rule([])).enabled is True
            assert Rule.from_dict({"id": "r", "name": "N"}).enabled is True
        assert "disabled" not in caplog.text

    def test_valid_conditions_stay_enabled(self) -> None:
        rule = Rule.from_dict(_rule([{"type": "time_after_sunset", "params": {"offset": 15}}]))
        assert rule.enabled is True

    @pytest.mark.asyncio
    async def test_storage_load_disables_and_persists(self, storage, mock_store) -> None:
        data = _base_config()
        data["rules"] = {"r": _rule([BAD_CONDITIONS[1]])}
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage.rules["r"].enabled is False
        # the raw store is consistent (and a save is scheduled)
        assert storage._data["rules"]["r"]["enabled"] is False
        mock_store.async_delay_save.assert_called()

    @pytest.mark.asyncio
    async def test_storage_load_keeps_rule_without_conditions(self, storage, mock_store) -> None:
        data = _base_config()
        data["rules"] = {"r": _rule([])}
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage.rules["r"].enabled is True

    @pytest.mark.asyncio
    async def test_import_disables(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["rules"] = {"r": _rule([BAD_CONDITIONS[0]])}
        await storage.async_import_data(data)
        assert "r" in storage.rules
        assert storage.rules["r"].enabled is False
        assert storage._data["rules"]["r"]["enabled"] is False


# ---------------------------------------------------------------------------
# 3. measured_travel_time exported; imported only for new covers
# ---------------------------------------------------------------------------

class TestMeasuredTravelExport:
    @pytest.mark.asyncio
    async def test_exported(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_measured_travel("cover.a", 23.5)
        cover = storage.get_export_data()["covers"]["cover.a"]
        assert cover["measured_travel_time"] == 23.5
        for key in ("status", "pause_until", "last_position_change"):
            assert key not in cover

    @pytest.mark.asyncio
    async def test_import_keeps_local_value_for_existing_cover(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_measured_travel("cover.a", 23.5)
        data = _base_config()
        data["covers"]["cover.a"]["measured_travel_time"] = 99.0
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].measured_travel_time == 23.5

    @pytest.mark.asyncio
    async def test_import_existing_cover_without_learned_value_stays_none(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        data = _base_config()
        data["covers"]["cover.a"]["measured_travel_time"] = 99.0
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].measured_travel_time is None

    @pytest.mark.asyncio
    async def test_import_takes_file_value_for_new_cover(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"].update(measured_travel_time=31.0, status="paused",
                                         pause_until=123.0, last_position_change=5.0)
        await storage.async_import_data(data)
        cover = storage.covers["cover.a"]
        assert cover.measured_travel_time == 31.0
        # runtime state is still never taken from the file
        assert cover.status.value == "auto"
        assert cover.pause_until is None
        assert cover.last_position_change is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [0, -5, "nan", "x"])
    async def test_import_unusable_value_for_new_cover(self, storage, bad) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"]["measured_travel_time"] = bad
        await storage.async_import_data(data)
        assert storage.covers["cover.a"].measured_travel_time is None

    @pytest.mark.asyncio
    async def test_round_trip(self, storage) -> None:
        await storage.async_load()
        await storage.async_import_data(_base_config())
        storage.update_cover_measured_travel("cover.a", 18.0)
        exported = storage.get_export_data()
        # fresh installation
        storage._data = {}
        storage._invalidate_cache()
        await storage.async_import_data(exported)
        assert storage.covers["cover.a"].measured_travel_time == 18.0


# ---------------------------------------------------------------------------
# 4. Facade azimuth normalised modulo 360
# ---------------------------------------------------------------------------

class TestAzimuthNormalized:
    @pytest.mark.parametrize("command", ["facade/add", "facade/update"])
    @pytest.mark.parametrize(("raw", "expected"), [
        (-90, 270.0), (-1, 359.0), (400, 40.0), (720, 0.0), (360, 0.0), (0, 0.0),
        (180.5, 180.5), ("450", 90.0), (-0.0, 0.0), (-1e-20, 0.0),
    ])
    def test_normalized(self, command, raw, expected) -> None:
        key = {"name": "F"} if command == "facade/add" else {"facade_id": "f"}
        msg = _valid(command, **key, azimuth_start=raw, azimuth_end=raw)
        assert msg["azimuth_start"] == expected
        assert msg["azimuth_end"] == expected
        assert 0 <= msg["azimuth_start"] < 360

    @pytest.mark.parametrize("bad", ["nan", "inf", "-inf", True, "x", None])
    def test_non_finite_rejected(self, bad) -> None:
        _invalid("facade/add", name="F", azimuth_start=bad)

    def test_start_equals_end_full_circle(self) -> None:
        msg = _valid("facade/add", name="F", azimuth_start=0, azimuth_end=360)
        assert msg["azimuth_start"] == msg["azimuth_end"] == 0.0

    @pytest.mark.parametrize("command", ["facade/add", "facade/update"])
    def test_min_elevation_still_bounded(self, command) -> None:
        key = {"name": "F"} if command == "facade/add" else {"facade_id": "f"}
        _invalid(command, **key, min_elevation=400)


# ---------------------------------------------------------------------------
# 5. Per-cover pause_duration 0 (older versions) becomes 1
# ---------------------------------------------------------------------------

class TestPauseDurationZero:
    def test_model_normalizes(self) -> None:
        assert CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                      "pause_duration": 0}).pause_duration == 1
        assert CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                      "pause_duration": None}).pause_duration is None
        assert CoverConfig.from_dict({"entity_id": "cover.a", "name": "A",
                                      "pause_duration": 45}).pause_duration == 45

    @pytest.mark.asyncio
    async def test_storage_load_normalizes_raw(self, storage, mock_store) -> None:
        data = _base_config()
        data["covers"]["cover.a"]["pause_duration"] = 0
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage.covers["cover.a"].pause_duration == 1
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 1
        mock_store.async_delay_save.assert_called()

    @pytest.mark.asyncio
    async def test_storage_load_leaves_valid_data_untouched(self, storage, mock_store) -> None:
        data = _base_config()
        data["covers"]["cover.a"]["pause_duration"] = 30
        data["migrations"] = list(_ALL_MIGRATIONS)
        mock_store.async_load.return_value = data
        await storage.async_load()
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 30
        mock_store.async_delay_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_normalizes(self, storage) -> None:
        await storage.async_load()
        data = _base_config()
        data["covers"]["cover.a"]["pause_duration"] = 0
        await storage.async_import_data(data)
        assert storage._data["covers"]["cover.a"]["pause_duration"] == 1
        assert storage.covers["cover.a"].pause_duration == 1


# ---------------------------------------------------------------------------
# 6. Daytime windows joined to the night conditions' offsets (no gap)
# ---------------------------------------------------------------------------

def _time_rule(rule_id: str, ctype: ConditionType, offset: int, *, enabled: bool = True) -> Rule:
    return Rule(id=rule_id, name=rule_id, enabled=enabled,
                conditions=[Condition(type=ctype, params={"offset": offset})])


# (daytime condition, night condition whose offset joins it, evening side?)
JOINED = [
    (ConditionType.TIME_AFTER_SUNRISE, ConditionType.TIME_AFTER_SUNSET, True),
    (ConditionType.TIME_AFTER_DAWN, ConditionType.TIME_AFTER_DUSK, True),
    (ConditionType.TIME_BEFORE_SUNSET, ConditionType.TIME_BEFORE_SUNRISE, False),
    (ConditionType.TIME_BEFORE_DUSK, ConditionType.TIME_BEFORE_DAWN, False),
]


def _scan(engine, day, night, night_offset):
    """Every minute over a day: (day, night) results."""
    for minute in range(0, 24 * 60):
        now = MIDNIGHT + minute * 60 + 1
        yield (
            now,
            _sun_eval(engine, day, now),
            _sun_eval(engine, night, now, offset=night_offset),
        )


class TestNoGapWithOffsets:
    @pytest.mark.parametrize(("day", "night", "_evening"), JOINED)
    def test_default_complementary_without_offsets(self, engine, mock_storage,
                                                   day, night, _evening) -> None:
        mock_storage.rules = {"n": _time_rule("n", night, 0), "d": _time_rule("d", day, 0)}
        for now, a, b in _scan(engine, day, night, 0):
            assert a != b, (day, night, (now - MIDNIGHT) / H)

    @pytest.mark.parametrize(("day", "night", "evening"), JOINED)
    def test_no_gap_with_offset(self, engine, mock_storage, day, night, evening) -> None:
        offset = 15 if evening else -15
        mock_storage.rules = {"n": _time_rule("n", night, offset), "d": _time_rule("d", day, 0)}
        for now, a, b in _scan(engine, day, night, offset):
            assert a or b, (day, night, (now - MIDNIGHT) / H)

    def test_after_dusk_plus_15_example(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "close": _time_rule("close", ConditionType.TIME_AFTER_DUSK, 15),
            "open": _time_rule("open", ConditionType.TIME_AFTER_DAWN, 0),
        }
        now = DUSK + 10 * 60
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DUSK, now, offset=15) is False
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DAWN, now) is True
        # ends exactly when the closing rule starts
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DAWN, DUSK + 15 * 60) is False
        assert _sun_eval(engine, ConditionType.TIME_AFTER_DUSK, DUSK + 15 * 60, offset=15) is True

    def test_largest_positive_offset_wins(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, 10),
            "b": _time_rule("b", ConditionType.TIME_AFTER_SUNSET, 40),
            "c": _time_rule("c", ConditionType.TIME_AFTER_SUNSET, -20),
        }
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 39 * 60) is True
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 41 * 60) is False

    def test_negative_offsets_do_not_shorten(self, engine, mock_storage) -> None:
        mock_storage.rules = {"a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, -30)}
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET - 10 * 60) is True
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 1) is False

    def test_disabled_rules_ignored(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, 30, enabled=False),
        }
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNSET + 10 * 60) is False

    def test_morning_lead_from_negative_before_sunrise(self, engine, mock_storage) -> None:
        mock_storage.rules = {
            "a": _time_rule("a", ConditionType.TIME_BEFORE_SUNRISE, -30),
            "b": _time_rule("b", ConditionType.TIME_BEFORE_SUNRISE, 20),
        }
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_SUNSET, SUNRISE - 20 * 60) is True
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_SUNSET, SUNRISE - 40 * 60) is False
        # dawn side is independent
        assert _sun_eval(engine, ConditionType.TIME_BEFORE_DUSK, DAWN - 20 * 60) is False

    def test_offset_does_not_extend_daytime_window_start(self, engine, mock_storage) -> None:
        # the evening extension does not change the morning start
        mock_storage.rules = {"a": _time_rule("a", ConditionType.TIME_AFTER_SUNSET, 30)}
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNRISE - 60) is False
        assert _sun_eval(engine, ConditionType.TIME_AFTER_SUNRISE, SUNRISE + 60) is True

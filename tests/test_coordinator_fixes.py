"""Coordinator fixes (lost commands, pause origin, missing sensors, statuses)."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.cover_automatic.coordinator import (
    PRE_LOCK_STATES_KEY,
    SETTLE_TIME,
    WIND_STATE_KEY,
)
from custom_components.cover_automatic.models import CoverConfig, CoverStatus
from homeassistant.util import dt as dt_util
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401
from tests.test_coordinator_robustness import TIME, _cover, _raw, _states, _use_covers

LOGBOOK = "custom_components.cover_automatic.coordinator.i18n.text"


@pytest.fixture(autouse=True)
def _close_created_coroutines(mock_hass):
    """Close coroutines handed to the mocked async_create_task (no warnings)."""
    def _create(coro):
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()
    mock_hass.async_create_task.side_effect = _create


def _log_keys(coordinator) -> list[dict]:
    return [c.args[3] for c in coordinator.log_storage.add_entry.call_args_list]


def _in_grace(coordinator) -> None:
    coordinator._startup_time = time.monotonic()


# ----------------------------------------------------- 1. lost command
class TestLostCommandCounterOrder:
    def _setup(self, coordinator, mock_hass, mock_storage, current: int = 100) -> None:
        _use_covers(mock_storage, {"cover.t": _raw()})
        mock_storage.covers = {"cover.t": _cover()}
        mock_storage.enabled = True
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        coordinator._last_positions["cover.t"] = 0
        coordinator._last_sent_target["cover.t"] = 0
        coordinator._last_command_time["cover.t"] = 0.0
        coordinator._move_start["cover.t"] = (0.0, 100, 0)
        coordinator._pending_settle.add("cover.t")
        coordinator.data = {"covers": {"cover.t": {"target_position": 0}}}
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("open", {"current_position": current}),
        })

    def test_counter_order_during_settle_is_manual(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage)
        with patch(TIME) as mock_time, patch.object(coordinator, "pause_cover") as pause:
            # During settle: the cover starts closing, then the user sends it back up
            mock_time.monotonic.return_value = 5.0
            coordinator._handle_cover_state_change(
                "cover.t", MockState("open", {"current_position": 100}),
                MockState("closing", {"current_position": 90}))
            mock_time.monotonic.return_value = 100.0
            coordinator._handle_cover_state_change(
                "cover.t", MockState("opening", {"current_position": 95}),
                MockState("open", {"current_position": 100}))
        pause.assert_called_once()
        assert not coordinator._lost_command_retries
        mock_hass.async_create_task.assert_not_called()

    def test_position_change_during_settle_counts(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 5.0
            coordinator._handle_cover_state_change(
                "cover.t", MockState("open", {"current_position": 100}),
                MockState("open", {"current_position": 80}))
        assert coordinator._resend_if_lost("cover.t", 100) is False

    def test_no_movement_still_resent(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 100.0
            assert coordinator._resend_if_lost("cover.t", 100) is True

    def test_not_resent_when_automation_off(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage)
        mock_storage.enabled = False
        assert coordinator._resend_if_lost("cover.t", 100) is False

    def test_not_resent_when_target_changed(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage)
        coordinator.data = {"covers": {"cover.t": {"target_position": 50}}}
        assert coordinator._resend_if_lost("cover.t", 100) is False
        coordinator.data = {"covers": {}}
        assert coordinator._resend_if_lost("cover.t", 100) is False

    @pytest.mark.asyncio
    async def test_new_command_clears_movement_flag(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage)
        coordinator._pending_settle.clear()
        coordinator._last_positions["cover.t"] = 100
        coordinator._moved_since_command = {"cover.t"}
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 9999.0
            await coordinator.async_apply_positions()
        assert "cover.t" not in coordinator._moved_since_command
        assert coordinator._move_start["cover.t"][1:] == (100, 0)


# ------------------------------------------------------- 2. pause origin
class TestPauseOrigin:
    def _setup(self, coordinator, mock_hass, mock_storage) -> CoverConfig:
        _use_covers(mock_storage, {"cover.t": _raw(min_position_change=1)})
        mock_storage.enabled = True
        mock_storage.pause_resume_on_match = True
        mock_storage.pause_duration = 30
        mock_storage.rules = {"r": SimpleNamespace(name="R")}
        cover = CoverConfig(entity_id="cover.t", name="t")
        mock_storage.covers = {"cover.t": cover}
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        state = MockState("open", {"current_position": 100})
        state.last_changed = state.last_updated = dt_util.utcnow() - timedelta(seconds=300)
        mock_hass.states.get.side_effect = _states({"cover.t": state})
        coordinator.engine = MagicMock()
        coordinator.engine.evaluate_cover.return_value = SimpleNamespace(
            position=100, tilt_position=None, rule_id="r")
        return cover

    def _pause_and_match(self, coordinator, cover, manual: bool | None) -> bool:
        with patch(TIME) as mock_time, patch(LOGBOOK, return_value="txt"):
            mock_time.monotonic.return_value = 0.0
            if manual is None:
                coordinator.pause_cover(cover)
            else:
                coordinator.pause_cover(cover, manual=manual)
            mock_time.monotonic.return_value = 1000.0
            return coordinator._resume_on_match(cover)

    def test_explicit_pause_not_resumed(self, coordinator, mock_hass, mock_storage) -> None:
        cover = self._setup(coordinator, mock_hass, mock_storage)
        assert self._pause_and_match(coordinator, cover, manual=False) is False
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED

    def test_manual_override_pause_resumed(self, coordinator, mock_hass, mock_storage) -> None:
        cover = self._setup(coordinator, mock_hass, mock_storage)
        assert self._pause_and_match(coordinator, cover, manual=None) is True
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO

    def test_restored_pause_treated_as_manual(self, coordinator, mock_hass, mock_storage) -> None:
        cover = self._setup(coordinator, mock_hass, mock_storage)
        coordinator._cover_states["cover.t"] = CoverStatus.PAUSED
        coordinator._pause_manual = None  # no origin known (restart)
        with patch(TIME) as mock_time, patch(LOGBOOK, return_value="txt"):
            mock_time.monotonic.return_value = 1000.0
            assert coordinator._resume_on_match(cover) is True

    @pytest.mark.asyncio
    async def test_services_pass_explicit_origin(self) -> None:
        from custom_components.cover_automatic.services import async_setup_services

        hass = MagicMock()
        hass.services.has_service.return_value = False
        coord = MagicMock()
        cover = MagicMock()
        coord.storage.covers = {"cover.t": cover}
        entry = MagicMock()
        entry.runtime_data.coordinator = coord
        hass.config_entries.async_entries.return_value = [entry]
        await async_setup_services(hass)
        handlers = {c.args[1]: c.args[2] for c in hass.services.async_register.call_args_list}
        await handlers["pause"](SimpleNamespace(data={"entity_id": "cover.t"}))
        await handlers["pause_all"](SimpleNamespace(data={}))
        assert [c.kwargs for c in coord.pause_cover.call_args_list] == [
            {"manual": False}, {"manual": False}]


# ------------------------------------------------ 3. missing lock sensor
class TestMissingLockSensor:
    def _setup(self, coordinator, mock_hass, mock_storage, sensor_state: str | None) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(status="locked", lock_sensor="binary_sensor.w")})
        mock_storage._data[PRE_LOCK_STATES_KEY] = {"cover.t": "auto"}
        coordinator.log_storage = MagicMock()
        states = {"cover.t": MockState("open", {"current_position": 100})}
        if sensor_state is not None:
            states["binary_sensor.w"] = MockState(sensor_state)
        mock_hass.states.get.side_effect = _states(states)
        coordinator._restore_cover_states()

    def test_released_after_grace_and_logged_once(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, None)
        coordinator._sync_cover_statuses()
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        missing = [d for d in _log_keys(coordinator) if d.get("key") == "lock_sensor_missing"]
        assert missing == [{"key": "lock_sensor_missing", "sensor": "binary_sensor.w"}]

    def test_kept_during_grace(self, coordinator, mock_hass, mock_storage) -> None:
        _in_grace(coordinator)
        self._setup(coordinator, mock_hass, mock_storage, None)
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        assert not [d for d in _log_keys(coordinator) if d.get("key") == "lock_sensor_missing"]

    @pytest.mark.parametrize("state", ["unavailable", "unknown"])
    def test_unusable_state_still_unknown(self, coordinator, mock_hass, mock_storage, state) -> None:
        self._setup(coordinator, mock_hass, mock_storage, state)
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED

    def test_logged_again_after_sensor_came_back(self, coordinator, mock_hass, mock_storage) -> None:
        coordinator.log_storage = MagicMock()
        raw = _raw(lock_sensor="binary_sensor.w")
        coordinator._track_missing_lock_sensor("cover.t", raw)
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("off")})
        coordinator._track_missing_lock_sensor("cover.t", raw)
        mock_hass.states.get.side_effect = _states({})
        coordinator._track_missing_lock_sensor("cover.t", raw)
        keys = [d["key"] for d in _log_keys(coordinator)]
        assert keys == ["lock_sensor_missing", "lock_sensor_missing"]

    def test_moves_not_blocked_by_missing_sensor(self, coordinator, mock_hass, mock_storage) -> None:
        raw = _raw(lock_sensor="binary_sensor.w")
        assert coordinator._blocked_by_unknown_lock("cover.t", raw, 0, 100) is False

    def test_move_blocked_logged_once_per_episode(self, coordinator, mock_hass, mock_storage) -> None:
        coordinator.log_storage = MagicMock()
        raw = _raw(lock_sensor="binary_sensor.w", inverted=True)
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("unavailable")})
        # Inverted: raw 100 = logical 0 (closed), raw 0 = logical 100
        assert coordinator._blocked_by_unknown_lock("cover.t", raw, 100, 0) is True
        assert coordinator._blocked_by_unknown_lock("cover.t", raw, 100, 0) is True
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("off")})
        assert coordinator._blocked_by_unknown_lock("cover.t", raw, 100, 0) is False
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("unknown")})
        assert coordinator._blocked_by_unknown_lock("cover.t", raw, 100, 0) is True
        blocked = [d for d in _log_keys(coordinator) if d["key"] == "move_blocked_window_unknown"]
        assert blocked == [
            {"key": "move_blocked_window_unknown", "sensor": "binary_sensor.w", "position": 0},
        ] * 2


# ------------------------------------------------- 4. restored wind state
class TestRestoredWindDropped:
    def _setup(self, coordinator, mock_hass, mock_storage, states: dict) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(status="wind_protected")})
        mock_storage._data[WIND_STATE_KEY] = True
        mock_storage._data[PRE_LOCK_STATES_KEY] = {"cover.t": "auto"}
        mock_storage.wind_sensor = "sensor.wind"
        mock_storage.wind_speed_threshold = 50.0
        mock_storage.wind_speed_hysteresis = 10.0
        coordinator.log_storage = MagicMock()
        mock_hass.states.get.side_effect = _states(states)
        _in_grace(coordinator)
        coordinator._restore_cover_states()
        assert coordinator.wind_protected is True

    def _end_grace(self, coordinator) -> None:
        coordinator._startup_time = -999.0

    def _dropped(self, coordinator) -> list[dict]:
        return [d for d in _log_keys(coordinator) if d.get("key") == "wind_restore_dropped"]

    @pytest.mark.parametrize("states", [{}, {"sensor.wind": MockState("unavailable")}])
    def test_dropped_at_grace_end(self, coordinator, mock_hass, mock_storage, states) -> None:
        self._setup(coordinator, mock_hass, mock_storage, states)
        coordinator._sync_cover_statuses()
        assert coordinator.wind_protected is True  # still in grace
        self._end_grace(coordinator)
        coordinator._sync_cover_statuses()
        coordinator._sync_cover_statuses()
        assert coordinator.wind_protected is False
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        assert mock_storage._data[WIND_STATE_KEY] is False
        assert self._dropped(coordinator) == [{"key": "wind_restore_dropped", "sensor": "sensor.wind"}]

    def test_kept_when_sensor_reported(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, {"sensor.wind": MockState("60")})
        coordinator._sync_cover_statuses()
        mock_hass.states.get.side_effect = _states({"sensor.wind": MockState("unavailable")})
        self._end_grace(coordinator)
        with patch.object(coordinator, "_send_wind_position"):
            coordinator._sync_cover_statuses()
        assert coordinator.wind_protected is True
        assert not self._dropped(coordinator)


# ------------------------------------------- 5. statuses vs auto_enabled
class TestStatusFollowsAutoEnabled:
    def _locked(self, coordinator, mock_hass, mock_storage, auto: bool, pre: CoverStatus) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(auto_enabled=auto)})
        coordinator._cover_states["cover.t"] = CoverStatus.LOCKED
        coordinator._pre_lock_states["cover.t"] = pre
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("open", {"current_position": 100})})

    def test_unlock_manual_with_auto_enabled_gives_auto(self, coordinator, mock_hass, mock_storage) -> None:
        self._locked(coordinator, mock_hass, mock_storage, True, CoverStatus.MANUAL)
        coordinator._unlock_cover("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO

    @pytest.mark.parametrize("pre", [CoverStatus.AUTO, CoverStatus.PAUSED])
    def test_unlock_auto_with_auto_disabled_gives_manual(
        self, coordinator, mock_hass, mock_storage, pre
    ) -> None:
        self._locked(coordinator, mock_hass, mock_storage, False, pre)
        mock_storage._data["covers"]["cover.t"]["pause_until"] = dt_util.now().timestamp() + 600
        coordinator._unlock_cover("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.MANUAL

    def test_refused_resume_while_locked_restores_auto(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        coordinator._cover_states["cover.t"] = CoverStatus.LOCKED
        coordinator._pre_lock_states["cover.t"] = CoverStatus.MANUAL
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("on")})
        coordinator.resume_cover("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        assert coordinator._pre_lock_states["cover.t"] == CoverStatus.AUTO

    def test_wind_release_with_automation_off_gives_manual(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(auto_enabled=False)})
        coordinator._cover_states["cover.t"] = CoverStatus.WIND_PROTECTED
        coordinator._pre_lock_states["cover.t"] = CoverStatus.AUTO
        coordinator._deactivate_wind_protection()
        assert coordinator._cover_states["cover.t"] == CoverStatus.MANUAL
        assert "cover.t" not in coordinator._post_protective_exit

    def test_wind_release_unknown_window_prelock_follows_auto(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        coordinator._cover_states["cover.t"] = CoverStatus.WIND_PROTECTED
        coordinator._pre_lock_states["cover.t"] = CoverStatus.MANUAL
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("unavailable")})
        coordinator._deactivate_wind_protection()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        assert coordinator._pre_lock_states["cover.t"] == CoverStatus.AUTO


# ------------------------------------------------- 6. vent and pauses
class TestVentKeepsPause:
    def _setup(self, coordinator, mock_hass, mock_storage, position: int) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(vent_sensor="binary_sensor.v", vent_position=30)})
        coordinator._cover_states["cover.t"] = CoverStatus.PAUSED
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("open", {"current_position": position})})

    def test_vent_open_keeps_pause_and_raises(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, 10)
        coordinator._handle_contact_sensor_change(
            "binary_sensor.v", [], ["cover.t"], MockState("off"), MockState("on"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED
        assert coordinator._last_positions["cover.t"] == 30
        assert mock_hass.async_create_task.call_count == 1
        mock_storage.update_cover_status.assert_not_called()

    def test_vent_open_above_floor_no_command(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, 80)
        coordinator._handle_contact_sensor_change(
            "binary_sensor.v", [], ["cover.t"], MockState("off"), MockState("on"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED
        mock_hass.async_create_task.assert_not_called()

    def test_vent_close_keeps_pause(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, 80)
        coordinator._handle_contact_sensor_change(
            "binary_sensor.v", [], ["cover.t"], MockState("on"), MockState("off"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED
        mock_storage.update_cover_status.assert_not_called()


# --------------------------------------- 7. stillness from position changes
class TestStillnessFromPositionChanges:
    def _setup(self, coordinator, mock_hass, mock_storage) -> CoverConfig:
        _use_covers(mock_storage, {"cover.t": _raw(min_position_change=1)})
        mock_storage.enabled = True
        mock_storage.pause_resume_on_match = True
        mock_storage.rules = {}
        cover = CoverConfig(entity_id="cover.t", name="t")
        coordinator._cover_states["cover.t"] = CoverStatus.PAUSED
        coordinator._paused_at = {"cover.t": 0.0}
        # Zigbee: attributes re-reported every few seconds
        state = MockState("open", {"current_position": 100, "linkquality": 80})
        state.last_updated = dt_util.utcnow() - timedelta(seconds=2)
        state.last_changed = dt_util.utcnow() - timedelta(seconds=2)
        mock_hass.states.get.side_effect = _states({"cover.t": state})
        coordinator.engine = MagicMock()
        coordinator.engine.evaluate_cover.return_value = SimpleNamespace(
            position=100, tilt_position=None, rule_id=None)
        return cover

    def _run(self, coordinator, cover, now: float) -> bool:
        with patch(TIME) as mock_time, patch(LOGBOOK, return_value="txt"):
            mock_time.monotonic.return_value = now
            return coordinator._resume_on_match(cover)

    def test_attribute_reports_do_not_block(self, coordinator, mock_hass, mock_storage) -> None:
        cover = self._setup(coordinator, mock_hass, mock_storage)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 100.0
            coordinator._record_motion(
                "cover.t", MockState("open", {"current_position": 90}),
                MockState("open", {"current_position": 100}))
            mock_time.monotonic.return_value = 995.0
            # attribute-only report: not a position change
            coordinator._record_motion(
                "cover.t", MockState("open", {"current_position": 100, "linkquality": 70}),
                MockState("open", {"current_position": 100, "linkquality": 80}))
        assert coordinator._position_changed_at["cover.t"] == 100.0
        assert self._run(coordinator, cover, 1000.0) is True

    def test_recent_position_change_blocks(self, coordinator, mock_hass, mock_storage) -> None:
        cover = self._setup(coordinator, mock_hass, mock_storage)
        coordinator._position_changed_at = {"cover.t": 1000.0 - SETTLE_TIME + 5}
        assert self._run(coordinator, cover, 1000.0) is False

    def test_fallback_last_changed(self, coordinator, mock_hass, mock_storage) -> None:
        cover = self._setup(coordinator, mock_hass, mock_storage)
        coordinator._position_changed_at = None
        assert self._run(coordinator, cover, 1000.0) is False


# ------------------------------------------------- 8. travel learning
class TestTravelLearningGrowth:
    def test_uncapped_sample_averaged(self, coordinator, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(measured_travel_time=20.0)})
        coordinator._move_start["cover.t"] = (0.0, 0, 100)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 24.0
            coordinator._measure_travel("cover.t", MockState("open", {"current_position": 100}))
        mock_storage.update_cover_measured_travel.assert_called_once_with("cover.t", 22.0)

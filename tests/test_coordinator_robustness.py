"""Coordinator robustness (restart, lost commands, wind tasks, vent events)."""
# ruff: noqa: F811 -- pytest fixtures are imported from sibling test modules
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cover_automatic.const import SET_POSITION_FEATURE_FLAG, TILT_FEATURE_FLAG
from custom_components.cover_automatic.coordinator import (
    MAX_LOST_COMMAND_RETRIES,
    PRE_LOCK_STATES_KEY,
    WIND_STATE_KEY,
)
from custom_components.cover_automatic.models import CoverConfig, CoverStatus
from tests.test_coordinator import MockState, coordinator, mock_hass, mock_storage  # noqa: F401

TIME = "custom_components.cover_automatic.coordinator.time_mod"


def _states(mapping: dict[str, MockState]):
    return lambda entity_id: mapping.get(entity_id)


def _use_covers(mock_storage, covers: dict[str, dict]) -> None:
    mock_storage._data = {"covers": covers, "facades": {}, "rules": {}, "scenarios": {}}
    mock_storage.get_cover_raw.side_effect = lambda e: mock_storage._data["covers"].get(e)


def _cover(entity_id: str = "cover.t", auto: bool = True) -> MagicMock:
    cover = MagicMock(spec=CoverConfig)
    cover.entity_id = entity_id
    cover.auto_enabled = auto
    cover.pause_duration = 30
    return cover


def _raw(**extra) -> dict:
    return {
        "auto_enabled": True, "inverted": False, "min_position_change": 5,
        "min_time_between_changes": 0, "lock_position": 100, "vent_position": 30, **extra,
    }


# ---------------------------------------------------------------- 1. restart
class TestRestartProtection:
    def test_locked_and_venting_restored_with_pre_lock(self, coordinator, mock_storage) -> None:
        _use_covers(mock_storage, {
            "cover.a": {"status": "locked"},
            "cover.b": {"status": "venting"},
            "cover.c": {"status": "wind_protected"},
        })
        mock_storage._data[PRE_LOCK_STATES_KEY] = {"cover.a": "manual"}
        coordinator._restore_cover_states()
        assert coordinator._cover_states["cover.a"] == CoverStatus.LOCKED
        assert coordinator._pre_lock_states["cover.a"] == CoverStatus.MANUAL
        assert coordinator._cover_states["cover.b"] == CoverStatus.VENTING
        assert "cover.b" not in coordinator._pre_lock_states
        # No wind state stored: wind status is not restored
        assert coordinator._cover_states["cover.c"] == CoverStatus.AUTO

    def test_restored_lock_kept_while_sensor_unknown(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(status="locked", lock_sensor="binary_sensor.w")})
        coordinator._restore_cover_states()
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("unknown"),
            "cover.t": MockState("open", {"current_position": 100}),
        })
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        # Sensor reports closed: normal unlock
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("off"),
            "cover.t": MockState("open", {"current_position": 100}),
        })
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO

    @pytest.mark.asyncio
    async def test_apply_never_lowers_with_unknown_window(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        coordinator.data = {"covers": {"cover.t": {"target_position": 0}}}
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("unavailable"),
            "cover.t": MockState("open", {"current_position": 100}),
        })
        await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_allows_raising_with_unknown_window(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        coordinator.data = {"covers": {"cover.t": {"target_position": 60}}}
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("unknown"),
            "cover.t": MockState("open", {"current_position": 20}),
        })
        await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_called_once_with(
            "cover", "set_cover_position", {"entity_id": "cover.t", "position": 60}, blocking=False)

    @pytest.mark.asyncio
    async def test_apply_unknown_window_inverted_cover(self, coordinator, mock_hass, mock_storage) -> None:
        """Inverted cover: logical 0 (closed) is raw 100 -- still blocked."""
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w", inverted=True)})
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        coordinator.data = {"covers": {"cover.t": {"target_position": 0}}}
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("unknown"),
            "cover.t": MockState("open", {"current_position": 0}),  # logical 100
        })
        await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_not_called()

    def test_wind_release_with_unknown_window_locks_in_place(self, coordinator, mock_hass, mock_storage) -> None:
        # MANUAL kept as pre-lock status only while automation is off
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w", auto_enabled=False)})
        coordinator._cover_states["cover.t"] = CoverStatus.WIND_PROTECTED
        coordinator._pre_lock_states["cover.t"] = CoverStatus.MANUAL
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("unavailable"),
            "cover.t": MockState("open", {"current_position": 100}),
        })
        coordinator._deactivate_wind_protection()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        assert coordinator._pre_lock_states["cover.t"] == CoverStatus.MANUAL
        mock_hass.services.async_call.assert_not_called()


# ---------------------------------------------------------- 2. lost command
class TestLostCommand:
    def _setup(self, coordinator, mock_hass, mock_storage, current: int) -> None:
        _use_covers(mock_storage, {"cover.t": _raw()})
        mock_storage.covers = {"cover.t": _cover()}
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

    @pytest.mark.asyncio
    async def test_resend_instead_of_pause(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, current=100)
        with patch(TIME) as mock_time, patch.object(coordinator, "pause_cover") as pause:
            mock_time.monotonic.return_value = 9999.0
            await coordinator.async_apply_positions()
        pause.assert_not_called()
        assert coordinator._lost_command_retries["cover.t"] == 1
        assert "cover.t" in coordinator._pending_settle
        assert coordinator._last_command_time["cover.t"] == 9999.0
        assert mock_hass.async_create_task.call_count == 1
        mock_hass.services.async_call.assert_called_once_with(
            "cover", "set_cover_position", {"entity_id": "cover.t", "position": 0}, blocking=False)

    @pytest.mark.asyncio
    async def test_bounded_retries_then_pause(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, current=100)
        coordinator._lost_command_retries = {"cover.t": MAX_LOST_COMMAND_RETRIES}
        with patch(TIME) as mock_time, patch.object(coordinator, "pause_cover") as pause:
            mock_time.monotonic.return_value = 9999.0
            await coordinator.async_apply_positions()
        pause.assert_called_once()
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_move_is_still_manual(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, current=60)
        with patch(TIME) as mock_time, patch.object(coordinator, "pause_cover") as pause:
            mock_time.monotonic.return_value = 9999.0
            await coordinator.async_apply_positions()
        pause.assert_called_once()

    def test_state_change_path_resends(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, current=100)
        with patch(TIME) as mock_time, patch.object(coordinator, "pause_cover") as pause:
            # Past the 30 s settle time, within the travel measurement window
            mock_time.monotonic.return_value = 100.0
            coordinator._handle_cover_state_change(
                "cover.t", MockState("open", {"current_position": 100}),
                MockState("open", {"current_position": 100, "friendly_name": "x"}),
            )
        pause.assert_not_called()
        assert coordinator._lost_command_retries["cover.t"] == 1

    def test_arrival_resets_retries(self, coordinator, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw()})
        coordinator._lost_command_retries = {"cover.t": 1}
        coordinator._move_start["cover.t"] = (0.0, 100, 0)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 10.0
            coordinator._measure_travel("cover.t", MockState("closed", {"current_position": 0}))
        assert "cover.t" not in coordinator._lost_command_retries


# ------------------------------------------------------- 3. wind commands
class TestWindCommandTasks:
    @pytest.mark.asyncio
    async def test_recheck_before_each_send(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage.command_stagger = 1.0
        coordinator._wind_protected = True
        coordinator._cover_states = {"cover.a": CoverStatus.WIND_PROTECTED, "cover.b": CoverStatus.WIND_PROTECTED}

        async def sleep(_delay):
            # Window opened on cover.b during the stagger
            coordinator._cover_states["cover.b"] = CoverStatus.LOCKED

        with patch("asyncio.sleep", side_effect=sleep), patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 500.0
            await coordinator._send_staggered_commands([("cover.a", 100), ("cover.b", 100)])
        assert mock_hass.services.async_call.call_count == 1
        assert coordinator._last_command_time["cover.a"] == 500.0

    @pytest.mark.asyncio
    async def test_wind_dropped_during_stagger(self, coordinator, mock_hass, mock_storage) -> None:
        mock_storage.command_stagger = 1.0
        coordinator._wind_protected = True
        coordinator._cover_states = {"cover.a": CoverStatus.WIND_PROTECTED, "cover.b": CoverStatus.WIND_PROTECTED}

        async def sleep(_delay):
            coordinator._wind_protected = False

        with patch("asyncio.sleep", side_effect=sleep):
            await coordinator._send_staggered_commands([("cover.a", 100), ("cover.b", 100)])
        assert mock_hass.services.async_call.call_count == 1

    @pytest.mark.asyncio
    async def test_task_cancelled_on_deactivation_reactivation_and_shutdown(
        self, coordinator, mock_hass, mock_storage
    ) -> None:
        loop = asyncio.get_running_loop()
        mock_hass.async_create_task.side_effect = loop.create_task
        mock_storage.command_stagger = 30.0
        _use_covers(mock_storage, {"cover.a": _raw(), "cover.b": _raw()})
        coordinator._wind_protected = True
        coordinator._activate_wind_protection()
        first = next(iter(coordinator._wind_tasks))
        # Re-activation: no parallel sequences
        coordinator._activate_wind_protection()
        await asyncio.sleep(0)
        assert first.cancelled() or first.done()
        assert len(coordinator._wind_tasks) == 1
        second = next(iter(coordinator._wind_tasks))
        coordinator._wind_protected = False
        coordinator._deactivate_wind_protection()
        await asyncio.sleep(0)
        assert second.cancelled()
        assert not coordinator._wind_tasks
        # Only the first cover of each sequence was sent before cancellation
        assert mock_hass.services.async_call.call_count <= 2

        coordinator._wind_protected = True
        coordinator._activate_wind_protection()
        third = next(iter(coordinator._wind_tasks))
        with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_shutdown",
                   new_callable=AsyncMock):
            await coordinator.async_shutdown()
        await asyncio.sleep(0)
        assert third.cancelled()


# ------------------------------------------------------- 4. vent events
class TestVentSensorEvents:
    def _setup(self, coordinator, mock_hass, mock_storage, status: CoverStatus, vent: str) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(vent_sensor="binary_sensor.v")})
        coordinator._cover_states["cover.t"] = status
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.v": MockState(vent),
            "cover.t": MockState("closed", {"current_position": 0}),
        })

    def test_back_from_unavailable_keeps_pause(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, CoverStatus.PAUSED, "off")
        coordinator._handle_contact_sensor_change(
            "binary_sensor.v", [], ["cover.t"], MockState("unavailable"), MockState("off"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED

    def test_old_state_none_ignored(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, CoverStatus.AUTO, "on")
        coordinator._handle_contact_sensor_change("binary_sensor.v", [], ["cover.t"], None, MockState("on"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        mock_hass.services.async_call.assert_not_called()

    def test_same_state_ignored(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, CoverStatus.PAUSED, "off")
        coordinator._handle_contact_sensor_change(
            "binary_sensor.v", [], ["cover.t"], MockState("off"), MockState("off"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.PAUSED

    def test_real_transition_still_handled(self, coordinator, mock_hass, mock_storage) -> None:
        self._setup(coordinator, mock_hass, mock_storage, CoverStatus.AUTO, "on")
        coordinator._handle_contact_sensor_change(
            "binary_sensor.v", [], ["cover.t"], MockState("off"), MockState("on"))
        assert coordinator._cover_states["cover.t"] == CoverStatus.VENTING


# ---------------------------------------------- 5. wind activation guard
class TestWindActivationUnknownLock:
    def test_locked_unknown_window_stays_locked(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w"), "cover.u": _raw()})
        coordinator._cover_states = {"cover.t": CoverStatus.LOCKED, "cover.u": CoverStatus.AUTO}
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("unavailable")})
        with patch.object(coordinator, "_send_staggered_commands") as staggered:
            coordinator._activate_wind_protection()
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED
        assert coordinator._cover_states["cover.u"] == CoverStatus.WIND_PROTECTED
        assert [c[0] for c in staggered.call_args[0][0]] == ["cover.u"]


# ---------------------------------------------- 6. wind state persisted
class TestWindPersistence:
    def test_activation_and_release_persisted(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {})
        mock_storage.wind_sensor = "sensor.wind"
        mock_storage.wind_speed_threshold = 50.0
        mock_storage.wind_speed_hysteresis = 10.0
        mock_hass.states.get.side_effect = _states({"sensor.wind": MockState("60")})
        coordinator._check_wind_protection()
        assert mock_storage._data[WIND_STATE_KEY] is True
        mock_storage._schedule_save.assert_called()
        mock_hass.states.get.side_effect = _states({"sensor.wind": MockState("20")})
        coordinator._check_wind_protection()
        assert mock_storage._data[WIND_STATE_KEY] is False

    def test_restored_and_kept_while_sensor_unavailable(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(status="wind_protected")})
        mock_storage._data[WIND_STATE_KEY] = True
        mock_storage._data[PRE_LOCK_STATES_KEY] = {"cover.t": "auto"}
        mock_storage.wind_sensor = "sensor.wind"
        mock_storage.wind_speed_threshold = 50.0
        # Kept during the startup grace period (dropped at its end
        # when the sensor never reported, see test_coordinator_fixes)
        import time
        coordinator._startup_time = time.monotonic()
        coordinator._restore_cover_states()
        assert coordinator.wind_protected is True
        assert coordinator._cover_states["cover.t"] == CoverStatus.WIND_PROTECTED
        mock_hass.states.get.side_effect = _states({"sensor.wind": MockState("unavailable")})
        with patch.object(coordinator, "_send_wind_position") as send:
            coordinator._sync_cover_statuses()
        assert coordinator.wind_protected is True
        assert coordinator._cover_states["cover.t"] == CoverStatus.WIND_PROTECTED
        send.assert_not_called()

    def test_not_restored_when_wind_feature_removed(self, coordinator, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(status="wind_protected")})
        mock_storage._data[WIND_STATE_KEY] = True
        coordinator._restore_cover_states()
        assert coordinator.wind_protected is False
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        assert mock_storage._data[WIND_STATE_KEY] is False

    def test_pre_lock_states_persisted(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        coordinator._cover_states["cover.t"] = CoverStatus.MANUAL
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.w": MockState("on"),
            "cover.t": MockState("open", {"current_position": 100}),
        })
        coordinator._handle_contact_sensor_change(
            "binary_sensor.w", ["cover.t"], [], MockState("off"), MockState("on"))
        assert mock_storage._data[PRE_LOCK_STATES_KEY] == {"cover.t": "manual"}


# ------------------------------------------------------------ 7. resume
class TestResume:
    def test_resume_refused_while_window_unknown(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        coordinator._cover_states["cover.t"] = CoverStatus.LOCKED
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("unknown")})
        coordinator.resume_cover("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.LOCKED

    def test_resume_drops_pre_lock_state(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        coordinator._cover_states["cover.t"] = CoverStatus.LOCKED
        coordinator._pre_lock_states["cover.t"] = CoverStatus.MANUAL
        mock_hass.states.get.side_effect = _states({"binary_sensor.w": MockState("off")})
        coordinator.resume_cover("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.AUTO
        assert "cover.t" not in coordinator._pre_lock_states


# --------------------------------------------- 8./9. venting after pause
class TestVenting:
    def test_pause_expiry_raises_to_vent_position(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(vent_sensor="binary_sensor.v", pause_until=1.0)})
        coordinator._cover_states["cover.t"] = CoverStatus.PAUSED
        mock_hass.states.get.side_effect = _states({
            "binary_sensor.v": MockState("on"),
            "cover.t": MockState("closed", {"current_position": 0}),
        })
        coordinator._sync_cover_statuses()
        assert coordinator._cover_states["cover.t"] == CoverStatus.VENTING
        mock_hass.services.async_call.assert_called_once_with(
            "cover", "set_cover_position", {"entity_id": "cover.t", "position": 30}, blocking=False)

    def test_vent_tilt_applied(self, coordinator, mock_hass, mock_storage) -> None:
        raw = _raw(vent_sensor="binary_sensor.v", vent_tilt_position=40,
                   supports_tilt=True, inverted_tilt=True)
        _use_covers(mock_storage, {"cover.t": raw})
        mock_hass.states.get.side_effect = _states({"cover.t": MockState("closed", {"current_position": 0})})
        with patch.object(coordinator, "_schedule_tilt") as tilt:
            coordinator._enter_venting("cover.t", raw, "test")
        tilt.assert_called_once()
        assert tilt.call_args[0][:2] == ("cover.t", 60)

    def test_vent_tilt_needs_tilt_support(self, coordinator, mock_hass, mock_storage) -> None:
        raw = _raw(vent_sensor="binary_sensor.v", vent_tilt_position=40, supports_tilt=False)
        _use_covers(mock_storage, {"cover.t": raw})
        mock_hass.states.get.side_effect = _states({"cover.t": MockState("closed", {"current_position": 0})})
        with patch.object(coordinator, "_schedule_tilt") as tilt:
            coordinator._enter_venting("cover.t", raw, "test")
        tilt.assert_not_called()


# ---------------------------------------------- 10. serialised apply
class TestApplySerialised:
    @pytest.mark.asyncio
    async def test_apply_cycles_do_not_interleave(self, coordinator) -> None:
        events: list[str] = []

        async def fake_apply() -> None:
            events.append("start")
            await asyncio.sleep(0.01)
            events.append("end")

        with patch.object(coordinator, "_async_apply_positions_locked", side_effect=fake_apply):
            await asyncio.gather(coordinator.async_apply_positions(), coordinator.async_apply_positions())
        assert events == ["start", "end", "start", "end"]


# -------------------------------------------------- 11. travel learning
class TestTravelLearning:
    def test_short_move_not_learned(self, coordinator, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw()})
        coordinator._move_start["cover.t"] = (0.0, 0, 40)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 30.0
            coordinator._measure_travel("cover.t", MockState("open", {"current_position": 40}))
        mock_storage.update_cover_measured_travel.assert_not_called()

    def test_sample_clamped_to_growth_limit(self, coordinator, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(measured_travel_time=20.0)})
        coordinator._move_start["cover.t"] = (0.0, 0, 100)
        with patch(TIME) as mock_time:
            mock_time.monotonic.return_value = 90.0  # late poll: 90 s sample
            coordinator._measure_travel("cover.t", MockState("open", {"current_position": 100}))
        # sample capped at 30 s (a capped sample is not averaged down again)
        mock_storage.update_cover_measured_travel.assert_called_once_with("cover.t", 30.0)


# ------------------------------------------------ 12. set_cover_manual
class TestSetManualKeepsProtection:
    @pytest.mark.parametrize("status", [CoverStatus.LOCKED, CoverStatus.VENTING])
    def test_protective_status_kept(self, coordinator, mock_storage, status) -> None:
        coordinator._cover_states["cover.t"] = status
        coordinator.set_cover_manual("cover.t")
        assert coordinator._cover_states["cover.t"] == status
        mock_storage.update_cover_status.assert_not_called()

    def test_auto_becomes_manual(self, coordinator) -> None:
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        coordinator.set_cover_manual("cover.t")
        assert coordinator._cover_states["cover.t"] == CoverStatus.MANUAL


# --------------------------------------------- 13. open/close-only covers
class TestOpenCloseOnlyCovers:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("target", "service", "current"), [(70, "open_cover", 0), (30, "close_cover", 100)])
    async def test_apply_uses_open_close(self, coordinator, mock_hass, mock_storage, target, service, current) -> None:
        _use_covers(mock_storage, {"cover.t": _raw()})
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        coordinator.data = {"covers": {"cover.t": {"target_position": target}}}
        features = 1 | 2  # OPEN | CLOSE, no SET_POSITION
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("open" if current else "closed", {"supported_features": features}),
        })
        await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_called_once_with(
            "cover", service, {"entity_id": "cover.t"}, blocking=False)
        assert coordinator._last_positions["cover.t"] == (100 if target >= 50 else 0)

    @pytest.mark.asyncio
    async def test_no_repeat_when_already_at_end(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw()})
        coordinator._cover_states["cover.t"] = CoverStatus.AUTO
        coordinator.data = {"covers": {"cover.t": {"target_position": 30}}}
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("closed", {"supported_features": 3}),
        })
        await coordinator.async_apply_positions()
        mock_hass.services.async_call.assert_not_called()

    def test_lock_opens_open_close_cover(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {"cover.t": _raw(lock_sensor="binary_sensor.w")})
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("closed", {"supported_features": 3}),
        })
        coordinator._lock_cover("cover.t", 100)
        mock_hass.services.async_call.assert_called_once_with(
            "cover", "open_cover", {"entity_id": "cover.t"}, blocking=False)

    def test_set_position_feature_used_when_supported(self, coordinator, mock_hass) -> None:
        features = int(SET_POSITION_FEATURE_FLAG) | int(TILT_FEATURE_FLAG)
        mock_hass.states.get.side_effect = _states({
            "cover.t": MockState("open", {"supported_features": features}),
        })
        assert coordinator._supports_set_position("cover.t") is True
        assert coordinator._effective_position("cover.t", 30) == 30


# ------------------------------------------------------ 14. after import
class TestReconcileAfterImport:
    def test_reconcile(self, coordinator, mock_hass, mock_storage) -> None:
        _use_covers(mock_storage, {
            "cover.on": _raw(auto_enabled=True),
            "cover.off": _raw(auto_enabled=False),
            "cover.locked_off": _raw(auto_enabled=False),
        })
        coordinator._cover_states = {
            "cover.on": CoverStatus.MANUAL,
            "cover.off": CoverStatus.AUTO,
            "cover.locked_off": CoverStatus.LOCKED,
        }
        assert coordinator.reconcile_after_import() is None
        assert coordinator._cover_states["cover.on"] == CoverStatus.AUTO
        assert coordinator._cover_states["cover.off"] == CoverStatus.MANUAL
        assert coordinator._cover_states["cover.locked_off"] == CoverStatus.LOCKED

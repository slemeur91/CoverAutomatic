"""Integration reload for covers that no longer react (cover option).

Some integrations stop executing commands without reporting any error: the
cover neither moves nor changes state until the integration is reloaded.
With the cover option reload_on_no_move, the first command such a cover
ignores (a lost command, see MotionMixin._resend_if_lost) reloads the
integration instead of resending; the apply cycle then commands every cover
of that integration again.

Mixin of CoverAutomaticCoordinator: it uses the coordinator's attributes."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.helpers import entity_registry as er

from . import coordinator_common as common
from . import i18n
from .const import DOMAIN, LOG_EVENT_STATUS
from .coordinator_common import (
    _UNUSABLE_STATES,
    MANUAL_OVERRIDE_TOLERANCE,
    RELOAD_AVAILABLE_TIMEOUT,
    RELOAD_COOLDOWN,
    RELOAD_GATHER_DELAY,
)

# Same logger as the coordinator: the split does not change the log names
_LOGGER = logging.getLogger(__package__ + ".coordinator")


class ReloadMixin:
    """Integration reload for covers that no longer react."""

    def _reload_entry_of(self, entity_id: str) -> Any | None:
        """Config entry providing a cover, when it can be reloaded."""
        reg_entry = er.async_get(self.hass).async_get(entity_id)
        entry_id = getattr(reg_entry, "config_entry_id", None)
        if not entry_id:
            return None
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain == DOMAIN or not entry.supports_unload:
            return None
        return entry

    def _reload_held(self, entity_id: str) -> bool:
        """Whether a cover waits for or goes through an integration reload.

        Such a cover gets no command and no manual override detection: it
        still reports the position it had before the ignored command.
        """
        return (
            entity_id in self._runtime_dict("_reload_waiting")
            or entity_id in self._runtime_set("_reload_running")
        )

    def _request_reload(self, entity_id: str, cover_raw: dict[str, Any], current: int) -> bool:
        """Ask for a reload of the cover's integration (first ignored command).

        Returns False when the option is off, the integration cannot be
        reloaded or was reloaded less than RELOAD_COOLDOWN ago: the command
        is then resent as usual.
        """
        if not cover_raw.get("reload_on_no_move"):
            return False
        entry = self._reload_entry_of(entity_id)
        if entry is None:
            _LOGGER.warning("[%s] Integration of the cover cannot be reloaded: command resent", entity_id)
            return False
        last = self._runtime_dict("_reload_last").get(entry.entry_id)
        if last is not None and common.time_mod.monotonic() - last < RELOAD_COOLDOWN:
            _LOGGER.warning(
                "[%s] %s reloaded %d s ago: command resent instead",
                entity_id, entry.title, int(common.time_mod.monotonic() - last),
            )
            return False
        self._runtime_dict("_reload_waiting")[entity_id] = entry.entry_id
        _LOGGER.warning(
            "[%s] No reaction to the command (still at %d%%): reloading %s",
            entity_id, current, entry.title,
        )
        self._log(LOG_EVENT_STATUS, entity_id, f"No move: reload of {entry.title} requested",
                  {"key": "reload_requested", "integration": entry.title})
        self._logbook(i18n.text(self.hass, "reload_requested", integration=entry.title), entity_id)
        tasks = self._runtime_dict("_reload_tasks")
        if entry.entry_id not in tasks:
            coro = self._async_reload_integration(entry.entry_id)
            name = f"{DOMAIN}_reload_{entry.domain}"
            if self.config_entry is not None:
                task = self.config_entry.async_create_background_task(self.hass, coro, name)
            else:
                task = self.hass.async_create_task(coro)
            tasks[entry.entry_id] = task
        return True

    def _reload_wait_report(self, entity_id: str, new_state: Any) -> bool:
        """State report of a cover held for a reload: True when it is ignored.

        While the reload runs, every report is ignored (unavailable, then the
        restored state). While it waits, a cover that moves after all
        (someone moved it, or the command arrived late) leaves the reload
        request and is handled as usual.
        """
        if entity_id in self._runtime_set("_reload_running"):
            return True
        waiting = self._runtime_dict("_reload_waiting")
        if entity_id not in waiting:
            return False
        move = self._move_start.get(entity_id)
        pos = self._raw_position(new_state)
        if new_state.state in ("opening", "closing") or (
            move is not None and pos is not None and abs(pos - move[1]) > MANUAL_OVERRIDE_TOLERANCE
        ):
            waiting.pop(entity_id, None)
            _LOGGER.info("[%s] Cover moved: integration reload request dropped", entity_id)
            return False
        return True

    async def _async_reload_integration(self, entry_id: str) -> None:
        """Reload one integration once for every cover waiting for it."""
        try:
            await asyncio.sleep(RELOAD_GATHER_DELAY)
            waiting = self._runtime_dict("_reload_waiting")
            requested = sorted(e for e, eid in waiting.items() if eid == entry_id)
            for entity_id in requested:
                waiting.pop(entity_id, None)
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if not requested or entry is None:
                return
            # Every managed cover of this integration: all are commanded again
            reg = er.async_get(self.hass)
            covers = [
                e for e in self.storage.covers
                if getattr(reg.async_get(e), "config_entry_id", None) == entry_id
            ]
            running = self._runtime_set("_reload_running")
            running.update(covers)
            self._runtime_dict("_reload_last")[entry_id] = common.time_mod.monotonic()
            _LOGGER.warning("Reloading %s (%s) for %s", entry.title, entry.domain, ", ".join(requested))
            try:
                ok = bool(await self.hass.config_entries.async_reload(entry_id))
            except Exception:  # noqa: BLE001 -- any failure of the other integration
                _LOGGER.exception("Reload of %s failed", entry.title)
                ok = False
            try:
                await self._async_wait_available(covers)
            finally:
                for entity_id in covers:
                    self._resync_after_reload(entity_id)
                running.difference_update(covers)
            names = [self._cover_name(e) for e in requested]
            self._log(LOG_EVENT_STATUS, None,
                      f"{entry.title} reloaded ({len(covers)} covers)" if ok else f"Reload of {entry.title} failed",
                      {"key": "reload_done" if ok else "reload_failed", "integration": entry.title,
                       "count": len(covers), "covers": ", ".join(names)})
            self._logbook(i18n.text(
                self.hass, "reload_done" if ok else "reload_failed", integration=entry.title, count=len(covers),
            ))
            self._schedule_refresh()
        finally:
            self._runtime_dict("_reload_tasks").pop(entry_id, None)

    async def _async_wait_available(self, covers: list[str]) -> None:
        """Wait until the covers report a usable state again (bounded)."""
        for _ in range(RELOAD_AVAILABLE_TIMEOUT):
            if all(
                (state := self.hass.states.get(e)) is not None and state.state not in _UNUSABLE_STATES
                for e in covers
            ):
                return
            await asyncio.sleep(1)
        _LOGGER.warning("Covers still unavailable %d s after the reload", RELOAD_AVAILABLE_TIMEOUT)

    def _resync_after_reload(self, entity_id: str) -> None:
        """Start again from the position read after the reload.

        The integration may report another position than before: it becomes
        the expected one (no false manual pause), and the next apply cycle
        commands the cover again, without waiting for the time hysteresis.
        """
        self._pending_settle.discard(entity_id)
        self._move_start.pop(entity_id, None)
        self._last_sent_target.pop(entity_id, None)
        self._runtime_set("_moved_since_command").discard(entity_id)
        if self._lost_command_retries:
            self._lost_command_retries.pop(entity_id, None)
        self._update_last_position_from_state(entity_id)
        self._post_protective_exit.add(entity_id)

    def _cover_name(self, entity_id: str) -> str:
        cover = self.storage.covers.get(entity_id)
        return cover.name if cover is not None and cover.name else entity_id

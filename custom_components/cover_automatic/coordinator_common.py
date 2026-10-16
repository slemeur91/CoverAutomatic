"""Constants and helpers shared by the coordinator and its mixins.

time_mod and dt_util are reached through this module (common.time_mod...)
so tests can patch the clock of every coordinator module at once."""
from __future__ import annotations

import time as time_mod  # noqa: F401 -- patched by tests
from typing import Any

from homeassistant.util import dt as dt_util  # noqa: F401 -- patched by tests

# Tolerance for manual override detection (positions)
MANUAL_OVERRIDE_TOLERANCE = 2

# Seconds to ignore position changes after our own commands
SETTLE_TIME = 30

# Margin added to a cover's travel time to get its settle time (seconds)
TRAVEL_TIME_MARGIN = 5

# Travel time measurement: minimum move (%) and maximum duration (seconds).
# Short moves of polled covers are dominated by the polling interval (the
# arrival is only seen at the next poll), which inflated the learned value:
# only moves of at least half the full travel are used.
MIN_MEASURED_DISTANCE = 50
MAX_MEASURED_TRAVEL = 300
# A new travel sample may exceed the previous measurement by this factor at
# most (one late poll must not double the settle time).
MAX_TRAVEL_GROWTH = 1.5

# Resends of a position command the cover did not react to at all (lost
# radio/cloud command) before it is treated as a manual override.
MAX_LOST_COMMAND_RETRIES = 2

# Keys written by the coordinator into storage._data (runtime state only,
# never part of the configuration): wind protection and pre-lock statuses,
# so protections survive a Home Assistant restart.
WIND_STATE_KEY = "wind_protected_state"
PRE_LOCK_STATES_KEY = "pre_lock_states"

_UNUSABLE_STATES = ("unavailable", "unknown")

# Resume on match (manual pause ended when the cover is back at its rule's
# position): no check during the first seconds of a pause -- a cover moved by
# hand still reports its start position, which may be the rule's target --
# and the cover must be still (no report for SETTLE_TIME).
RESUME_MATCH_GRACE = 60

# Seconds after startup before applying positions (sensor stabilization)
STARTUP_GRACE_PERIOD = 120


def _is_safety(result: Any) -> bool:
    """Whether an engine result comes from a safety rule."""
    return result is not None and getattr(result, "safety", False) is True

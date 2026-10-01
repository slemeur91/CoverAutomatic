"""Sun position calculations for CoverAutomatic."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from astral import Observer
from astral.sun import zenith_and_azimuth
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from .models import Facade

_LOGGER = logging.getLogger(__name__)

SUN_ENTITY_ID = "sun.sun"

# Astral event names (civil twilight: sun 6 degrees below the horizon)
SUN_EVENT_DAWN = "dawn"
SUN_EVENT_DUSK = "dusk"


def get_sun_position(hass: HomeAssistant) -> tuple[float, float] | None:
    """Get current sun azimuth and elevation.

    Returns:
        Tuple of (azimuth, elevation) in degrees, or None if unavailable.
    """
    sun_state = hass.states.get(SUN_ENTITY_ID)
    if sun_state is None:
        _LOGGER.warning("Sun entity not available")
        return None

    try:
        azimuth_val = sun_state.attributes.get("azimuth")
        elevation_val = sun_state.attributes.get("elevation")
        if azimuth_val is None or elevation_val is None:
            return None
        return (float(azimuth_val), float(elevation_val))
    except (ValueError, TypeError) as err:
        _LOGGER.error("Error reading sun position: %s", err)
        return None


def is_sun_on_facade(
    hass: HomeAssistant, facade: Facade,
) -> bool:
    """Check if sun is shining on a facade.

    Facade azimuth values are real compass bearings (house rotation already
    applied at configuration time).

    Args:
        hass: Home Assistant instance
        facade: Facade to check

    Returns:
        True if sun is currently shining on the facade.
    """
    position = get_sun_position(hass)
    if position is None:
        return False

    azimuth, elevation = position
    return _sun_hits_facade(facade, azimuth, elevation)


def _sun_hits_facade(facade: Facade, azimuth: float, elevation: float) -> bool:
    """Return True if a sun at azimuth/elevation shines on the facade.

    Shared by is_sun_on_facade and get_facade_sun_times so the sensor times
    match when the automation sees the sun on the facade. The sun is never
    "on" a facade while below the horizon, whatever a negative min_elevation
    says.
    """
    if elevation < max(facade.min_elevation, 0.0):
        return False
    return _azimuth_in_facade(azimuth, facade.azimuth_start, facade.azimuth_end)


def get_sun_event_time(
    hass: HomeAssistant, event: str, day_offset: int = 0
) -> float | None:
    """Get a sun event (sunrise/sunset) timestamp for today + day_offset days."""
    event_dt = get_astral_event_date(
        hass, event, dt_util.now() + timedelta(days=day_offset)
    )
    if event_dt is None:
        return None
    return event_dt.timestamp()


def get_sunrise_time(hass: HomeAssistant) -> float | None:
    """Get today's sunrise time as timestamp."""
    sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, dt_util.now())
    if sunrise is None:
        return None
    return sunrise.timestamp()


def get_sunset_time(hass: HomeAssistant) -> float | None:
    """Get today's sunset time as timestamp."""
    sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, dt_util.now())
    if sunset is None:
        return None
    return sunset.timestamp()


def get_dawn_time(hass: HomeAssistant) -> float | None:
    """Get today's dawn (civil twilight start, sun 6 deg below horizon)."""
    return get_sun_event_time(hass, SUN_EVENT_DAWN)


def get_dusk_time(hass: HomeAssistant) -> float | None:
    """Get today's dusk (civil twilight end, sun 6 deg below horizon)."""
    return get_sun_event_time(hass, SUN_EVENT_DUSK)


# Facade sun times: coarse scan of the local day, then bisection at each edge
_SCAN_STEP = timedelta(minutes=5)
_BOUNDARY_PRECISION = timedelta(seconds=15)

# (day, facade geometry, location) -> (entry, exit); holds the current day only
_SUN_TIME_CACHE: dict[tuple[Any, ...], tuple[str | None, str | None]] = {}


def _azimuth_in_facade(azimuth: float, start: float, end: float) -> bool:
    """Return True if the azimuth lies within the facade range (wrap-aware).

    start == end means a full circle (every azimuth): the models normalise
    360 to 0, so a 0-360 range entered by the user is stored as 0/0 and must
    not shrink to the single bearing 0.
    """
    if start == end:
        return True
    if start <= end:
        return start <= azimuth <= end
    return azimuth >= start or azimuth <= end


def get_facade_sun_times(
    hass: HomeAssistant, facade: Facade,
) -> tuple[str | None, str | None]:
    """Return today's sun entry and exit time (local HH:MM) for a facade.

    Derived from the real sun path at the configured location with the same
    test as is_sun_on_facade, so the times match when the automation sees the
    sun on the facade. Facade azimuth values are real compass bearings (house
    rotation already applied at configuration time).

    The local day is scanned every 5 minutes and each edge is refined by
    bisection to 15 s. A facade lit in two separate periods (wrap-around
    facade in summer) reports the first one. Returns (None, None) when the
    sun does not reach it today (or during polar night). Computed once per
    day and facade, both sensors share the result.
    """
    today = dt_util.now().date()
    key = (
        today,
        facade.azimuth_start,
        facade.azimuth_end,
        facade.min_elevation,
        hass.config.latitude,
        hass.config.longitude,
        hass.config.elevation,
    )
    cached = _SUN_TIME_CACHE.get(key)
    if cached is not None:
        return cached

    # Drop entries of previous days so the cache cannot grow unbounded
    for stale in [k for k in _SUN_TIME_CACHE if k[0] != today]:
        del _SUN_TIME_CACHE[stale]
    result = _compute_facade_sun_times(hass, facade, today)
    _SUN_TIME_CACHE[key] = result
    return result


def _compute_facade_sun_times(
    hass: HomeAssistant, facade: Facade, day: date,
) -> tuple[str | None, str | None]:
    """Scan the local day for the first period the sun shines on the facade."""
    # Observer built directly (HA's get_astral_location is deprecated and
    # removed in 2027.7).
    observer = Observer(
        hass.config.latitude, hass.config.longitude, hass.config.elevation or 0
    )

    def lit(moment: datetime) -> bool:
        zenith, azimuth = zenith_and_azimuth(observer, moment)
        return _sun_hits_facade(facade, azimuth, 90.0 - zenith)

    day_start = dt_util.start_of_local_day(day)
    day_end = dt_util.start_of_local_day(day + timedelta(days=1))

    entry: datetime | None = None
    exit_: datetime | None = None
    previous: datetime | None = None
    moment = day_start
    while moment < day_end:
        if lit(moment):
            if entry is None:
                entry = _boundary(lit, moment, previous) if previous else moment
            exit_ = moment
        elif entry is not None:
            exit_ = _boundary(lit, exit_, moment)
            break
        previous = moment
        moment += _SCAN_STEP

    if entry is None or exit_ is None:
        return None, None
    return _format_local(entry), _format_local(exit_)


def _boundary(
    lit: Callable[[datetime], bool], inside: datetime, outside: datetime,
) -> datetime:
    """Bisect between a lit and an unlit moment, return the lit side of the edge."""
    while abs(outside - inside) > _BOUNDARY_PRECISION:
        middle = inside + (outside - inside) / 2
        if lit(middle):
            inside = middle
        else:
            outside = middle
    return inside


def _format_local(moment: datetime) -> str:
    return dt_util.as_local(moment).strftime("%H:%M")

// CoverAutomatic panel -- shared constants.

/* ============================================================
 * Curated scenario icon choices (Material Design Icons)
 * ============================================================ */
// Keep in sync with MAX_CONDITION_GROUPS in models.py
export const MAX_CONDITION_GROUPS = 10;

export const SCENARIO_ICON_CHOICES = [
  "mdi:home", "mdi:home-variant",
  "mdi:white-balance-sunny", "mdi:weather-sunny",
  "mdi:weather-night", "mdi:moon-waning-crescent",
  "mdi:weather-sunset", "mdi:weather-sunset-up",
  "mdi:snowflake", "mdi:weather-partly-cloudy",
  "mdi:airplane", "mdi:beach",
  "mdi:car", "mdi:office-building",
  "mdi:television", "mdi:movie-open",
  "mdi:gamepad-variant", "mdi:music",
  "mdi:sofa", "mdi:bed",
  "mdi:silverware-fork-knife", "mdi:coffee",
  "mdi:account-group", "mdi:party-popper",
  "mdi:sleep", "mdi:shield-home",
  "mdi:fire", "mdi:weather-windy",
  "mdi:gesture-tap", "mdi:cog",
  "mdi:star", "mdi:heart",
];

/* ============================================================
 * Condition type metadata
 * ============================================================ */
export const CONDITION_TYPES = [
  "sun_on_facade", "sun_elevation_above", "sun_elevation_below",
  "temperature_above", "temperature_below", "temperature_comfort", "outdoor_vs_indoor",
  "room_occupied",
  "time_between", "time_after_sunrise", "time_after_sunset",
  "time_before_sunrise", "time_before_sunset",
  "time_after_dawn", "time_before_dawn", "time_after_dusk", "time_before_dusk",
  "state_is", "numeric_state", "weather_is", "day_of_week", "workday"
];

export const CONDITION_PARAMS = {
  sun_on_facade: [],
  sun_elevation_above: [{ key: "elevation", type: "number", default: 10, step: 0.5 }],
  sun_elevation_below: [{ key: "elevation", type: "number", default: 60, step: 0.5 }],
  temperature_above: [{ key: "temperature", type: "number", default: 25 }],
  temperature_below: [{ key: "temperature", type: "number", default: 15 }],
  temperature_comfort: [{ key: "mode", type: "select", options: ["heating", "neutral", "cooling"], default: "cooling" }],
  outdoor_vs_indoor: [
    { key: "operator", type: "select", options: ["cooler", "warmer"], default: "cooler" },
    { key: "delta", type: "number", default: 0, step: 0.5 }
  ],
  room_occupied: [],
  time_between: [
    { key: "start_time", type: "time", default: "08:00" },
    { key: "end_time", type: "time", default: "20:00" }
  ],
  time_after_sunrise: [{ key: "offset", type: "number", default: 0 }],
  time_after_sunset: [{ key: "offset", type: "number", default: 0 }],
  time_before_sunrise: [{ key: "offset", type: "number", default: 0 }],
  time_before_sunset: [{ key: "offset", type: "number", default: -60 }],
  time_after_dawn: [{ key: "offset", type: "number", default: 0 }],
  time_before_dawn: [{ key: "offset", type: "number", default: 0 }],
  time_after_dusk: [{ key: "offset", type: "number", default: 0 }],
  time_before_dusk: [{ key: "offset", type: "number", default: 0 }],
  state_is: [
    { key: "entity_id", type: "entity", default: "" },
    { key: "state", type: "text", default: "on" }
  ],
  numeric_state: [
    { key: "entity_id", type: "entity", default: "" },
    { key: "operator", type: "select", options: ["above", "below"], default: "above" },
    { key: "value", type: "number", default: 0 },
    { key: "hysteresis", type: "number", default: 0, step: 0.1 }
  ],
  weather_is: [{ key: "weather", type: "multiselect", options: ["sunny", "clear-night", "partlycloudy", "cloudy", "fog", "rainy", "pouring", "lightning", "lightning-rainy", "hail", "snowy", "snowy-rainy", "windy", "windy-variant", "exceptional"], default: ["sunny"] }],
  day_of_week: [{ key: "days", type: "dayselect", default: ["mon","tue","wed","thu","fri"] }],
  workday: [{ key: "state", type: "select", options: ["on", "off"], default: "on" }]
};

// "Add condition" menu, grouped by theme. The legacy "state_is" and
// "numeric_state" types are no longer offered (existing ones keep working and
// can be converted): the "Entités" group creates native HA conditions.
export const CONDITION_MENU = [
  { label: "cond_group_sun", items: ["sun_on_facade", "sun_elevation_above", "sun_elevation_below"].map(t => ({ value: t, label: "cond_" + t })) },
  { label: "cond_group_temperature", items: ["temperature_above", "temperature_below", "temperature_comfort", "outdoor_vs_indoor"].map(t => ({ value: t, label: "cond_" + t })) },
  { label: "cond_group_presence", items: [{ value: "room_occupied", label: "cond_room_occupied" }] },
  { label: "cond_group_time", items: ["time_between", "time_after_dawn", "time_before_dawn", "time_after_sunrise", "time_before_sunrise", "time_after_sunset", "time_before_sunset", "time_after_dusk", "time_before_dusk", "day_of_week", "workday"].map(t => ({ value: t, label: "cond_" + t })) },
  { label: "cond_group_weather", items: [{ value: "weather_is", label: "cond_weather_is" }] },
  { label: "cond_group_entities", items: [
    { value: "ha:state", label: "cond_menu_ha_state" },
    { value: "ha:numeric", label: "cond_menu_ha_numeric" },
    { value: "ha:yaml", label: "cond_menu_ha_yaml" },
  ] },
];

// Condition types that depend on a cover/facade context and cannot be
// evaluated in the editor preview (mirrors engine _CONTEXT_DEPENDENT_TYPES).
export const CONTEXT_DEPENDENT_TYPES = ["sun_on_facade", "temperature_comfort", "outdoor_vs_indoor", "room_occupied"];

// Compass bearing of each facade direction (before house rotation).
export const FACADE_BEARINGS = { north: 0, east: 90, south: 180, west: 270 };

// Colour of each house side on the compass and in its legend.
export const FACADE_SIDE_COLORS = { north: "#7da7c8", east: "#7fb89e", south: "#c4a979", west: "#c98969" };

// Same orientation as the compass of the settings: south at the top.
export const DIRECTION_ARROWS = {
  north: "\u2193",
  east: "\u2190",
  south: "\u2191",
  west: "\u2192"
};

// Integer cover settings and their range (cover/update schema: plain int).
export const COVER_INT_LIMITS = {
  pause_duration: [1, 480],
  lock_position: [0, 100],
  vent_position: [0, 100],
  lock_tilt_position: [0, 100],
  vent_tilt_position: [0, 100],
  min_position_change: [1, 50],
  min_time_between_changes: [60, 3600],
  travel_time: [1, 300],
};

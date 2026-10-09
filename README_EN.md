<p align="center">
  <img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/custom_components/cover_automatic/brand/logo@2x.png" alt="CoverAutomatic logo" width="331">
</p>

<h1 align="center">CoverAutomatic V2</h1>

<p align="center"><strong>Custom integration for Home Assistant: smart, automatic control of covers (roller shutters, blinds, sun shades, roof windows).</strong></p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistant&logoColor=white" alt="HACS Custom"></a>
  <a href="https://github.com/slemeur91/CoverAutomatic/releases/latest"><img src="https://img.shields.io/github/v/release/slemeur91/CoverAutomatic?label=Version" alt="Latest version"></a>
  <a href="https://github.com/slemeur91/CoverAutomatic/actions/workflows/ci.yml"><img src="https://github.com/slemeur91/CoverAutomatic/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/LICENSE"><img src="https://img.shields.io/github/license/slemeur91/CoverAutomatic" alt="License"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.3%2B-03a9f4?logo=homeassistant&logoColor=white" alt="Home Assistant 2026.3+">
</p>

<p align="center">🇫🇷 <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/README.md">Version française</a> · 📖 <a href="https://github.com/slemeur91/CoverAutomatic/wiki">Wiki</a> (in French)</p>

---

> **ℹ️ This is a fork**
>
> This repository is a **fork** of [CoverAutomatic by @crandler](https://github.com/crandler/CoverAutomatic).
> It is based on the original version **1.62.1** and adds many changes gathered in **V2**
> (see [What's new in V2](#whats-new-in-v2)).
> For the original version, its documentation and its issue tracker, go to the original repository.
> For this V2, use this repository: [github.com/slemeur91/CoverAutomatic](https://github.com/slemeur91/CoverAutomatic).

---

## Disclaimer

**NO WARRANTY – NO LIABILITY**

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement.

In no event shall the authors be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from the software, its use or any other dealings with it.

**By using this software, you acknowledge that:**
- a wrong cover position may affect the safety or thermal comfort of your home;
- you alone are responsible for testing and validating its behaviour;
- the authors accept no liability for damage to property or equipment.

---

## Features

- **Sun-based automation** – automatic shading when the sun reaches a facade
- **Temperature aware** – indoor and outdoor, with comfort setpoints per room
- **Outdoor air compared to the room** – to air the room when it is cooler outside, or to keep the heat out
- **Occupancy** – "room occupied" condition based on an occupancy sensor per cover
- **Weather** – reacts to conditions (sunny, cloudy, rain, thunderstorm…)
- **Schedules** – open / close at a fixed time or relative to sunrise / sunset, dawn or dusk
- **Advanced rules** – conditions on any entity (Home Assistant conditions), negated conditions (NOT),
  AND / OR groups, priorities
- **Safety rule** – acts even when paused, in manual mode, wind protected or with automation off (fire alarm…)
- **Scenarios** – switch between modes such as "Everyday", "Summer", "Holiday"; each rule selects its scenarios
- **Manual control respected** – automatic pause after a manual move, resumed at the end of the pause or as soon as
  the cover is back at the position requested by its rule
- **Cover travel time** – learned automatically, for reliable detection of manual moves
- **Open window** – the cover moves to its lock position or keeps its current position; automation is
  blocked while the window is open
- **Tilted window** – minimum venting position, automation continues above it
- **Wind protection** – configurable fallback position above a wind threshold
- **Sun arrival / departure times** – for each facade, computed from the real sun path
- **Hysteresis** – limits motor wear (minimum position change and minimum delay between two moves)
- **Inverted covers** – supported (100 % = closed)
- **Dashboard card and sensors** – follow each cover (active rule, target position, pause end) and the
  covers that are paused, in manual mode or locked
- **Activity log** – history of moves and status changes, filterable per cover
- **Backup / restore** – of the whole configuration, from the panel or with a service
- **Fully graphical configuration** – everything is done in the Home Assistant interface, no YAML
- **Hardware independent** – works with any `cover` entity (Somfy, Velux, Shelly, Zigbee, Z-Wave…)

---

## What's new in V2

V2 gathers all changes made since the original version 1.61.1.

### French language
- The whole integration is translated: configuration panel, dashboard card, services and error messages,
  activity log and Home Assistant logbook, entities, facade devices, weather states and built-in scenarios.
- The language follows Home Assistant (English, German or French), with French typography where it applies.

### Rules
- **Home Assistant conditions**: any automation condition (state, numeric state, template, zone, sun…),
  entered with a form or in YAML, validated live (see [below](#conditions-on-any-entity-home-assistant-conditions)).
- **Condition groups and NOT**: for example (A OR B) AND (C OR D). A condition negated with NOT is never met
  while its sensor is unavailable, to avoid an unwanted move.
- **Scenarios per rule**: each rule selects the scenarios it applies in.
- **Dawn and dusk** (civil twilight), with an offset in minutes. The pairs "after sunrise / before sunset"
  and "after dawn / before dusk" are complementary: no gap and no overlap, even with offsets.
- **Outdoor air compared to the room**: "outdoor air cooler / warmer than the room", with a minimum difference.
  Ideal for airing or keeping the heat out; a single rule serves every room.
- **Room occupied**: an occupancy sensor per cover (binary sensor, person, select…) and the "Room occupied" condition
  (with NOT: "room free").
- **Safety rule**: it acts even when the cover is paused, in manual mode, wind protected or with automation off.
  It never overrides the lock of an open window and, between rules, priority decides.
  Typical use: the fire alarm.
- **Duplicate a rule**: the copy is created right below the original. ▲▼ buttons to order conditions, groups
  and priorities (keyboard and touch).

### Covers
- **Keep the position when the window opens**: a new choice in addition to the lock position. When the window
  opens, the cover can either move to its lock position (original behaviour) or stay where it is; in both
  cases automation is blocked while the window stays open.
- **Cover travel time**: entered or learned automatically, with a global default. It avoids false "manual" pauses
  on slow covers that do not report their position while moving.
- **Resume when the position matches the rule**: a pause caused by a manual move ends as soon as the cover
  is back at the position requested by its rule (moved back by hand, or the rule changed in the meantime).
- **Lost commands resent**: a command the cover did not execute (lost radio frame) is sent again,
  never after a manual counter-order.

### Settings
- Configurable **wind protection position** (instead of always opening fully).
- **Thresholds driven by an entity**: temperature setpoints and the sunshine threshold can follow an entity
  (`input_number`, sensor…), with the typed value as fallback.
- Configurable **"sun on the facade" behaviour**, globally then per cover (cold room, room within the
  comfort range, strong sunshine).
- **Temperature colours** of your choice: by action needed or like a thermometer.
- Settings reorganised (House, Sensors, Sun exposure, Wind, Automation, Backup) with
  "How does it work?" blocks and options greyed out when they have no effect.

### Entities and dashboard
- **Dashboard card** `custom:cover-automatic-card` (a new card, in addition to the panel, which changes nothing
  in the existing behaviour): one line per cover (position, active rule, status, remaining pause
  time, resume button, automation switch) and a global header (scenario, master switch, wind,
  number of covers paused / manual / locked, "Resume all" button).
- **Sensors per cover** (new, in addition to the existing switch and status): active rule, target position, position,
  comfort mode, pause end (see [Created entities](#created-entities)).
- **Global entities**: wind protection and number of covers paused, in manual mode or locked.
- Devices and entities are created and removed automatically when a cover or a facade is added or removed.

### Interface
- **Cover sheet** in collapsible sections: General, Window, Room, Sun exposure, Automation.
- **Rule editor**: collapsible conditions, draft kept, warning before losing unsaved changes.
- **Scenarios tab**: rules listed by priority, disabled rules greyed out, "Safety" badge.
- **Log** filterable per cover, with a button on the cover sheet.
- **Mobile**: cover sheet header reachable below the notch, short labels, scroll position and input kept.

### Reliability and safety
- **Window and wind**: the lock of an open window keeps priority over the wind during the whole storm;
  the locked / wind states survive a restart; an unknown window sensor never lowers the cover;
  a removed sensor no longer blocks the cover forever.
- **False manual pauses removed**: slow covers, rule change during a move, window closed
  while the cover moves to its lock position.
- **Backups**: complete export, validated import (out-of-range values, unknown references, migrations); the
  runtime state is no longer restored from the file.
- Three full code audits and more than 1,300 automated tests.

---

## Screenshots

The integration adds a panel to the Home Assistant sidebar. All configuration is done there, without YAML.
Click a thumbnail to enlarge it. *(The screenshots come from a French installation: the cover, room and rule names are in French.)*

<table>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/covers-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/covers-desktop.png" alt="Covers" /></a>
      <p align="center"><sub><b>Covers</b> – list, status, temperature, position, active rule</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/facades-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/facades-desktop.png" alt="Facades" /></a>
      <p align="center"><sub><b>Facades</b> – azimuths and assigned covers</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/scenarios-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/scenarios-desktop.png" alt="Scenarios" /></a>
      <p align="center"><sub><b>Scenarios</b> – rules per scenario, Safety badge</sub></p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/rule-editor.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/rule-editor.png" alt="Rule editor" /></a>
      <p align="center"><sub><b>Rule editor</b> – scenarios, covers, conditions</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/settings-house.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/settings-house.png" alt="Settings – House" /></a>
      <p align="center"><sub><b>Settings – House</b> – rotation and sunshine sector</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/settings-automation.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/settings-automation.png" alt="Settings – Automation" /></a>
      <p align="center"><sub><b>Settings – Automation</b> – global defaults</sub></p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/settings-sensors.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/settings-sensors.png" alt="Settings – Sensors" /></a>
      <p align="center"><sub><b>Settings – Sensors</b> – temperature setpoints</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/log-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/log-desktop.png" alt="Log" /></a>
      <p align="center"><sub><b>Log</b> – moves and status changes</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/cover-editor.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/cover-editor.png" alt="Cover sheet" /></a>
      <p align="center"><sub><b>Cover sheet</b> – side panel with sections</sub></p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/rules-desktop.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/rules-desktop.png" alt="Rules" /></a>
      <p align="center"><sub><b>Rules</b> – filter, priorities, Safety badge, conditions</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/settings-sun.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/settings-sun.png" alt="Settings – Sun exposure" /></a>
      <p align="center"><sub><b>Settings – Sun exposure</b> – behaviour of "Sun on facade"</sub></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/settings-wind.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/settings-wind.png" alt="Settings – Wind protection" /></a>
      <p align="center"><sub><b>Settings – Wind protection</b> – threshold, hysteresis, position</sub></p>
    </td>
  </tr>
</table>

<table>
  <tr>
    <td width="33%" align="center">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/card.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/card.png" alt="Dashboard card" width="320" /></a>
      <p><sub><b>Dashboard card</b> – position, active rule, temperature, status</sub></p>
    </td>
    <td width="33%" align="center">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/mobile-covers.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/mobile-covers.png" alt="Mobile – Covers" width="320" /></a>
      <p><sub><b>Mobile – Covers</b></sub></p>
    </td>
    <td width="33%" align="center">
      <a href="https://github.com/slemeur91/CoverAutomatic/blob/main/.github/screenshots/en/mobile-settings.png"><img src="https://raw.githubusercontent.com/slemeur91/CoverAutomatic/main/.github/screenshots/en/mobile-settings.png" alt="Mobile – Settings" width="320" /></a>
      <p><sub><b>Mobile – Settings</b> – sections in a horizontal bar</sub></p>
    </td>
  </tr>
</table>

## Requirements

- Home Assistant 2026.3.0 or newer
- HACS (Home Assistant Community Store) for installation through HACS
- Existing `cover` entities to control

---

## Installation

> If the original version by @crandler is already installed, remove it (or replace its folder) before installing this V2:
> both use the same `cover_automatic` folder. Your configuration (covers, facades, rules) is kept.

### Method 1: HACS (recommended)

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=slemeur91&repository=CoverAutomatic&category=integration)

#### Step 1: add the custom repository

1. Open Home Assistant
2. Go to **HACS** in the sidebar
3. Click the **three-dot menu** (top right)
4. Choose **Custom repositories**
5. In the dialog:
   - **Repository:** `https://github.com/slemeur91/CoverAutomatic`
   - **Type:** `Integration`
6. Click **Add**

#### Step 2: install the integration

1. In HACS, search for **CoverAutomatic**
2. Open it and click **Download**
3. Choose the latest version and confirm

#### Step 3: restart Home Assistant

1. **Settings** > **System** > **Restart**
2. Wait for Home Assistant to restart

#### Step 4: add the integration

1. **Settings** > **Devices & services**
2. Click **+ Add integration** (bottom right)
3. Search for **CoverAutomatic**
4. Confirm (nothing to enter)
5. A **CoverAutomatic** entry appears in the sidebar for all the configuration

---

### Method 2: manual installation

1. Download the latest version from [github.com/slemeur91/CoverAutomatic](https://github.com/slemeur91/CoverAutomatic)
   (**Code** > **Download ZIP** button, or the [releases](https://github.com/slemeur91/CoverAutomatic/releases) page)
2. Delete the old `config/custom_components/cover_automatic` folder if it exists
3. Copy the `custom_components/cover_automatic` folder into the `config/custom_components/` directory of Home Assistant
4. Restart Home Assistant
5. Add the integration through **Settings** > **Devices & services** > **Add integration**

After an update, reload the browser page (Ctrl/Cmd+Shift+R) to load the new panel.

---

## Configuration

After installation, everything is configured in the **CoverAutomatic** panel of the sidebar.
The [wiki](https://github.com/slemeur91/CoverAutomatic/wiki) (in French) describes each part of the integration, with screenshots.

1. **Covers** – add the `cover` entities to control; each cover has its own sheet (window, room, exposure, automation)
2. **Facades** – define the facades of the building by direction. For a new facade, the azimuth
   start / end are prefilled with the widest sun window of the chosen direction (90° on each side, house rotation
   applied, without the sector the sun never reaches at your latitude) and stay editable
3. **Rules** – create the automation rules from conditions (sun, temperature, time, weather, entities…).
   The list can be filtered by facade, cover and scenario.
   Conditions can be negated (NOT) and organised in groups, for example (A OR B) AND (C OR D);
   an existing rule can be duplicated as a starting point
4. **Scenarios** – define modes such as "Everyday", "Summer", "Holiday". Each rule selects its scenarios
   (all by default); within a scenario, a rule can also be temporarily disabled
5. **Settings** – sensors, temperature setpoints, sun exposure, wind protection, backup…
6. **Log** – history of moves and status changes, filterable per cover and per type

### Cover sheet

Clicking a cover in the **Covers** tab opens its sheet, organised in collapsible sections. A field left empty
uses the default value from the **Settings**.

| Section | Content |
|---------|---------|
| **General** | Automation enabled, facade, invert the open/close direction, inverted tilt |
| **Window** | *Open window*: sensor, **keep the current position** or move to the lock position (and its tilt). *Tilted window*: sensor, venting position (and its tilt) |
| **Room** | Indoor temperature sensor and cold / warm setpoints (number or entity), occupancy sensor and "room occupied" states |
| **Sun exposure** | "Sun on the facade" settings specific to this cover (or the global setting) |
| **Automation** | Pause duration, resume when the position matches the rule, minimum position change, minimum delay between changes, **cover travel time** (entered or measured) |

The "Show this cover's log" button opens the log filtered on this cover.

### Settings

| Tab | Content |
|-----|---------|
| **House** | House rotation, with compass (south at the top; position of the sun, sunshine sector in the colours of the four house sides, with their azimuths in a legend); choice to rotate the existing facades or not when the rotation changes |
| **Sensors** | Global indoor temperature sensor and cold / warm setpoints with their hysteresis; outdoor temperature sensor and hysteresis used by the rules; weather; workday |
| **Sun exposure** | Behaviour of "Sun on the facade" depending on the room temperature; sunshine sensor, strong-sunshine threshold and hysteresis |
| **Wind protection** | Wind sensor, threshold, hysteresis and **protection position** |
| **Automation** | *Pause after a manual command* (duration, resume when the position matches the rule); default *window positions*; *Moves* (minimum change, minimum delay, delay between commands, default travel time); *Log and updates* |
| **Backup** | Export / import of the whole configuration (JSON file) |

Temperature setpoints and the sunshine threshold can follow an **entity** (`input_number`, sensor…):
its value is then used, and the typed number is the fallback if the entity is unavailable.

### Available conditions

The *Add condition* menu groups them by theme (✨ = new in V2):

| Group | Conditions |
|-------|------------|
| **Sun** | Sun on the facade; sun elevation above / below |
| **Temperature** | Outdoor temperature above / below; room temperature (cold, between the setpoints, warm); ✨ outdoor air compared to the room (cooler / warmer, minimum difference) |
| **Occupancy** | ✨ Room occupied (based on the cover's occupancy sensor) |
| **Schedules** | Time between; before / after sunrise; before / after sunset; ✨ before / after dawn; ✨ before / after dusk (with an offset in minutes); day of the week; workday |
| **Weather** | The weather is (all Home Assistant weather states) |
| **Entities** | ✨ State of an entity; ✨ numeric value of an entity; ✨ Home Assistant condition (YAML) |

Each condition can be negated with **NOT**; a negated condition is never met while the value it reads
is unavailable. Conditions are split into **groups**: each group has its own operator (AND / OR) and the groups
are joined by another operator, for example (A OR B) AND (C OR D).

### Safety rule

In the editor, the **Safety rule** checkbox makes the rule act even when the cover is paused after a manual move,
in manual mode, wind protected or when automation (of the cover or global) is off. Taking control
and releasing it are written to the log. A safety rule never overrides the lock of an open window and,
between several rules, priority always decides: place it at the top of the list. Keep it for emergencies,
for example the fire alarm.

### Example: heat protection based on the outdoor temperature

To shade a facade when it is hot outside, combine two conditions in a rule (**AND** operator).
No extra setting is needed: the "Outdoor temperature above" condition reads by default the outdoor temperature
sensor defined in the **Settings**.

1. Choose an **outdoor temperature sensor** in the Settings.
2. Create a rule, for example *"Heat protection South"*:
   - "Sun on the facade" condition → your south facade
   - "Outdoor temperature above" condition → `28` (°C)
   - target position → for example `30` (partly closed)
3. Optional: give it a higher priority than your usual daytime rule so that it wins
   when the sun is on the facade and it is hot.

The rule closes the cover only when the sun really hits the facade **and** the outdoor temperature
exceeds the threshold, then releases it as soon as one of the two conditions is no longer met.

### Conditions on any entity (Home Assistant conditions)

The **Entities** group of the *Add condition* menu adds a condition evaluated by Home Assistant itself,
in the same format as the `condition:` section of an automation:

- **State of an entity** / **Numeric value of an entity** open a form: choose the entity,
  optionally an attribute, then the states (offered as buttons, for example the zones of a person),
  *is / is not*, a minimum duration, or above / below / between.
- **Home Assistant condition (YAML)** accepts any automation condition —
  templates, zones, devices, nested `and` / `or` / `not`:

```yaml
condition: or
conditions:
  - condition: state
    entity_id: media_player.living_room
    state: [playing, paused]
  - condition: template
    value_template: "{{ states('sensor.illuminance') | float(0) > 20000 }}"
```

Each condition has a **Form / YAML** button, is checked by Home Assistant while you type and shows the
entities it watches (rules react immediately to their changes). An invalid or
incomplete condition is kept but is never met, and it is flagged in red.

### Created entities

For each managed cover, a "CoverAutomatic *cover name*" device groups:

| Entity | Description |
|--------|-------------|
| `switch` Automation | Enables / disables the automation of the cover |
| `sensor` Status | Current status (auto / paused / manual / locked / venting / wind protection). Attributes: `rule_name`, `rule_id` and `target_position` (rule controlling the cover; empty when paused, manual, locked or wind protected, unless a safety rule controls it), plus position, pause end, safety rule, comfort mode… |
| `sensor` Active rule | Name of the rule controlling the cover |
| `sensor` Target position | Position requested by the active rule (%) |
| `sensor` Position (rule scale) | Current position, inverted for inverted covers (%) |
| `sensor` Comfort mode | Cold / comfort / warm depending on the room temperature |
| `sensor` Pause end | End time of the current pause |

For each facade, a "CoverAutomatic Facade *name*" device groups:

| Entity | Description |
|--------|-------------|
| `sensor` Sun on the facade | Yes / No |
| `sensor` Sun arrival time | Time the sun reaches the facade today (real sun path at your location) |
| `sensor` Sun departure time | Time the sun leaves the facade today |

Global entities ("CoverAutomatic" device):

| Entity | Description |
|--------|-------------|
| `switch` CoverAutomatic | Master switch of the automation. When off, the open-window lock, venting and safety rules stay active |
| `select` Scenario | Active scenario (`scenario_names` attribute: display names of the scenarios) |
| `binary_sensor` Wind protection | On when the wind exceeds the threshold (attributes: wind speed, threshold, hysteresis) |
| `sensor` Covers paused / manual / locked | Number of covers in this status (names as attributes) |

Devices and entities are created and removed automatically when covers or facades are added or
removed in the panel or by an import, without a restart. A device left orphaned can be deleted from
its device page.

Note: the integration controls your original `cover` entities directly; it does not create intermediate `cover` entities.

### Dashboard card

The `custom:cover-automatic-card` card is loaded automatically and offered in the card picker, with a visual editor.
Options: `title`, `covers` (all by default), `show_rule`, `show_auto`, `show_temp` (room temperature,
with the colours chosen in the Settings), `show_header`.

```yaml
type: custom:cover-automatic-card
title: Covers
show_header: true
```

### Available services

| Service | Description |
|---------|-------------|
| `cover_automatic.pause` | Pauses the automation of a cover |
| `cover_automatic.resume` | Resumes the automation of a cover (same as the cross in the panel) |
| `cover_automatic.pause_all` | Pauses all covers |
| `cover_automatic.resume_all` | Resumes all covers |
| `cover_automatic.set_scenario` | Selects the active scenario |
| `cover_automatic.export_config` | Exports the configuration to a YAML file |
| `cover_automatic.import_config` | Imports the configuration from a YAML file |

Backup and restore are also available in **Settings > Backup** of the panel (JSON file).

---

## Troubleshooting

Most "bugs" are actually one of the safety mechanisms below doing its job.
Check this list before opening an issue.

### Covers do not move right after a Home Assistant restart

This is intended. After startup, CoverAutomatic waits **120 seconds** before applying positions.
This delay avoids wrong moves while sensors do not yet report all their data
(for example a Zigbee gateway not reconnected yet). Automation starts at the first cycle after this delay.

### A cover suddenly switches to PAUSED

CoverAutomatic detected a **manual command**: the cover was moved by something other than CoverAutomatic
(wall switch, remote control, another automation, the Home Assistant interface). The automation of this cover
is paused for the configured duration (global or per cover) to respect your choice, then resumes by itself.
It also resumes as soon as the cover is back at the position requested by its rule ("Resume when the position
matches the rule" option). To resume earlier: the cross in the panel, the cover's "Automation" switch
or the `cover_automatic.resume` service.

For slow covers that report neither intermediate positions nor *opening* / *closing*, the integration
waits for the **cover travel time** (learned automatically, or entered in the cover sheet, Automation section)
before treating a position as manual. If a slow cover is still wrongly paused right after an automatic
move, enter a cover travel time slightly longer than the real one.

### A rule is met but the cover does not move

Check in this order:

1. **Status priority** — WIND PROTECTION, LOCKED (open window), VENTING (tilted window) and PAUSED
   come before the rules (except a safety rule, which also acts when paused, manual and wind protected).
   The cover list of the panel shows the status and the active rule of each cover.
2. **Master switch / cover automation** — both must be on.
3. **Active scenario** — only the rules of the active scenario (and not disabled in that scenario) are considered.
4. **Minimum delay between two moves** — position changes are rate-limited; the move happens
   at a later cycle.

### A sun rule does not shade

For a cover that has an indoor temperature sensor (its own or the global one), the "Sun on the facade" condition
takes the room temperature into account, according to the settings in **Settings > Sun exposure** (which can be changed per
cover in the "Sun exposure" section of its sheet):

- **cold** room (at most the cold setpoint): with the "let the sun heat the room" option (on by default), the condition
  answers "no sun" to let the sun heat the room;
- room **between the setpoints**: depending on the choice "as soon as the sun is on the facade", "never (wait until the room gets
  too warm)" or "only in strong sunshine" (sunshine sensor above its threshold);
- **warm** room (at least the warm setpoint): the condition answers "sun" as soon as the sun is on the facade.

The "How does it work?" block of these settings shows the result for your own values.

### A cover stays LOCKED or VENTING

These statuses come from the configured window sensors: locked = open window (automation blocked),
venting = tilted window (the cover keeps a minimum position). If the sensor itself is `unavailable` or `unknown`,
the last status is kept for safety — check the sensor rather than the integration. A sensor removed
from Home Assistant is ignored after the startup delay (reported in the log).

### The panel looks broken or outdated after an update

The panel file is reloaded with each version, but some browsers keep it in cache.
Force a reload (Ctrl/Cmd+Shift+R) or clear the cache of the Home Assistant companion app.

### Enable debug logging

**Settings > Devices & services > CoverAutomatic** > three-dot menu > **Enable debug logging**.
Reproduce the problem then disable it the same way: Home Assistant offers the log for download.
Attach it to your report with a backup of the configuration (Settings > Backup, or the
`cover_automatic.export_config` service).

Still stuck? [Report a bug](https://github.com/slemeur91/CoverAutomatic/issues/new?template=bug_report.yml) —
the form asks for everything needed to help you quickly.

---

## Privacy

- **Update check:** when the panel is open, it sends an anonymous `GET` request to the public GitHub API
  (`api.github.com`, hosted in the United States) to read the number of the latest published version and show
  an update hint. No account, token or personal data is sent. This check can be
  disabled in **Settings > Automation > Check for updates**: no request is sent then.
  The automation itself never contacts GitHub.
- **Backups:** exported files contain the identifiers of your sensors and covers. Identifiers named
  after rooms or people (for example `cover.bedroom_anna`) may contain a personal reference.
  Keep these files like any other configuration backup.

---

## Version

2.0.7

## Release history

The full history is kept in [CHANGELOG.md](https://github.com/slemeur91/CoverAutomatic/blob/main/CHANGELOG.md), in the [Keep a Changelog](https://keepachangelog.com/) format.

Latest version: v2.0.7 (2026-10-09), based on the original version
[v1.62.1](https://github.com/crandler/CoverAutomatic/releases/tag/v1.62.1) by @crandler.

## License

MIT License — see the [LICENSE](https://github.com/slemeur91/CoverAutomatic/blob/main/LICENSE) file.

```
MIT License

Copyright (c) 2026 Sven Eulberg
Copyright (c) 2026 slemeur91 (fork CoverAutomatic V2)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Authors

- Original project: [@crandler](https://github.com/crandler) — [github.com/crandler/CoverAutomatic](https://github.com/crandler/CoverAutomatic)
- V2 fork: [@slemeur91](https://github.com/slemeur91) — [github.com/slemeur91/CoverAutomatic](https://github.com/slemeur91/CoverAutomatic)

**This is not an official product.**

---

## Development

This project was developed with the help of an AI (Claude, by Anthropic) under human supervision.
Every change is reviewed and approved by a person before it is published.

**AI-assisted | Human supervision | Code reviewed**

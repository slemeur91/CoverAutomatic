/**
 * CoverAutomatic Config Panel
 * Home Assistant custom panel for intelligent cover/shutter automation.
 * Vanilla web component with Shadow DOM -- no external dependencies.
 */

import { PanelCore } from "./core.js";
import { EventsMixin } from "./events.js";
import { CoversMixin } from "./covers.js";
import { SlideCoverMixin } from "./slide-cover.js";
import { FacadesMixin } from "./facades.js";
import { RulesMixin } from "./rules.js";
import { ConditionsMixin } from "./conditions.js";
import { HaConditionsMixin } from "./ha-conditions.js";
import { ScenariosMixin } from "./scenarios.js";
import { SettingsMixin } from "./settings.js";
import { SettingsComfortMixin } from "./settings-comfort.js";
import { LogMixin } from "./log.js";

// The element is the core plus one mixin per area; every mixin only adds
// methods (names are unique across the modules).
class CoverAutomaticPanel extends LogMixin(SettingsComfortMixin(SettingsMixin(ScenariosMixin(HaConditionsMixin(ConditionsMixin(RulesMixin(FacadesMixin(SlideCoverMixin(CoversMixin(EventsMixin(PanelCore))))))))))) {}

customElements.define("cover-automatic-panel", CoverAutomaticPanel);

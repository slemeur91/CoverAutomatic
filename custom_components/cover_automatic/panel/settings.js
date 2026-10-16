// CoverAutomatic panel -- Settings tab: sections, draft, save, backup.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).

export const SettingsMixin = (Base) => class extends Base {
  /* ============================================================
   * TAB: Settings
   * ============================================================ */
  // Phones: the settings sections are a horizontal pill strip. A re-render
  // brings it back to the start, which hides a pill chosen near the end:
  // scroll the strip so the active pill sits in the middle.
  _centerActiveSettingsPill() {
    const nav = this.shadowRoot && this.shadowRoot.querySelector(".settings-nav");
    const active = nav && nav.querySelector(".settings-nav-btn.active");
    if (!active || nav.scrollWidth <= nav.clientWidth) return;
    const navRect = nav.getBoundingClientRect();
    const btnRect = active.getBoundingClientRect();
    nav.scrollLeft += btnRect.left - navRect.left - (navRect.width - btnRect.width) / 2;
  }

  _renderSettings() {
    const s = this._config.settings || {};
    const hint = (text) => `<div class="settings-hint">${text}</div>`;
    const hintIntro = (text) => `<div class="settings-hint-intro">${text}</div>`;
    let active = this._activeSettingsSection || "house";
    if (active === "solar") active = this._activeSettingsSection = "comfort";

    const sections = [
      { id: "house", labelKey: "settings_section_house", icon: this._lucideIcon("house", 16) },
      { id: "sensors", labelKey: "settings_section_sensors", icon: this._lucideIcon("gauge", 16) },
      { id: "comfort", labelKey: "settings_section_comfort", icon: this._lucideIcon("sun", 16) },
      { id: "wind", labelKey: "settings_section_wind", icon: this._lucideIcon("wind", 16) },
      { id: "automation", labelKey: "settings_section_automation", icon: this._lucideIcon("cog", 16) },
      { id: "backup", labelKey: "settings_section_backup", icon: this._lucideIcon("archive", 16) }
    ];

    let html = '<div class="settings-shell">';

    // Sidebar navigation
    html += '<aside class="settings-nav" role="tablist" aria-label="' + this._esc(this._t("settings_nav_label")) + '">';
    for (const sec of sections) {
      const isActive = sec.id === active;
      const cls = "settings-nav-btn" + (isActive ? " active" : "");
      html += '<button class="' + cls + '" role="tab" aria-selected="' + (isActive ? "true" : "false") + '" data-action="settings-section" data-section="' + sec.id + '">';
      html += '<span class="settings-nav-icon">' + sec.icon + '</span>';
      html += '<span class="settings-nav-label">' + this._esc(this._t(sec.labelKey)) + '</span>';
      html += '</button>';
    }
    html += '</aside>';

    // Content column
    html += '<div class="settings-content"><div class="settings-stack">';

    // House section
    if (active === "house") {
      const rot = this._num(s.house_rotation, 0);
      html += `<div class="card">
      <div class="card-header">${this._lucideIcon("house")} ${this._t("settings_section_house")}</div>
      <div class="card-body">
        <div class="settings-house-layout">
          <div class="form-group settings-house-input">
            <label>${this._t("settings_house_rotation")}</label>
            <input type="number" step="0.5" min="-180" max="180" value="${rot}" data-settings-field="house_rotation" id="house-rotation-input">
            <div class="rotation-quick">
              <button type="button" class="rotation-quick-btn" data-action="rotate-by" data-delta="-45">−45°</button>
              <button type="button" class="rotation-quick-btn" data-action="rotate-by" data-delta="-5">−5°</button>
              <button type="button" class="rotation-quick-btn rotation-quick-reset" data-action="rotate-by" data-set="0">${this._t("settings_house_rotation_reset")}</button>
              <button type="button" class="rotation-quick-btn" data-action="rotate-by" data-delta="5">+5°</button>
              <button type="button" class="rotation-quick-btn" data-action="rotate-by" data-delta="45">+45°</button>
            </div>
            ${hint(this._t("settings_house_rotation_hint"))}
            <label class="checkbox-row" style="margin-top:28px">
              <input type="checkbox" data-settings-field="rotate_facades_with_house" ${s.rotate_facades_with_house !== false ? "checked" : ""}>
              <span>${this._esc(this._t("settings_rotate_facades"))}</span>
            </label>
            ${hint(this._esc(this._t("settings_rotate_facades_hint")))}
          </div>
          <div class="settings-house-compass">${this._renderCompassSVG(rot)}</div>
        </div>
      </div>
    </div>`;
    }

    // Sensors section (outdoor/indoor/weather/workday)
    if (active === "sensors") {
      html += `<div class="card">
      <div class="card-header">${this._lucideIcon("gauge")} ${this._t("settings_section_sensors")}</div>
      <div class="card-body">
        ${this._optBox({
          title: this._t("settings_comfort_range_title"),
          head: `<div class="form-group">
            <label>${this._L("settings_indoor_temp")}</label>
            ${this._renderEntitySelect("indoor_temp_sensor", s.indoor_temp_sensor, "sensor", "temperature")}
            ${this._renderSensorValue(s.indoor_temp_sensor, "\u00B0")}
            ${hint(this._t("settings_indoor_temp_hint"))}
          </div>`,
          body: `${hintIntro(this._t("settings_comfort_hint"))}
          ${hintIntro(this._esc(this._t("profile_intro")))}
          ${this._renderProfileFields()}
          <div class="profile-grid">${["a", "b"].map(p => {
            const sfx = p === "b" ? "_b" : "";
            const def = p === "b" ? [22, 24] : [21, 23];
            return `<div class="profile-col" data-profile="${p}">
              <div class="profile-col-title">${this._esc(this._t("profile_title").replace("{p}", p.toUpperCase()))}</div>
              <label>${this._esc(this._t("profile_scenarios"))}</label>
              ${this._renderProfileChips(p, true)}
              <div class="profile-off-note">${this._esc(this._t("profile_off_note"))}</div>
              <div class="profile-fields">
                <div class="form-row">
                  <div class="form-group">
                    <label>${this._L("settings_comfort_min")}</label>
                    <input type="number" step="0.5" value="${this._num(s["comfort_temp_min" + sfx], def[0])}" data-settings-field="comfort_temp_min${sfx}">
                  </div>
                  <div class="form-group">
                    <label>${this._L("settings_comfort_max")}</label>
                    <input type="number" step="0.5" value="${this._num(s["comfort_temp_max" + sfx], def[1])}" data-settings-field="comfort_temp_max${sfx}">
                  </div>
                </div>
                <div class="form-group">
                  <label>${this._L("settings_comfort_hysteresis")}</label>
                  <input type="number" step="0.1" min="0.1" max="5" value="${this._num(s["comfort_hysteresis" + sfx], 1)}" data-settings-field="comfort_hysteresis${sfx}">
                  ${hint(this._t("settings_comfort_hysteresis_hint"))}
                </div>
                ${this._renderHystExplain(p === "b" ? "comfort_b" : "comfort")}
              </div>
            </div>`;
          }).join("")}</div>
          ${this._renderProfileFree()}
          <div class="form-group" style="margin-top:16px">
            <label>${this._t("settings_temp_color")}</label>
            <input type="hidden" data-settings-field="temp_color_mode" value="${s.temp_color_thermometer === true ? "thermometer" : "action"}" data-initial="${s.temp_color_thermometer === true ? "thermometer" : "action"}">
            <div class="radio-group">${["action", "thermometer"].map(v => `<label class="radio-row">
              <input type="radio" name="temp_color_mode" value="${v}" data-settings-radio="temp_color_mode" ${(s.temp_color_thermometer === true ? "thermometer" : "action") === v ? "checked" : ""}>
              <span><b>${this._esc(this._t("settings_temp_color_" + v))}</b><br><span class="radio-hint">${this._esc(this._t("settings_temp_color_" + v + "_hint"))}</span></span>
            </label>`).join("")}</div>
          </div>`,
        })}
        ${this._optBox({
          title: this._t("settings_outdoor_box_title"),
          dep: '[data-settings-field="outdoor_temp_sensor"]', mode: "value",
          head: `<div class="form-group">
            <label>${this._t("settings_outdoor_temp")}</label>
            ${this._renderEntitySelect("outdoor_temp_sensor", s.outdoor_temp_sensor, "sensor", "temperature")}
            ${this._renderSensorValue(s.outdoor_temp_sensor, "\u00B0")}
            ${hint(this._t("settings_outdoor_temp_hint"))}
          </div>`,
          offNote: this._t("settings_outdoor_off_note"),
          body: `<div class="form-group">
            <label>${this._L("settings_threshold_hysteresis")}</label>
            <input type="number" step="0.1" min="0" max="5" value="${this._num(s.threshold_hysteresis, 0.5)}" data-settings-field="threshold_hysteresis">
            ${hint(this._t("settings_threshold_hysteresis_hint"))}
          </div>
          ${this._renderHystExplain("rules")}`,
        })}
        ${this._optBox({
          title: this._t("settings_other_sensors_title"),
          body: `<div class="form-row">
            <div class="form-group">
              <label>${this._t("settings_weather")}</label>
              ${this._renderEntitySelect("weather_entity", s.weather_entity, "weather", null)}
              ${this._renderSensorValue(s.weather_entity)}
              ${hint(this._t("settings_weather_hint"))}
            </div>
            <div class="form-group">
              <label>${this._t("settings_workday_sensor")}</label>
              ${this._renderEntitySelect("workday_sensor", s.workday_sensor, "binary_sensor", null)}
              ${this._renderSensorValue(s.workday_sensor)}
              ${hint(this._t("settings_workday_hint"))}
            </div>
          </div>`,
        })}
      </div>
    </div>`;
    }

    // Wind section
    if (active === "wind") {
      const windSt = s.wind_sensor && this._hass?.states ? this._hass.states[s.wind_sensor] : null;
      const windUnit = (windSt && windSt.attributes.unit_of_measurement) || "";
      html += `<div class="card">
      <div class="card-header">${this._lucideIcon("wind")} ${this._t("settings_section_wind")}</div>
      <div class="card-body">
        ${hintIntro(this._t("settings_wind_hint"))}
        ${this._optBox({
          dep: '[data-settings-field="wind_sensor"]', mode: "value",
          head: `<div class="form-group">
          <label>${this._t("settings_wind_sensor")}</label>
          ${this._renderEntitySelect("wind_sensor", s.wind_sensor, "sensor", "wind_speed")}
          ${this._renderSensorValue(s.wind_sensor)}
        </div>`,
          offNote: this._t("settings_wind_off_note"),
          body: `<div class="form-row">
          <div class="form-group">
            <label>${this._t("settings_wind_threshold")}${windUnit ? " (" + this._esc(windUnit) + ")" : ""}</label>
            <input type="number" step="1" min="0" value="${this._num(s.wind_speed_threshold, 0)}" data-settings-field="wind_speed_threshold">
          </div>
          <div class="form-group">
            <label>${this._L("settings_wind_hysteresis")} (${this._esc(windUnit || this._t("unit_sensor"))})</label>
            <input type="number" step="1" min="0" value="${this._num(s.wind_speed_hysteresis, 0)}" data-settings-field="wind_speed_hysteresis">
            ${hint(this._t("settings_wind_hysteresis_hint"))}
          </div>
        </div>
        <div class="form-group">
          <label>${this._t("settings_wind_position")}</label>
          <input type="number" step="1" min="0" max="100" value="${this._num(s.wind_position, 100)}" data-settings-field="wind_position">
          ${hint(this._t("settings_wind_position_hint"))}
        </div>
        ${this._renderHystExplain("wind")}`,
        })}
      </div>
    </div>`;
    }

    // Sun exposure tab: the behaviour of "Sun on facade" per comfort profile
    if (active === "comfort") {
      const used = this._coversUsingRadiation();
      const solarSt = s.solar_sensor && this._hass?.states ? this._hass.states[s.solar_sensor] : null;
      const solarUnit = (solarSt && solarSt.attributes.unit_of_measurement) || "";
      const solarInner = this._optBox({
          cls: "opt-box-flat",
          dep: '[data-settings-field="solar_sensor"]', mode: "value",
          head: `${hintIntro(this._esc(this._t("settings_solar_hint")))}
          <div class="settings-hint" style="margin-bottom:12px">${this._esc(used
            ? this._t("solar_used_by").replace("{n}", used)
            : this._t("solar_unused"))}</div>
          <div class="form-group">
            <label>${this._t("settings_solar_sensor")}</label>
            ${this._renderEntitySelect("solar_sensor", s.solar_sensor, "sensor")}
            ${this._renderSensorValue(s.solar_sensor)}
          </div>`,
          offNote: this._t("settings_solar_off_note"),
          body: `<div class="form-row">
            <div class="form-group">
              <label>${this._L("settings_solar_threshold")}${solarUnit ? " (" + this._esc(solarUnit) + ")" : ""}</label>
              <input type="number" step="100" min="0" value="${this._num(s.solar_threshold, 0)}" data-settings-field="solar_threshold">
              ${hint(this._t("settings_solar_threshold_hint"))}
              ${this._renderThresholdEntity('data-settings-field="solar_threshold_entity"', s.solar_threshold_entity)}
            </div>
            <div class="form-group">
              <label>${this._L("settings_solar_hysteresis")} (${this._esc(solarUnit || this._t("unit_sensor"))})</label>
              <input type="number" step="100" min="0" value="${this._num(s.solar_hysteresis, 0)}" data-settings-field="solar_hysteresis">
              ${hint(this._t("settings_solar_hysteresis_hint"))}
            </div>
          </div>
          ${this._renderHystExplain("solar")}`,
        });
      const solarBox = this._optBox({
        title: this._t("settings_section_solar"),
        dep: '[data-settings-field^="sun_comfort_mode"]', mode: "anyequals", value: "preemptive", force: used > 0,
        offNote: this._t("settings_solar_nested_off"),
        body: solarInner,
      });
      const column = (p) => {
        const sfx = p === "b" ? "_b" : "";
        const v = this._profileValues(p, !this._settingsDraft);
        const cmin = v.min, cmax = v.max;
        const mode = this._sunComfortMode(s["sun_neutral_ignore" + sfx] !== false, s["preemptive_shading" + sfx] !== false);
        const radio = (value) => `<label class="radio-row">
          <input type="radio" name="sun_comfort_mode${sfx}" value="${value}" data-settings-radio="sun_comfort_mode${sfx}" ${mode === value ? "checked" : ""}>
          <span><b>${this._esc(this._t("sun_comfort_" + value))}</b><br><span class="radio-hint">${this._esc(this._t("sun_comfort_" + value + "_hint"))}</span></span>
        </label>`;
        return `<div class="profile-col" data-profile="${p}">
          <div class="profile-col-title">${this._esc(this._t("profile_title").replace("{p}", p.toUpperCase()))}</div>
          ${this._renderProfileChips(p, false)}
          <div class="settings-hint">${this._esc(this._t("profile_sun_scenarios_note"))}</div>
          <div class="profile-off-note">${this._esc(this._t("profile_off_note"))}</div>
          <div class="profile-fields">
            <div class="settings-hint" style="margin:8px 0 10px"><b>${this._esc(this._t("profile_sun_reminder")
              .replace("{name}", s.indoor_temp_sensor ? this._haEntityName(s.indoor_temp_sensor) : this._t("settings_indoor_none"))
              .replace("{min}", cmin).replace("{max}", cmax))}</b></div>
            <div class="form-group">
              <label class="checkbox-row">
                <input type="checkbox" data-settings-field="sun_heating_ignore${sfx}" ${s["sun_heating_ignore" + sfx] !== false ? "checked" : ""}>
                <span>${this._L("sun_heating_label")} <span class="radio-hint">(${this._esc(this._t("sun_below").replace("{t}", cmin))})</span></span>
              </label>
              ${hint(this._esc(this._t("sun_heating_hint")))}
            </div>
            <div class="form-group">
              <label>${this._L("sun_comfort_label")} <span class="radio-hint">(${this._esc(this._t("sun_between").replace("{min}", cmin).replace("{max}", cmax))})</span></label>
              <input type="hidden" data-settings-field="sun_comfort_mode${sfx}" value="${mode}" data-initial="${mode}">
              <div class="radio-group">${radio("position")}${radio("ignore")}${radio("preemptive")}</div>
            </div>
            <div class="settings-hint">${this._esc(this._t("sun_hot_note").replace("{t}", cmax))}</div>
            ${this._renderSunExplain(cmin, cmax, p)}
          </div>
        </div>`;
      };
      html += `<div class="card">
      <div class="card-header">${this._lucideIcon("sun", 18)} ${this._t("settings_section_comfort")}</div>
      <div class="card-body">
        <div class="opt-box">
        <div class="opt-box-title">${this._L("settings_sun_facade_title")}</div>
        ${this._renderRichHint("settings_sun_facade_hint")}
        ${this._renderProfileFields()}
        <div class="profile-grid">${column("a")}${column("b")}</div>
        ${this._renderProfileFree()}
        </div>
        ${solarBox}
      </div>
    </div>`;
    }

    // Automation section
    if (active === "automation") {
      html += `<div class="card">
      <div class="card-header">${this._lucideIcon("cog")} ${this._t("settings_section_automation")}</div>
      <div class="card-body">
        <div class="opt-box">
        <div class="opt-box-title">${this._esc(this._t("settings_auto_box_pause"))}</div>
        <div class="form-group">
          <label>${this._t("settings_pause_duration")}</label>
          <input type="number" min="1" max="480" value="${this._num(s.pause_duration, 10)}" data-settings-field="pause_duration">
          ${hint(this._t("settings_pause_duration_hint"))}
        </div>
        <div class="form-group">
          <label class="checkbox-row">
            <input type="checkbox" data-settings-field="pause_resume_on_match" ${s.pause_resume_on_match !== false ? "checked" : ""}>
            <span>${this._t("pause_resume_on_match")}</span>
          </label>
          ${hint(this._t("pause_resume_on_match_hint"))}
        </div>
        </div>
        <div class="opt-box">
        <div class="opt-box-title">${this._esc(this._t("settings_auto_box_window"))}</div>
        <div class="form-row">
          <div class="form-group">
            <label>${this._t("settings_lock_position")}</label>
            <input type="number" min="0" max="100" value="${this._num(s.lock_position, 100)}" data-settings-field="lock_position">
            ${hint(this._t("settings_lock_position_hint"))}
          </div>
          <div class="form-group">
            <label>${this._t("settings_vent_position")}</label>
            <input type="number" min="0" max="100" value="${this._num(s.vent_position, 30)}" data-settings-field="vent_position">
            ${hint(this._t("settings_vent_position_hint"))}
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>${this._t("settings_lock_tilt_position")}</label>
            <input type="number" min="0" max="100" value="${this._num(s.lock_tilt_position, "")}" data-settings-field="lock_tilt_position">
            ${hint(this._t("settings_lock_tilt_position_hint"))}
          </div>
          <div class="form-group">
            <label>${this._t("settings_vent_tilt_position")}</label>
            <input type="number" min="0" max="100" value="${this._num(s.vent_tilt_position, "")}" data-settings-field="vent_tilt_position">
            ${hint(this._t("settings_vent_tilt_position_hint"))}
          </div>
        </div>
        </div>
        <div class="opt-box">
        <div class="opt-box-title">${this._esc(this._t("settings_auto_box_moves"))}</div>
        <div class="form-row">
          <div class="form-group">
            <label>${this._t("settings_min_position_change")}</label>
            <input type="number" min="1" max="50" value="${this._num(s.min_position_change, 5)}" data-settings-field="min_position_change">
            ${hint(this._t("settings_min_position_change_hint"))}
          </div>
          <div class="form-group">
            <label>${this._t("settings_min_time")}</label>
            <input type="number" min="60" max="3600" value="${this._num(s.min_time_between_changes, 300)}" data-settings-field="min_time_between_changes">
            ${hint(this._t("settings_min_time_hint"))}
          </div>
        </div>
        <div class="form-group">
          <label>${this._t("settings_command_stagger")}</label>
          <input type="number" step="0.1" min="0" max="2" value="${this._num(s.command_stagger, 0)}" data-settings-field="command_stagger">
          ${hint(this._t("settings_command_stagger_hint"))}
        </div>
        <div class="form-group">
          <label>${this._t("settings_default_travel_time")}</label>
          <input type="number" min="1" max="300" step="1" value="${this._num(s.default_travel_time, "")}" placeholder="${this._esc(this._t("settings_default_travel_time_placeholder"))}" data-settings-field="default_travel_time">
          ${hint(this._t("settings_default_travel_time_hint"))}
        </div>
        </div>
        <div class="opt-box">
        <div class="opt-box-title">${this._esc(this._t("settings_auto_box_misc"))}</div>
        <div class="form-group">
          <label class="checkbox-row">
            <input type="checkbox" data-settings-field="logbook_enabled" ${s.logbook_enabled !== false ? "checked" : ""}>
            <span>${this._t("settings_logbook_enabled")}</span>
          </label>
          ${hint(this._t("settings_logbook_enabled_hint"))}
        </div>
        <div class="form-group">
          <label class="checkbox-row">
            <input type="checkbox" data-settings-field="update_check_enabled" ${s.update_check_enabled !== false ? "checked" : ""}>
            <span>${this._t("settings_update_check_enabled")}</span>
          </label>
          ${hint(this._t("settings_update_check_enabled_hint"))}
        </div>
        </div>
      </div>
    </div>`;
    }

    // Save bar - for all sections except backup
    if (active !== "backup") {
      html += `<div class="settings-save-bar">
      <button class="btn btn-primary" data-action="settings-save">${this._t("save")}</button>
    </div>`;
    }

    // Backup section
    if (active === "backup") {
      html += `<div class="card">
      <div class="card-header">${this._lucideIcon("archive")} ${this._t("settings_section_backup")}</div>
      <div class="card-body">
        ${hintIntro(this._t("settings_backup_hint"))}
        ${this._settingsDirty() ? `<div class="settings-unsaved-warning">${this._lucideIcon("info", 16)} ${this._esc(this._t("settings_unsaved_warning"))}
          <button class="btn btn-primary" data-action="settings-save">${this._t("save")}</button></div>` : ""}
        <div class="settings-backup-actions">
          <button class="btn" data-action="backup-export">${this._t("settings_export")}</button>
          <button class="btn" data-action="backup-import">${this._t("settings_import")}</button>
          <input type="file" accept=".json" data-action="backup-file" hidden>
        </div>
      </div>
    </div>`;
    }

    html += '</div></div></div>'; // close settings-stack, settings-content, settings-shell
    return html;
  }

  async _onMasterToggle(checked, el = null) {
    try {
      const result = await this._ws("cover_automatic/settings/update", { enabled: checked });
      this._updateConfigFromResult(result);
    } catch (e) {
      console.error(e);
      if (el) el.checked = !checked;
      this._showError(e);
    }
  }

  // Unsaved settings inputs survive section switches and re-renders.
  _captureSettingsDraft() {
    if (this._activeTab !== "settings" || !this.shadowRoot || this._skipSettingsCapture || this._settingsDomStale) return;
    const inputs = this.shadowRoot.querySelectorAll("[data-settings-field]");
    if (!inputs.length) return;
    const draft = this._settingsDraft || {};
    inputs.forEach(input => {
      const kind = input.type === "checkbox" ? "checkbox" : (input.type === "number" ? "number" : "text");
      const field = input.dataset.settingsField;
      const value = kind === "checkbox" ? input.checked : input.value;
      // The stored value the input was rendered with (first capture only)
      const initial = draft[field] ? draft[field].initial : this._settingsInputDefault(input);
      draft[field] = { kind, value, initial };
    });
    this._settingsDraft = draft;
  }

  // Value an input was rendered with (the stored setting), not the edited one.
  _settingsInputDefault(input) {
    // Hidden inputs change their attribute with their value: explicit initial
    if (input.dataset.initial !== undefined) return input.dataset.initial;
    if (input.type === "checkbox") return input.defaultChecked;
    if (input.tagName === "SELECT") {
      const opt = Array.from(input.options).find(o => o.defaultSelected) || input.options[0];
      return opt ? opt.value : "";
    }
    return input.defaultValue;
  }

  // True when a settings input differs from its stored value.
  _settingsDirty() {
    this._captureSettingsDraft();
    return Object.values(this._settingsDraft || {}).some(d => !this._draftSame(d));
  }

  // Draft entry unchanged? Numbers compare by value ("21.0" == "21").
  _draftSame(d) {
    if (d.kind === "number") {
      const a = String(d.value ?? "").trim(), b = String(d.initial ?? "").trim();
      if (a === "" || b === "") return a === b;
      return Number(a) === Number(b);
    }
    return d.value === d.initial;
  }

  // Run `then` after the user agreed to drop unsaved settings (if any).
  _confirmLeaveSettings(then) {
    if (this._activeTab === "settings" && this._settingsDirty()) {
      this._showConfirm(this._t("settings_unsaved_confirm"), then, this._t("discard"));
    } else then();
  }

  // Radio groups follow their hidden draft field (restored drafts)
  _syncSettingsRadios() {
    if (!this.shadowRoot) return;
    this.shadowRoot.querySelectorAll("[data-settings-radio]").forEach(r => {
      const hidden = this.shadowRoot.querySelector(`[data-settings-field="${r.dataset.settingsRadio}"]`);
      if (hidden) r.checked = r.value === hidden.value;
    });
  }

  _applySettingsDraft() {
    const draft = this._settingsDraft;
    if (!draft || this._activeTab !== "settings" || !this.shadowRoot) return;
    this.shadowRoot.querySelectorAll("[data-settings-field]").forEach(input => {
      const d = draft[input.dataset.settingsField];
      if (!d) return;
      // Stored value after a server-side change: taken from the fresh render
      if (d.initial === undefined) d.initial = this._settingsInputDefault(input);
      if (d.kind === "checkbox") input.checked = !!d.value;
      else if (input.value !== d.value) {
        input.value = d.value;
        // Compass preview follows the restored rotation
        if (input.id === "house-rotation-input") input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
  }

  async _onSettingsSave() {
    this._captureSettingsDraft();
    return this._saveSettingsDraft();
  }

  // Returns true once saved (false when invalid or on error).
  async _saveSettingsDraft() {
    // Only these numeric settings accept null (= unset); an empty field of
    // any other numeric setting is left out and keeps its stored value.
    const NULLABLE = new Set(["lock_tilt_position", "vent_tilt_position", "default_travel_time"]);
    const data = {};
    for (const [field, d] of Object.entries(this._settingsDraft || {})) {
      // Send only the fields really changed: an untouched field must not
      // overwrite a value changed meanwhile elsewhere (other window, import).
      if (this._draftSame(d)) continue;
      if (d.kind === "checkbox") {
        data[field] = !!d.value;
      } else if (d.kind === "number") {
        const raw = String(d.value ?? "").trim();
        const n = raw === "" ? NaN : parseFloat(raw);
        if (Number.isFinite(n)) data[field] = n;
        else if (raw === "" && NULLABLE.has(field)) data[field] = null;
      } else {
        data[field] = String(d.value ?? "").trim() || null;
      }
    }
    // Comfort-range behaviour: one choice stored as two flags (per profile)
    if (data.sun_comfort_mode !== undefined) {
      if (data.sun_comfort_mode) Object.assign(data, this._sunComfortFlags(data.sun_comfort_mode));
      delete data.sun_comfort_mode;
    }
    if (data.sun_comfort_mode_b !== undefined) {
      if (data.sun_comfort_mode_b) {
        const f = this._sunComfortFlags(data.sun_comfort_mode_b);
        data.sun_neutral_ignore_b = f.sun_neutral_ignore;
        data.preemptive_shading_b = f.preemptive_shading;
      }
      delete data.sun_comfort_mode_b;
    }
    // Scenarios of the comfort profiles: comma-separated in the form. Both
    // lists are sent together so a scenario never ends up in both.
    if ("profile_a_scenarios" in data || "profile_b_scenarios" in data) {
      for (const p of ["a", "b"]) data["profile_" + p + "_scenarios"] = this._profileScenarioIds(p);
    }
    // Temperature colours: radio choice stored as one flag
    if (data.temp_color_mode !== undefined) {
      if (data.temp_color_mode) data.temp_color_thermometer = data.temp_color_mode === "thermometer";
      delete data.temp_color_mode;
    }
    if (data.wind_position !== undefined && !(Number.isInteger(data.wind_position) && data.wind_position >= 0 && data.wind_position <= 100)) {
      alert(this._t("settings_wind_position") + this._colon() + this._t("input_invalid_range").replace("{min}", 0).replace("{max}", 100));
      return false;
    }
    // Whole-number settings: refuse decimals instead of letting the backend
    // silently truncate them (10.5 -> 10).
    const INTEGER = ["pause_duration", "lock_position", "vent_position", "lock_tilt_position",
      "vent_tilt_position", "min_position_change", "min_time_between_changes", "default_travel_time"];
    const badInt = INTEGER.find(f => data[f] != null && !Number.isInteger(data[f]));
    if (badInt) {
      const input = this.shadowRoot.querySelector(`[data-settings-field="${badInt}"]`);
      const label = input?.closest(".form-group")?.querySelector("label")?.textContent?.trim() || badInt;
      alert(label + this._colon() + this._t("input_not_integer"));
      return false;
    }
    // Validate the comfort range of each profile
    const cur = this._config.settings || {};
    for (const sfx of ["", "_b"]) {
      const cmin = data["comfort_temp_min" + sfx] ?? cur["comfort_temp_min" + sfx];
      const cmax = data["comfort_temp_max" + sfx] ?? cur["comfort_temp_max" + sfx];
      if (cmin != null && cmax != null && cmin >= cmax) {
        alert(this._t("profile_title").replace("{p}", sfx ? "B" : "A") + this._colon() + this._t("settings_validation_min_max"));
        return false;
      }
    }
    try {
      const result = await this._ws("cover_automatic/settings/update", data);
      this._settingsDraft = null;
      this._skipSettingsCapture = true;
      try { this._updateConfigFromResult(result); } finally { this._skipSettingsCapture = false; }
      return true;
    } catch (e) { console.error(e); this._showError(e); return false; }
  }

  // Unsaved settings would be missing from the export: offer to save first.
  _onBackupExportClick() {
    if (this._settingsDirty()) {
      this._showConfirm(this._t("settings_export_unsaved_confirm"), async () => {
        if (await this._saveSettingsDraft()) await this._onBackupExport();
      }, this._t("settings_save_and_export"));
    } else this._onBackupExport();
  }

  async _onBackupExport() {
    try {
      const result = await this._ws("cover_automatic/export", {});
      const json = JSON.stringify(result.data, null, 2);
      const blob = new Blob([json], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "cover_automatic_backup.json";
      a.style.display = "none";
      // Firefox/Safari need the link in the document; revoking right away
      // can cancel the download before it starts.
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { a.remove(); URL.revokeObjectURL(url); }, 1000);
    } catch (e) {
      console.error(e);
      alert(this._t("settings_export_error") + this._colon() + e.message);
    }
  }

  _onBackupFileSelected(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      input.value = "";
      let data;
      try {
        data = JSON.parse(reader.result);
      } catch (e) {
        alert(this._t("settings_import_error") + this._colon() + this._t("import_invalid_json"));
        return;
      }
      if (!confirm(this._t("settings_import_confirm"))) return;
      try {
        const result = await this._ws("cover_automatic/import", { data });
        // Everything shown now comes from the imported file
        this._settingsDraft = null;
        this._updateConfigFromResult(result);
        this._showToast();
        alert(this._t("settings_import_success"));
      } catch (e) {
        console.error(e);
        this._showError(e);
      }
    };
    reader.readAsText(file);
  }
};

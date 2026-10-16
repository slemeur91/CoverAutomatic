// CoverAutomatic panel -- Settings helpers: comfort profiles, dependent options, explanations, thresholds.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).

export const SettingsComfortMixin = (Base) => class extends Base {
  // Framed group of options. With `dep` (CSS selector of the controlling
  // input) the body is greyed out and its inputs disabled while the control
  // is off; values are kept and still saved. Modes: "checked", "unchecked",
  // "value" (non-empty), "tristate" ("" = follow `global`).
  // Scenarios of a comfort profile ("a" or "b"): the settings form (draft)
  // or, with saved = true, the stored configuration. A scenario is in one
  // profile at most; without profile it has no setpoints.
  _profileIds(p, saved = false) {
    const field = "profile_" + p + "_scenarios";
    const scenarios = (this._config && this._config.scenarios) || {};
    let ids = null;
    if (!saved) {
      const hidden = this.shadowRoot && this.shadowRoot.querySelector(`[data-settings-field="${field}"]`);
      const draft = this._settingsDraft && this._settingsDraft[field];
      const raw = hidden ? hidden.value : (draft ? draft.value : undefined);
      if (raw !== undefined) ids = String(raw).split(",").map(x => x.trim()).filter(Boolean);
    }
    if (ids === null) ids = (((this._config && this._config.settings) || {})[field] || []).slice();
    return ids.filter(id => id in scenarios);
  }

  // Scenario ids of a comfort profile, in the order of the scenarios
  _profileScenarioIds(p, saved = false) {
    const members = new Set(this._profileIds(p, saved));
    const other = new Set(this._profileIds(p === "a" ? "b" : "a", saved));
    return Object.keys((this._config && this._config.scenarios) || {})
      .filter(id => members.has(id) && (p === "b" || !other.has(id)));
  }

  // Scenarios in neither profile (no setpoints)
  _profileFreeIds(saved = false) {
    const used = new Set([...this._profileScenarioIds("a", saved), ...this._profileScenarioIds("b", saved)]);
    return Object.keys((this._config && this._config.scenarios) || {}).filter(id => !used.has(id));
  }

  _scenarioNames(ids) {
    const scenarios = (this._config && this._config.scenarios) || {};
    return ids.map(id => (scenarios[id] && scenarios[id].name) || id).join(", ");
  }

  _profileScenarioNames(p, saved = false) {
    return this._scenarioNames(this._profileScenarioIds(p, saved));
  }

  // Global setpoints of a comfort profile: the form values (draft) or, with
  // saved = true, the stored ones
  _profileValues(p, saved = false) {
    const s = (this._config && this._config.settings) || {};
    const sfx = p === "b" ? "_b" : "";
    const def = p === "b" ? [22, 24, 1] : [21, 23, 1];
    const read = (name, d) => {
      let raw = s[name];
      if (!saved) {
        const el = this.shadowRoot ? this.shadowRoot.querySelector(`[data-settings-field="${name}"]`) : null;
        const draft = this._settingsDraft && this._settingsDraft[name];
        if (el) raw = el.value;
        else if (draft) raw = draft.value;
      }
      const v = parseFloat(raw);
      return Number.isFinite(v) ? v : d;
    };
    return {
      min: read("comfort_temp_min" + sfx, def[0]),
      max: read("comfort_temp_max" + sfx, def[1]),
      h: read("comfort_hysteresis" + sfx, def[2]),
    };
  }

  // Hidden fields holding the scenarios of both profiles, and the line
  // listing the scenarios without profile
  _renderProfileFields() {
    const saved = !this._settingsDraft;
    return ["a", "b"].map(p => {
      const v = this._esc(this._profileScenarioIds(p, saved).join(","));
      const init = this._esc(this._profileScenarioIds(p, true).join(","));
      return `<input type="hidden" data-settings-field="profile_${p}_scenarios" value="${v}" data-initial="${init}">`;
    }).join("");
  }

  _renderProfileFree() {
    return `<div class="settings-hint profile-free" data-profile-free></div>`;
  }

  // Help box written with a light markup: blank line = new block, "- " =
  // bullet, **text** = bold.
  _renderRichHint(key) {
    const inline = (t) => this._esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    const blocks = this._t(key).split(/\n\s*\n/).map(block => {
      const lines = block.split("\n");
      let html = "", items = [];
      const flush = () => { if (items.length) { html += `<ul>${items.map(i => `<li>${inline(i)}</li>`).join("")}</ul>`; items = []; } };
      for (const line of lines) {
        if (line.startsWith("- ")) items.push(line.slice(2));
        else { flush(); html += `<p>${inline(line)}</p>`; }
      }
      flush();
      return html;
    });
    return `<div class="settings-hint-intro rich-hint">${blocks.join("")}</div>`;
  }

  // Scenario chips of a profile column. In the sensors tab a click moves the
  // scenario to the other profile; elsewhere they are read-only.
  _renderProfileChips(p, editable) {
    const scenarios = (this._config && this._config.scenarios) || {};
    const members = new Set(this._profileScenarioIds(p));
    const chips = Object.entries(scenarios).map(([id, sc]) => {
      const member = members.has(id);
      if (!editable && !member) return "";
      const tag = editable ? "button" : "span";
      const act = editable ? ` type="button" data-action="profile-scenario" data-profile="${p}" data-scenario="${this._esc(id)}"` : "";
      return `<${tag} class="ms-item${member ? " selected" : ""}"${act}>${this._esc(sc.name || id)}</${tag}>`;
    }).join("");
    return `<div class="multi-select profile-chips" data-profile-chips="${p}" data-editable="${editable ? "1" : "0"}">${chips}</div>`;
  }

  // Greys out the column of a profile without scenario and refreshes the chips
  _refreshProfiles() {
    const root = this.shadowRoot;
    if (!root) return;
    root.querySelectorAll("[data-profile-chips]").forEach(box => {
      const html = this._renderProfileChips(box.dataset.profileChips, box.dataset.editable === "1");
      const tmp = document.createElement("div");
      tmp.innerHTML = html;
      const fresh = tmp.firstElementChild.innerHTML;
      if (box.innerHTML !== fresh) box.innerHTML = fresh;
    });
    const free = this._scenarioNames(this._profileFreeIds());
    root.querySelectorAll("[data-profile-free]").forEach(el => {
      el.hidden = !free;
      el.textContent = free ? this._t("profile_free").replace("{list}", free) : "";
    });
    root.querySelectorAll(".profile-col[data-profile]").forEach(col => {
      const used = this._profileScenarioIds(col.dataset.profile).length > 0;
      col.classList.toggle("profile-off", !used);
      col.querySelectorAll(".profile-fields input, .profile-fields select").forEach(el => {
        if (!used) {
          if (!el.disabled) { el.disabled = true; el.dataset.profileDisabled = "1"; }
        } else if (el.dataset.profileDisabled) {
          el.disabled = false;
          delete el.dataset.profileDisabled;
        }
      });
    });
  }

  // Click on a scenario chip: adds the scenario to this profile (it leaves
  // the other one) or removes it (the scenario then has no setpoints)
  _onProfileScenario(el) {
    const root = this.shadowRoot;
    const p = el.dataset.profile, other = p === "a" ? "b" : "a", id = el.dataset.scenario;
    const own = root.querySelector(`[data-settings-field="profile_${p}_scenarios"]`);
    const oth = root.querySelector(`[data-settings-field="profile_${other}_scenarios"]`);
    if (!own || !oth) return;
    const mine = this._profileScenarioIds(p), theirs = this._profileScenarioIds(other);
    // Lists kept in the order of the scenarios, like the stored value, so
    // undoing a change does not leave the form marked as modified
    const order = Object.keys((this._config && this._config.scenarios) || {});
    if (mine.includes(id)) {
      own.value = mine.filter(x => x !== id).join(",");
    } else {
      own.value = order.filter(x => x === id || mine.includes(x)).join(",");
      oth.value = theirs.filter(x => x !== id).join(",");
    }
    this._refreshDeps();
  }

  _optBox({ dep = null, mode = "checked", global = null, title = "", head = "", body = "", offNote = "", cls = "", value = null, force = false } = {}) {
    const depAttrs = dep
      ? ` data-dep="${this._esc(dep)}" data-dep-mode="${mode}"${global == null ? "" : ` data-dep-global="${global ? "1" : "0"}"`}`
        + (value == null ? "" : ` data-dep-value="${this._esc(value)}"`) + (force ? ` data-dep-force="1"` : "")
      : "";
    return `<div class="opt-box${cls ? " " + cls : ""}"${depAttrs}>
      ${title ? `<div class="opt-box-title">${this._esc(title)}</div>` : ""}
      ${head}
      ${offNote ? `<div class="opt-box-offnote">${this._esc(offNote)}</div>` : ""}
      <div class="opt-box-body">${body}</div>
    </div>`;
  }

  // Apply the enabled/greyed state of every dependent option box.
  _refreshDeps() {
    const root = this.shadowRoot;
    if (!root) return;
    this._refreshProfiles();
    this._refreshSunExplain();
    this._refreshHystExplains();
    this._refreshEntityDriven();
    root.querySelectorAll(".opt-box[data-dep]").forEach(box => {
      let ctl = null;
      try { ctl = root.querySelector(box.dataset.dep); } catch (e) { ctl = null; }
      let on = !!ctl && !ctl.disabled;
      if (box.dataset.depMode === "anyequals") {
        // On when one of the matching controls has the value
        let ctls = [];
        try { ctls = Array.from(root.querySelectorAll(box.dataset.dep)); } catch (e) { ctls = []; }
        on = ctls.some(c => c.value === box.dataset.depValue);
      } else if (on) {
        const mode = box.dataset.depMode || "checked";
        if (mode === "checked") on = !!ctl.checked;
        else if (mode === "unchecked") on = !ctl.checked;
        else if (mode === "value") on = String(ctl.value || "").trim() !== "";
        else if (mode === "tristate") on = ctl.value === "" ? box.dataset.depGlobal === "1" : ctl.value === "true";
        else if (mode === "equals") on = ctl.value === box.dataset.depValue;
      }
      if (box.dataset.depForce === "1") on = true;
      box.classList.toggle("opt-off", !on);
      const body = box.querySelector(":scope > .opt-box-body");
      if (!body) return;
      body.querySelectorAll("input, select, textarea, button").forEach(el => {
        if (!on) {
          if (!el.disabled) { el.disabled = true; el.dataset.depDisabled = "1"; }
        } else if (el.dataset.depDisabled) {
          el.disabled = false;
          delete el.dataset.depDisabled;
        }
      });
    });
  }

  // "How does it work?" table of the Sun on facade card. Rows matching the
  // current (draft) choices are highlighted by _refreshSunExplain.
  // A threshold driven by an entity: the number field is replaced by a greyed
  // box with the entity's value; the number stays stored as the fallback used
  // while the entity is unavailable.
  _refreshEntityDriven() {
    const root = this.shadowRoot;
    if (!root) return;
    root.querySelectorAll("[data-threshold-entity]").forEach(sel => {
      const group = sel.closest(".form-group");
      const num = group ? group.querySelector(':scope > input[type="number"]') : null;
      if (!num) return;
      let shadow = num.nextElementSibling;
      if (!shadow || !shadow.classList.contains("entity-shadow")) {
        shadow = document.createElement("div");
        shadow.className = "entity-shadow";
        num.insertAdjacentElement("afterend", shadow);
      }
      const entity = sel.value;
      num.classList.toggle("entity-driven", !!entity);
      shadow.hidden = !entity;
      group.querySelectorAll(":scope > .global-note").forEach(n => { n.hidden = !!entity; });
      if (!entity) return;
      const st = this._hass && this._hass.states ? this._hass.states[entity] : null;
      const v = st ? parseFloat(st.state) : NaN;
      const unit = st && st.attributes.unit_of_measurement ? " " + st.attributes.unit_of_measurement : "";
      const fallback = num.value !== "" ? num.value : num.placeholder;
      const html = `<div class="entity-shadow-value">${this._esc(Number.isFinite(v) ? String(v) + unit : "—")}</div>`
        + (fallback !== "" && fallback != null
          ? `<div class="entity-shadow-note">${this._esc(this._t("threshold_fallback").replace("{v}", fallback))}</div>` : "");
      if (shadow.dataset.sig !== html) { shadow.innerHTML = html; shadow.dataset.sig = html; }
    });
  }

  // "How does it work?" blocks of the hysteresis settings. The table is
  // computed from the values currently in the form (draft included) and
  // refreshed on every input by _refreshHystExplains.
  _renderHystExplain(kind) {
    const open = this._explainOpen && this._explainOpen[kind];
    const body = this._hystBody(kind, this._hystValues(kind));
    return `<details class="sun-explain" data-hyst="${kind}"${open ? " open" : ""}>
      <summary data-action="explain-toggle" data-key="${kind}">${this._esc(this._t("hyst_title_" + kind))}</summary>
      <div class="sun-explain-body" data-hyst-body>${body}</div>
    </details>`;
  }

  _refreshHystExplains() {
    const root = this.shadowRoot;
    if (!root) return;
    root.querySelectorAll("details[data-hyst]").forEach(d => {
      const body = d.querySelector("[data-hyst-body]");
      if (!body) return;
      const html = this._hystBody(d.dataset.hyst, this._hystValues(d.dataset.hyst));
      if (body.dataset.sig !== html) { body.innerHTML = html; body.dataset.sig = html; }
    });
  }

  _hystValues(kind) {
    const s = (this._config && this._config.settings) || {};
    const root = this.shadowRoot;
    const field = (name) => root ? root.querySelector(`[data-settings-field="${name}"]`) : null;
    const str = (name) => { const el = field(name); return el ? el.value : (s[name] || ""); };
    const num = (name, def) => { const v = parseFloat(str(name)); return Number.isFinite(v) ? v : def; };
    const unitOf = (id) => {
      const st = id && this._hass && this._hass.states ? this._hass.states[id] : null;
      return (st && st.attributes.unit_of_measurement) || "";
    };
    if (kind === "comfort" || kind === "comfort_b") {
      const v = this._profileValues(kind === "comfort_b" ? "b" : "a");
      return { a: v.min, b: v.max, h: v.h };
    }
    if (kind === "rules") {
      // Real example taken from the rules when one uses the condition
      const h = num("threshold_hysteresis", 0.5);
      const rules = Object.values((this._config && this._config.rules) || {})
        .sort((x, y) => (y.enabled !== false) - (x.enabled !== false));
      for (const r of rules) {
        for (const c of r.conditions || []) {
          if (c.type !== "temperature_above" && c.type !== "temperature_below") continue;
          const p = c.params || {};
          const t = parseFloat(p.temperature != null ? p.temperature : p.value);
          if (Number.isFinite(t)) return { t, h, above: c.type === "temperature_above", rule: r.name || r.id };
        }
      }
      return { t: 18, h, above: true, rule: null };
    }
    if (kind === "solar") {
      const t = this._effectiveThreshold(str("solar_threshold_entity"), num("solar_threshold", 0));
      const h = num("solar_hysteresis", 0), u = unitOf(str("solar_sensor"));
      return t > 0 ? { t, h, u, ex: false } : { t: 30000, h: h || 5000, u: u || "lx", ex: true };
    }
    const t = num("wind_speed_threshold", 0), u = unitOf(str("wind_sensor"));
    let h = num("wind_speed_hysteresis", 0);
    if (t > 0) { if (h >= t) h = 0; return { t, h, u, ex: false }; }
    return { t: 50, h: h > 0 && h < 50 ? h : 10, u: u || "km/h", ex: true };
  }

  _hystBody(kind, v) {
    const lang = (this._hass && this._hass.language) || "en";
    const fmt = (x) => {
      const r = String(Math.round(x * 100) / 100);
      return /^(fr|de)/.test(lang) ? r.replace(".", ",") : r;
    };
    const fu = (x, u) => fmt(x) + (u ? " " + u : "");
    const tr = (key, map) => {
      let out = this._t(key);
      for (const [k, val] of Object.entries(map || {})) out = out.split("{" + k + "}").join(val);
      return out;
    };
    const between = (a, b, u) => tr("hyst_between", { a: fmt(a), b: fmt(b) }) + (u ? " " + u : "");
    const table = (cols, rows) => `<table class="sun-explain-table">
        <thead><tr>${cols.map(c => `<th>${this._esc(this._t(c))}</th>`).join("")}</tr></thead>
        <tbody>${rows.map(r => `<tr><td>${this._esc(r[0])}</td><td>${this._esc(r[1])}</td></tr>`).join("")}</tbody>
      </table>`;
    const so = (lines) => `<div class="sun-explain-so"><b>${this._esc(this._t("sun_explain_so"))}</b>
        <ul>${lines.map(l => `<li>${this._esc(l)}</li>`).join("")}</ul></div>`;
    const intro = (key, map) => `<div class="settings-hint">${this._esc(tr(key, map))}</div>`;
    const w = this._t("hyst_with_values");
    if (kind === "comfort" || kind === "comfort_b") {
      const { a, b, h } = v, ah = a + h, bh = b - h, deg = "°C";
      const rows = [[this._t("sun_below").replace("{t}", fmt(a)), this._t("hyst_cold")]];
      if (h > 0) rows.push([between(a, ah, deg), this._t("hyst_stay_cold")]);
      if (ah < bh) rows.push([between(ah, bh, deg), this._t("hyst_comfortable")]);
      if (h > 0) rows.push([between(bh, b, deg), this._t("hyst_stay_hot")]);
      rows.push([this._t("sun_above").replace("{t}", fmt(b)), this._t("hyst_hot")]);
      const m = { a: fmt(a), b: fmt(b), ah: fmt(ah), bh: fmt(bh), mid: fmt(a + h / 2), h: fmt(h), w };
      return intro("hyst_comfort_intro", m) + table(["hyst_col_room_temp", "hyst_col_state"], rows)
        + so([tr("hyst_comfort_so1", m), tr("hyst_comfort_so2", m), tr("hyst_comfort_so3", m), tr("hyst_comfort_so4", m)]);
    }
    if (kind === "rules" || kind === "solar") {
      const { t, h } = v, u = kind === "rules" ? "°C" : v.u;
      const yes = this._t(kind === "rules" ? "hyst_true" : "hyst_strong_yes");
      const no = this._t(kind === "rules" ? "hyst_false" : "hyst_strong_no");
      const rows = h > 0
        ? [[tr("hyst_above", { a: fu(t + h, u) }), yes], [between(t - h, t + h, u), this._t("hyst_keep")], [tr("hyst_below", { a: fu(t - h, u) }), no]]
        : [[tr("hyst_above", { a: fu(t, u) }), yes], [tr("hyst_below", { a: fu(t, u) }), no]];
      const m = { t: kind === "rules" ? fmt(t) : fu(t, u), h: kind === "rules" ? fmt(h) : fu(h, u),
        th: kind === "rules" ? fmt(t + h) : fu(t + h, u), tl: kind === "rules" ? fmt(t - h) : fu(t - h, u),
        w: v.ex ? this._t("hyst_example") : w };
      if (kind === "rules") {
        const sfx = v.above ? "" : "_below";
        const rrows = v.above ? rows : rows.slice().reverse().map((r, i, arr) => [r[0], arr[arr.length - 1 - i][1]]);
        m.rule = v.rule || "";
        m.op = this._t(v.above ? "hyst_op_above" : "hyst_op_below");
        const lines = h > 0
          ? [tr("hyst_rules_so1" + sfx, m), tr("hyst_rules_so2" + sfx, m), tr("hyst_rules_so3" + sfx, m)]
          : [this._t("hyst_zero")];
        return `<div class="settings-hint" style="margin-bottom:6px"><b>${this._esc(this._t("hyst_rules_scope"))}</b></div>`
          + intro(v.rule ? "hyst_rules_intro_real" : "hyst_rules_intro", m)
          + table(["hyst_col_temp", "hyst_col_condition"], rrows) + so(lines);
      }
      const lines = h > 0 ? [tr("hyst_solar_so1", m), tr("hyst_solar_so2", m)] : [this._t("hyst_zero"), tr("hyst_solar_so2", m)];
      return intro("hyst_solar_intro", m) + table(["hyst_col_sensor", "hyst_col_strong"], rows) + so(lines);
    }
    // wind
    const { t, h, u } = v, tl = t - h;
    const rows = [["≥ " + fu(t, u), this._t("hyst_wind_on")]];
    if (h > 0) rows.push([between(tl, t, u), this._t("hyst_wind_stay")]);
    rows.push([(h > 0 ? "≤ " + fu(tl, u) : "< " + fu(t, u)), this._t("hyst_wind_off")]);
    const m = { t: fu(t, u), h: fu(h, u), tl: fu(tl, u), w: v.ex ? this._t("hyst_example") : w };
    const lines = h > 0 ? [tr("hyst_wind_so1", m), tr("hyst_wind_so2", m)] : [this._t("hyst_zero")];
    return intro("hyst_wind_intro", m) + table(["hyst_col_wind", "hyst_col_protection"], rows) + so(lines);
  }

  // Numeric state of a threshold entity when readable, else the static value
  _effectiveThreshold(entityId, fallback) {
    const st = entityId && this._hass?.states ? this._hass.states[entityId] : null;
    const v = st ? parseFloat(st.state) : NaN;
    return Number.isFinite(v) ? Math.round(v * 10) / 10 : fallback;
  }

  _renderSunExplain(cmin, cmax, p = "a") {
    const t = (k) => this._esc(this._t(k));
    const sun = t("sun_explain_sun"), noSun = t("sun_explain_no_sun");
    const rows = [
      ["cold-on", "sun_explain_room_cold_on", noSun, "sun_explain_eff_warm", this._t("sun_below").replace("{t}", cmin)],
      ["cold-off", "sun_explain_room_cold_off", sun, "sun_explain_eff_close", this._t("sun_below").replace("{t}", cmin)],
      ["position", "sun_explain_room_position", sun, "sun_explain_eff_close_as_hot", this._t("sun_between").replace("{min}", cmin).replace("{max}", cmax)],
      ["ignore", "sun_explain_room_ignore", noSun, "sun_explain_eff_wait", this._t("sun_between").replace("{min}", cmin).replace("{max}", cmax)],
      ["preemptive", "sun_explain_room_preemptive", t("sun_explain_sun_if_strong"), "sun_explain_eff_strong", this._t("sun_between").replace("{min}", cmin).replace("{max}", cmax)],
      ["hot", "sun_explain_room_hot", t("sun_explain_sun_always"), "sun_explain_eff_close", this._t("sun_above").replace("{t}", cmax)],
    ];
    const key = "sun_" + p;
    return `<details class="sun-explain" data-sun-explain="${p}"${this._explainOpen && this._explainOpen[key] ? " open" : ""}>
      <summary data-action="explain-toggle" data-key="${key}">${t("sun_explain_title")}</summary>
      <div class="sun-explain-body">
        <div class="settings-hint">${t("sun_explain_intro")}</div>
        <table class="sun-explain-table">
          <thead><tr><th>${t("sun_explain_col_room")}</th><th>${t("sun_explain_col_answer")}</th><th>${t("sun_explain_col_effect")}</th></tr></thead>
          <tbody>${rows.map(([id, room, answer, eff, range]) => `<tr data-sun-row="${id}">
            <td>${t(room)}<br><span class="radio-hint">${this._esc(range)}</span></td><td>${answer}</td><td>${t(eff)}</td></tr>`).join("")}</tbody>
        </table>
        <div class="sun-explain-so"><b>${t("sun_explain_so")}</b>
          <ul><li>${t("sun_explain_cold")}</li><li>${t("sun_explain_hot")}</li><li>${t("sun_explain_comfort")}</li></ul>
        </div>
      </div>
    </details>`;
  }

  _refreshSunExplain() {
    const root = this.shadowRoot;
    if (!root) return;
    root.querySelectorAll("details[data-sun-explain]").forEach(d => {
      const sfx = d.dataset.sunExplain === "b" ? "_b" : "";
      const heat = root.querySelector(`[data-settings-field="sun_heating_ignore${sfx}"]`);
      const mode = root.querySelector(`[data-settings-field="sun_comfort_mode${sfx}"]`);
      const on = new Set(["hot", heat && heat.checked ? "cold-on" : "cold-off", mode ? mode.value : ""]);
      d.querySelectorAll("tr[data-sun-row]").forEach(tr => tr.classList.toggle("current", on.has(tr.dataset.sunRow)));
    });
  }

  // Behaviour of "Sun on facade" while the room is in its comfort range,
  // stored as two flags: position (no ignore) / ignore / ignore unless
  // strong solar radiation (preemptive shading).
  _sunComfortMode(neutralIgnore, preemptive) {
    if (!neutralIgnore) return "position";
    return preemptive ? "preemptive" : "ignore";
  }

  _sunComfortFlags(mode) {
    return {
      sun_neutral_ignore: mode !== "position",
      preemptive_shading: mode === "preemptive",
    };
  }

  // Covers whose effective setting uses the sunshine sensor: those with an
  // indoor sensor, when a profile in use is set to "strong sunshine"
  _coversUsingRadiation() {
    const s = this._config.settings || {};
    const root = this.shadowRoot;
    const preemptive = ["a", "b"].some(p => {
      if (!this._profileScenarioIds(p).length) return false;
      const sfx = p === "b" ? "_b" : "";
      const el = root && root.querySelector(`[data-settings-field="sun_comfort_mode${sfx}"]`);
      return el ? el.value === "preemptive"
        : this._sunComfortMode(s["sun_neutral_ignore" + sfx] !== false, s["preemptive_shading" + sfx] !== false) === "preemptive";
    });
    if (!preemptive) return 0;
    return Object.values(this._config.covers || {}).filter(c => c.indoor_temp_sensor || s.indoor_temp_sensor).length;
  }

  _renderSensorValue(entityId, unit) {
    if (!entityId || !this._hass || !this._hass.states) return "";
    const state = this._hass.states[entityId];
    if (!state || state.state === "unavailable" || state.state === "unknown") return "";
    let text;
    if (!unit && typeof this._hass.formatEntityState === "function") {
      try { text = this._hass.formatEntityState(state); } catch (e) { text = undefined; }
    }
    if (!text) text = state.state + (unit || state.attributes.unit_of_measurement || "");
    return '<div class="sensor-current-value">' + this._t("settings_current_value") + this._colon() + this._esc(text) + '</div>';
  }

  // Entities that can provide a threshold value (numbers and numeric text).
  _thresholdEntityOptions(currentValue, kind = null) {
    const states = (this._hass && this._hass.states) || {};
    const list = Object.values(states).filter(st => {
      const dom = st.entity_id.split(".")[0];
      if (kind === "temperature") {
        // Setpoints: number helpers, and sensors in degrees only
        if (dom === "input_number" || dom === "number") return true;
        const u = st.attributes.unit_of_measurement;
        return dom === "sensor" && (st.attributes.device_class === "temperature" || u === "°C" || u === "°F");
      }
      if (dom === "input_number" || dom === "number" || dom === "input_text") return true;
      // Sensors: only numeric ones (a text sensor cannot be a threshold)
      return dom === "sensor" && (st.attributes.unit_of_measurement != null || Number.isFinite(parseFloat(st.state)));
    }).sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id));
    let html = `<option value="">-- ${this._t("none")} --</option>`;
    let found = false;
    for (const e of list) {
      const name = e.attributes.friendly_name || e.entity_id;
      const sel = e.entity_id === currentValue;
      if (sel) found = true;
      html += `<option value="${this._esc(e.entity_id)}"${sel ? " selected" : ""}>${this._esc(name)} (${this._esc(e.entity_id)})</option>`;
    }
    // Keep a configured entity selectable even when it is not loaded
    if (currentValue && !found) html += `<option value="${this._esc(currentValue)}" selected>${this._esc(currentValue)}</option>`;
    return html;
  }

  // Current value of a threshold entity, e.g. "currently: 23 °C".
  _thresholdEntityValue(entityId) {
    if (!entityId) return "";
    const st = this._hass && this._hass.states ? this._hass.states[entityId] : null;
    if (!st || st.state === "unavailable" || st.state === "unknown" || st.state === "") {
      return `<span class="threshold-entity-unavail">${this._esc(this._t("threshold_entity_unavailable"))}</span>`;
    }
    const u = st.attributes.unit_of_measurement;
    return this._esc(this._t("threshold_entity_current") + this._colon() + st.state + (u ? " " + u : ""));
  }

  // Optional entity next to a numeric threshold. attrs: the select's
  // data attributes (settings field or cover-input).
  _renderThresholdEntity(attrs, currentValue, kind = null) {
    const cur = currentValue || "";
    const control = (this._hass && this._hass.states)
      ? `<select ${attrs} data-threshold-entity>${this._thresholdEntityOptions(cur, kind)}</select>`
      : `<input type="text" value="${this._esc(cur)}" ${attrs} data-threshold-entity>`;
    return `<div class="threshold-entity">
      <div class="threshold-entity-label">${this._esc(this._t("threshold_entity"))}</div>
      ${control}
      <div class="threshold-entity-value">${this._thresholdEntityValue(cur)}</div>
      ${this._hint("threshold_entity_hint")}
    </div>`;
  }
};

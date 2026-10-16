// CoverAutomatic panel -- Native Home Assistant conditions: form, YAML, validation.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).

export const HaConditionsMixin = (Base) => class extends Base {
  // Parse a condition config into the form model, or null when the form
  // cannot represent it (templates, zones, nested and/or...).
  _haFormModel(config, opHint = null) {
    if (!config || typeof config !== "object") return null;
    let cfg = config;
    let negate = false;
    if (cfg.condition === "not") {
      const subs = Array.isArray(cfg.conditions) ? cfg.conditions : [];
      if (subs.length !== 1 || !subs[0] || subs[0].condition !== "state") return null;
      negate = true;
      cfg = subs[0];
    }
    const allowed = new Set(["condition", "entity_id", "attribute", "state", "for", "above", "below"]);
    if (Object.keys(cfg).some(k => !allowed.has(k))) return null;
    let entity = cfg.entity_id;
    if (Array.isArray(entity)) {
      if (entity.length > 1) return null;
      entity = entity[0];
    }
    if (entity != null && typeof entity !== "string") return null;
    const model = { kind: null, entity: entity || "", attribute: cfg.attribute || "", negate };
    if (cfg.condition === "state") {
      if (cfg.above != null || cfg.below != null) return null;
      model.kind = "state";
      const st = cfg.state;
      model.states = st == null ? [] : (Array.isArray(st) ? st.map(String) : [String(st)]);
      model.forMinutes = null;
      if (cfg.for != null) {
        const f = cfg.for;
        if (typeof f === "object" && !Array.isArray(f)) {
          const keys = Object.keys(f);
          if (keys.some(k => !["hours", "minutes", "seconds"].includes(k))) return null;
          model.forMinutes = (Number(f.hours) || 0) * 60 + (Number(f.minutes) || 0) + (Number(f.seconds) || 0) / 60;
        } else if (typeof f === "string" && /^\d{1,2}:\d{2}(:\d{2})?$/.test(f)) {
          const p = f.split(":").map(Number);
          model.forMinutes = p[0] * 60 + p[1] + (p[2] || 0) / 60;
        } else if (typeof f === "number") {
          model.forMinutes = f / 60;
        } else {
          return null;
        }
      }
      return model;
    }
    if (cfg.condition === "numeric_state" && !negate) {
      if (cfg.state != null || cfg.for != null) return null;
      const num = (v) => (v == null || v === "" ? null : Number(v));
      if ((cfg.above != null && !Number.isFinite(num(cfg.above))) || (cfg.below != null && !Number.isFinite(num(cfg.below)))) return null;
      model.kind = "numeric";
      model.above = num(cfg.above);
      model.below = num(cfg.below);
      model.operator = model.above != null && model.below != null ? "between" : (model.below != null ? "below" : "above");
      // The chosen operator is kept in the params while a value is missing
      // (e.g. "between" with only the minimum filled in yet).
      if (["above", "below", "between"].includes(opHint)) model.operator = opHint;
      return model;
    }
    return null;
  }

  // Build the Home Assistant condition config from the form model.
  _haFormToConfig(m) {
    if (m.kind === "numeric") {
      const cfg = { condition: "numeric_state", entity_id: m.entity || "" };
      if (m.attribute) cfg.attribute = m.attribute;
      if (m.operator !== "below" && m.above != null && Number.isFinite(m.above)) cfg.above = m.above;
      if (m.operator !== "above" && m.below != null && Number.isFinite(m.below)) cfg.below = m.below;
      return cfg;
    }
    const cfg = { condition: "state", entity_id: m.entity || "" };
    if (m.attribute) cfg.attribute = m.attribute;
    cfg.state = m.states.length === 1 ? m.states[0] : [...m.states];
    if (!m.negate && m.forMinutes != null && m.forMinutes > 0) cfg.for = { minutes: m.forMinutes };
    return m.negate ? { condition: "not", conditions: [cfg] } : cfg;
  }

  _haDefaultConfig(kind) {
    return kind === "numeric"
      ? { condition: "numeric_state", entity_id: "", above: 0 }
      : { condition: "state", entity_id: "", state: [] };
  }

  // Missing field in a form-built condition (shown instead of HA's error).
  _haFormIncomplete(m) {
    if (!m) return null;
    if (!m.entity) return "ha_incomplete_entity";
    if (m.kind === "state" && m.states.length === 0) return "ha_incomplete_states";
    if (m.kind === "numeric") {
      if (m.operator === "between" && (m.above == null || m.below == null)) return "ha_incomplete_value";
      if (m.operator === "above" && m.above == null) return "ha_incomplete_value";
      if (m.operator === "below" && m.below == null) return "ha_incomplete_value";
    }
    return null;
  }

  // Possible states of an entity, for the state buttons.
  _haKnownStates(stateObj, attribute) {
    const out = [];
    const add = (v) => { if (v != null && v !== "" && !out.includes(String(v))) out.push(String(v)); };
    if (!stateObj) return out;
    if (attribute) {
      add(stateObj.attributes[attribute]);
      return out;
    }
    const domain = stateObj.entity_id.split(".")[0];
    const a = stateObj.attributes || {};
    const ONOFF = ["on", "off"];
    const BY_DOMAIN = {
      binary_sensor: ONOFF, switch: ONOFF, light: ONOFF, input_boolean: ONOFF, fan: ONOFF,
      automation: ONOFF, script: ONOFF, remote: ONOFF, siren: ONOFF, humidifier: ONOFF,
      cover: ["open", "closed", "opening", "closing"],
      lock: ["locked", "unlocked", "locking", "unlocking", "open", "jammed"],
      alarm_control_panel: ["disarmed", "armed_home", "armed_away", "armed_night", "armed_vacation", "armed_custom_bypass", "arming", "pending", "triggered"],
      media_player: ["off", "on", "idle", "playing", "paused", "standby", "buffering"],
      sun: ["above_horizon", "below_horizon"],
      vacuum: ["cleaning", "docked", "idle", "paused", "returning", "error"],
      lawn_mower: ["mowing", "docked", "paused", "returning", "error"],
      weather: ["sunny", "clear-night", "partlycloudy", "cloudy", "fog", "rainy", "pouring", "lightning", "lightning-rainy", "hail", "snowy", "snowy-rainy", "windy", "windy-variant", "exceptional"],
    };
    if (Array.isArray(a.options)) a.options.forEach(add);
    if (domain === "climate" && Array.isArray(a.hvac_modes)) a.hvac_modes.forEach(add);
    if (domain === "water_heater" && Array.isArray(a.operation_list)) a.operation_list.forEach(add);
    if (domain === "person" || domain === "device_tracker") {
      add("home"); add("not_home");
      for (const z of Object.values(this._hass.states)) {
        if (z.entity_id.startsWith("zone.") && z.entity_id !== "zone.home") add(z.attributes.friendly_name);
      }
    }
    (BY_DOMAIN[domain] || []).forEach(add);
    add(stateObj.state);
    return out.filter(v => v !== "unavailable" && v !== "unknown");
  }

  _haStateLabel(stateObj, attribute, value) {
    try {
      if (stateObj && attribute && this._hass.formatEntityAttributeValue) {
        return this._hass.formatEntityAttributeValue(stateObj, attribute, value);
      }
      if (stateObj && !attribute && this._hass.formatEntityState) {
        return this._hass.formatEntityState(stateObj, value);
      }
    } catch (e) { /* fall through */ }
    return String(value);
  }

  _haAttributeLabel(stateObj, attribute) {
    try {
      if (stateObj && this._hass.formatEntityAttributeName) return this._hass.formatEntityAttributeName(stateObj, attribute);
    } catch (e) { /* fall through */ }
    return attribute;
  }

  _haEntityName(entityId) {
    const s = entityId && this._hass?.states ? this._hass.states[entityId] : null;
    return s ? (s.attributes.friendly_name || entityId) : (entityId || "?");
  }

  _haCondTitle(cond) {
    const p = cond.params || {};
    if ((p.ui || "form") === "form") {
      const m = this._haFormModel(p.config);
      if (m) return this._t(m.kind === "numeric" ? "cond_ha_numeric" : "cond_ha_state");
    }
    return this._t("cond_ha_condition");
  }

  // Current validation status of an ha_condition card (live result from the
  // validate command, else the status sent with the configuration).
  _haStatus(ruleId, idx) {
    const live = this._haLive && this._haLive[ruleId + ":" + idx];
    if (live) return live;
    const st = this._config?.condition_status?.[ruleId]?.[String(idx)];
    return st || null;
  }

  _renderHaConditionBody(rule, idx, cond) {
    const p = cond.params || {};
    const ui = p.ui || "form";
    const rid = this._esc(rule.id);
    const base = `data-rule="${rid}" data-idx="${idx}"`;
    let html = `<div class="ha-seg" role="tablist">
      <button type="button" class="${ui === "form" ? "on" : ""}" data-action="ha-ui" data-mode="form" ${base} aria-selected="${ui === "form"}">${this._t("ha_tab_form")}</button>
      <button type="button" class="${ui === "yaml" ? "on" : ""}" data-action="ha-ui" data-mode="yaml" ${base} aria-selected="${ui === "yaml"}">${this._t("ha_tab_yaml")}</button>
    </div>`;
    html += '<div class="cond-params ha-params">';
    if (ui === "yaml") {
      const text = p.yaml != null ? p.yaml : "";
      html += `<div class="form-group"><label>${this._t("ha_yaml_label")}</label>
        <textarea class="ha-yaml" rows="${Math.max(4, text.split("\n").length + 1)}" spellcheck="false" data-action="ha-yaml" ${base} placeholder="${this._esc(this._t("ha_yaml_placeholder"))}">${this._esc(text)}</textarea>
        <div class="ha-help">${this._esc(this._t("ha_yaml_help"))}</div></div>`;
    } else {
      const m = this._haFormModel(p.config, p.op);
      if (!m) {
        html += `<div class="ha-msg ha-msg-info">${this._esc(this._t("ha_form_unsupported"))}</div>`;
        html += '</div>';
        html += `<div class="ha-status" data-ha-status="${rid}:${idx}">${this._renderHaStatus(rule.id, idx, null)}</div>`;
        return html;
      }
      html += this._renderHaForm(rule, idx, m);
    }
    html += '</div>';
    html += `<div class="ha-status" data-ha-status="${rid}:${idx}">${this._renderHaStatus(rule.id, idx, ui === "form" ? this._haFormModel(p.config, p.op) : null)}</div>`;
    return html;
  }

  _renderHaForm(rule, idx, m) {
    const base = `data-rule="${this._esc(rule.id)}" data-idx="${idx}"`;
    const stateObj = m.entity && this._hass?.states ? this._hass.states[m.entity] : null;
    let html = '';
    // Kind + entity
    html += `<div class="form-row"><div class="form-group"><label>${this._t("ha_kind")}</label>
      <select data-action="ha-form" data-field="kind" ${base}>
        <option value="state"${m.kind === "state" ? " selected" : ""}>${this._t("ha_kind_state")}</option>
        <option value="numeric"${m.kind === "numeric" ? " selected" : ""}>${this._t("ha_kind_numeric")}</option>
      </select></div>`;
    html += `<div class="form-group"><label>${this._t("ha_entity")}</label>${this._renderHaEntityInput(rule, idx, m.entity)}`;
    if (stateObj) {
      const cur = m.attribute ? stateObj.attributes[m.attribute] : stateObj.state;
      if (cur != null) {
        const fname = stateObj.attributes.friendly_name;
        html += `<div class="ha-current">${fname ? this._esc(fname) + " · " : ""}${this._esc(this._t("ha_current"))}${this._colon()}${this._esc(this._haStateLabel(stateObj, m.attribute, cur))}</div>`;
      }
    }
    html += '</div></div>';

    // Attribute
    const SKIP = new Set(["friendly_name", "icon", "entity_picture", "supported_features", "device_class", "unit_of_measurement",
      "attribution", "assumed_state", "restored", "editable", "id", "user_id", "device_trackers", "options", "hvac_modes",
      "operation_list", "state_class", "entity_id", "source_list", "sound_mode_list", "preset_modes", "fan_modes", "swing_modes"]);
    const attrs = stateObj ? Object.keys(stateObj.attributes).filter(k => !SKIP.has(k)).filter(k => {
      const v = stateObj.attributes[k];
      if (m.kind === "numeric") return typeof v === "number" || (typeof v === "string" && v !== "" && Number.isFinite(Number(v)));
      return v == null || ["string", "number", "boolean"].includes(typeof v);
    }) : [];
    if (m.attribute && !attrs.includes(m.attribute)) attrs.unshift(m.attribute);
    html += `<div class="form-row"><div class="form-group"><label>${this._t("ha_attribute")}</label>
      <select data-action="ha-form" data-field="attribute" ${base}>
        <option value="">${this._t("ha_attribute_none")}</option>
        ${attrs.map(a => `<option value="${this._esc(a)}"${a === m.attribute ? " selected" : ""}>${this._esc(this._haAttributeLabel(stateObj, a))}</option>`).join("")}
      </select></div>`;

    if (m.kind === "state") {
      html += `<div class="form-group"><label>${this._t("ha_compare")}</label>
        <select data-action="ha-form" data-field="negate" ${base}>
          <option value="0"${!m.negate ? " selected" : ""}>${this._t("ha_is")}</option>
          <option value="1"${m.negate ? " selected" : ""}>${this._t("ha_is_not")}</option>
        </select></div></div>`;
      html += `<div class="form-row"><div class="form-group"><label>${this._t("ha_for")}</label>
        <input type="number" min="0" step="any" value="${m.forMinutes != null && !m.negate ? this._esc(String(Math.round(m.forMinutes * 100) / 100)) : ""}" placeholder="0" data-action="ha-form" data-field="for" ${base}${m.negate ? " disabled" : ""}>
        ${m.negate ? `<div class="ha-help">${this._esc(this._t("ha_for_negate_hint"))}</div>` : ""}</div><div class="form-group"></div></div>`;
      // States buttons
      const known = this._haKnownStates(stateObj, m.attribute);
      m.states.forEach(s => { if (!known.includes(s)) known.push(s); });
      html += `<div class="form-group"><label>${this._t("ha_states")}</label><div class="day-select">`;
      for (const s of known) {
        const sel = m.states.includes(s);
        html += `<button type="button" class="day-btn${sel ? " selected" : ""}" data-action="ha-state-toggle" data-val="${this._esc(s)}" ${base} title="${this._esc(s)}">${this._esc(this._haStateLabel(stateObj, m.attribute, s))}</button>`;
      }
      html += `</div><div class="ha-add-state"><input type="text" placeholder="${this._esc(this._t("ha_state_other"))}" data-ha-other="${this._esc(rule.id)}:${idx}">
        <button type="button" class="btn btn-secondary" data-action="ha-state-add" ${base}>${this._t("ha_state_add")}</button></div></div>`;
    } else {
      html += `<div class="form-group"><label>${this._t("ha_operator")}</label>
        <select data-action="ha-form" data-field="operator" ${base}>
          ${["above", "below", "between"].map(o => `<option value="${o}"${m.operator === o ? " selected" : ""}>${this._t("ha_op_" + o)}</option>`).join("")}
        </select></div></div>`;
      const num = (v) => (v == null ? "" : this._esc(String(v)));
      if (m.operator === "between") {
        html += `<div class="form-row"><div class="form-group"><label>${this._t("ha_min")}</label>
          <input type="number" step="any" value="${num(m.above)}" data-action="ha-form" data-field="above" ${base}></div>
          <div class="form-group"><label>${this._t("ha_max")}</label>
          <input type="number" step="any" value="${num(m.below)}" data-action="ha-form" data-field="below" ${base}></div></div>`;
      } else {
        const field = m.operator === "below" ? "below" : "above";
        html += `<div class="form-row"><div class="form-group"><label>${this._t("ha_value")}</label>
          <input type="number" step="any" value="${num(m[field])}" data-action="ha-form" data-field="${field}" ${base}></div><div class="form-group"></div></div>`;
      }
    }
    return html;
  }

  _renderHaEntityInput(rule, idx, value) {
    const attrs = `data-action="ha-form" data-field="entity" data-rule="${this._esc(rule.id)}" data-idx="${idx}"`;
    if (!this._hass || !this._hass.states) {
      return `<input type="text" value="${this._esc(value || "")}" ${attrs}>`;
    }
    const listId = `ca-ha-ent-${this._esc(rule.id)}-${idx}`;
    const entities = Object.values(this._hass.states)
      .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id));
    let html = `<input type="text" list="${listId}" value="${this._esc(value || "")}" placeholder="${this._t("param_entity_search")}" autocomplete="off" ${attrs}>`;
    html += `<datalist id="${listId}">`;
    for (const e of entities) {
      html += `<option value="${this._esc(e.entity_id)}">${this._esc(e.attributes.friendly_name || e.entity_id)}</option>`;
    }
    return html + "</datalist>";
  }

  _renderHaStatus(ruleId, idx, formModel) {
    const incomplete = this._haFormIncomplete(formModel);
    if (incomplete) return `<div class="ha-msg ha-msg-info">${this._esc(this._t(incomplete))}</div>`;
    const st = this._haStatus(ruleId, idx);
    if (!st) return "";
    if (st.pending) return `<div class="ha-msg ha-msg-info">${this._esc(this._t("ha_checking"))}</div>`;
    let html = "";
    if (st.valid) {
      html += `<div class="ha-msg ha-msg-ok">✓ ${this._esc(this._t("ha_valid"))}</div>`;
    } else if (st.error_code && st.error_code !== "pending") {
      html += `<div class="ha-msg ha-msg-err">✕ ${this._esc(this._haErrorText(st))}</div>`;
    }
    if (Array.isArray(st.entities) && st.entities.length) {
      html += `<div class="ha-msg ha-msg-info">${this._esc(this._t("ha_entities"))}${this._colon()}${this._esc(st.entities.join(", "))}</div>`;
    }
    if (Array.isArray(st.unknown_entities) && st.unknown_entities.length) {
      html += `<div class="ha-msg ha-msg-warn">${this._esc(this._t("ha_unknown_entities"))}${this._colon()}${this._esc(st.unknown_entities.join(", "))}</div>`;
    }
    return html;
  }

  _haErrorText(st) {
    const fill = (tpl, values) => tpl.replace(/\{(\w+)\}/g, (mm, n) => (values[n] != null ? String(values[n]) : mm));
    switch (st.error_code) {
      case "yaml":
        return fill(this._t("ha_err_yaml"), { line: st.error_line ?? "?", column: st.error_column ?? "?" }) + (st.error ? " — " + st.error : "");
      case "not_mapping": return this._t("ha_err_not_mapping");
      case "empty": return this._t("ha_err_empty");
      case "request": return this._t("ha_err_request") + (st.error ? this._colon() + st.error : "");
      default: return this._t("ha_err_invalid") + (st.error ? this._colon() + st.error : "");
    }
  }

  _haCond(ruleId, idx) {
    const rule = this._edRule(ruleId);
    const cond = rule && rule.conditions ? rule.conditions[idx] : null;
    if (!cond || cond.type !== "ha_condition") return null;
    if (!cond.params) cond.params = {};
    return cond;
  }

  // Re-render a single condition card (keeps the rest of the editor intact).
  _rerenderCondCard(ruleId, idx) {
    const rule = this._edRule(ruleId);
    const root = this.shadowRoot;
    const card = root && root.querySelector(`.condition-card[data-cond-card="${CSS.escape(ruleId)}:${idx}"]`);
    if (!rule || !card) { this._render(); return; }
    const tmp = document.createElement("div");
    tmp.innerHTML = this._renderConditionCard(rule, idx);
    card.replaceWith(tmp.firstElementChild);
    this._refreshCondPreview();
  }

  _refreshHaStatusBox(ruleId, idx) {
    const cond = this._haCond(ruleId, idx);
    const box = this.shadowRoot && this.shadowRoot.querySelector(`[data-ha-status="${CSS.escape(ruleId)}:${idx}"]`);
    if (!cond || !box) return;
    const model = (cond.params.ui || "form") === "form" ? this._haFormModel(cond.params.config, cond.params.op) : null;
    box.innerHTML = this._renderHaStatus(ruleId, idx, model);
  }

  // Validate the condition with Home Assistant (debounced per card).
  _scheduleHaValidate(ruleId, idx, delay = 400) {
    const key = ruleId + ":" + idx;
    this._haTimers = this._haTimers || {};
    if (this._haTimers[key]) clearTimeout(this._haTimers[key]);
    this._haTimers[key] = setTimeout(() => {
      delete this._haTimers[key];
      this._runHaValidate(ruleId, idx);
    }, delay);
  }

  // Validate one card now. The result is dropped when the card no longer
  // holds the same condition (deleted, moved, draft discarded or reset).
  _runHaValidate(ruleId, idx) {
    const key = ruleId + ":" + idx;
    const cond = this._haCond(ruleId, idx);
    if (!cond) return Promise.resolve();
    const p = cond.params;
    const req = (p.ui || "form") === "yaml" ? { yaml: p.yaml || "" } : { config: p.config || null };
    const job = (async () => {
      try {
        const res = await this._ws("cover_automatic/condition/validate", req);
        if (!res || this._haCond(ruleId, idx) !== cond) return;
        (this._haLive = this._haLive || {})[key] = res;
        // A newer edit is already queued for validation otherwise.
        if (req.yaml !== undefined && p.yaml === req.yaml) p.config = res.config || null;
        this._refreshHaStatusBox(ruleId, idx);
        this._refreshCondPreview();
      } catch (e) {
        console.error(e);
        // Show the failure instead of "Checking…" forever
        if (this._haCond(ruleId, idx) !== cond) return;
        (this._haLive = this._haLive || {})[key] = this._haRequestError(e);
        this._refreshHaStatusBox(ruleId, idx);
      }
    })();
    this._haInflight = this._haInflight || {};
    this._haInflight[key] = job;
    job.finally(() => { if (this._haInflight[key] === job) delete this._haInflight[key]; });
    return job;
  }

  // Run pending (debounced) validations of a rule right away and wait for
  // all running ones, so params.config matches params.yaml before a save.
  async _flushHaValidations(ruleId = null) {
    const pre = ruleId != null ? ruleId + ":" : "";
    const jobs = [];
    for (const [key, t] of Object.entries(this._haTimers || {})) {
      if (pre && !key.startsWith(pre)) continue;
      clearTimeout(t);
      delete this._haTimers[key];
      const sep = key.lastIndexOf(":");
      jobs.push(this._runHaValidate(key.slice(0, sep), parseInt(key.slice(sep + 1), 10)));
    }
    for (const [key, job] of Object.entries(this._haInflight || {})) {
      if (!pre || key.startsWith(pre)) jobs.push(job);
    }
    await Promise.all(jobs.map(j => Promise.resolve(j).catch(() => {})));
  }

  // Drop pending validations of a rule (structural change: indices shift).
  _cancelHaTimers(ruleId) {
    const pre = ruleId + ":";
    for (const [key, t] of Object.entries(this._haTimers || {})) {
      if (!key.startsWith(pre)) continue;
      clearTimeout(t);
      delete this._haTimers[key];
    }
  }

  // Live status of a validation call that failed (connection, backend error)
  _haRequestError(e) {
    return { valid: false, error_code: "request", error: (e && (e.message || e.code)) ? String(e.message || e.code) : "" };
  }

  async _onHaUi(el) {
    const ruleId = el.dataset.rule, idx = parseInt(el.dataset.idx, 10);
    const cond = this._haCond(ruleId, idx);
    if (!cond) return;
    const mode = el.dataset.mode;
    const p = cond.params;
    if ((p.ui || "form") === mode) return;
    if (mode === "yaml") {
      // Render the current config as YAML (server-side dump)
      try {
        const res = await this._ws("cover_automatic/condition/validate", { config: p.config || null });
        if (this._haCond(ruleId, idx) !== cond) return;
        p.yaml = res && res.yaml ? res.yaml : (p.yaml || "");
        (this._haLive = this._haLive || {})[ruleId + ":" + idx] = res;
      } catch (e) {
        // Stay in the form: an outdated YAML text would replace the condition
        console.error(e);
        if (this._haCond(ruleId, idx) !== cond) return;
        (this._haLive = this._haLive || {})[ruleId + ":" + idx] = this._haRequestError(e);
        this._refreshHaStatusBox(ruleId, idx);
        this._showError(e);
        return;
      }
    } else {
      // Only switch when the form can represent the YAML (else a notice shows)
      if (p.yaml && p.yaml.trim()) {
        try {
          const res = await this._ws("cover_automatic/condition/validate", { yaml: p.yaml });
          if (this._haCond(ruleId, idx) !== cond) return;
          if (res && res.config) p.config = res.config;
          (this._haLive = this._haLive || {})[ruleId + ":" + idx] = res;
        } catch (e) {
          // Stay in YAML: the form would show the config of the old text
          console.error(e);
          if (this._haCond(ruleId, idx) !== cond) return;
          (this._haLive = this._haLive || {})[ruleId + ":" + idx] = this._haRequestError(e);
          this._refreshHaStatusBox(ruleId, idx);
          this._showError(e);
          return;
        }
      }
    }
    p.ui = mode;
    this._rerenderCondCard(ruleId, idx);
  }

  _onHaFormChange(el, isInputEvent) {
    const ruleId = el.dataset.rule, idx = parseInt(el.dataset.idx, 10);
    const cond = this._haCond(ruleId, idx);
    if (!cond) return;
    const p = cond.params;
    const m = this._haFormModel(p.config, p.op) || this._haFormModel(this._haDefaultConfig("state"));
    const field = el.dataset.field;
    let structural = false;
    const toNum = (v) => (v === "" || v == null ? null : Number(v));
    switch (field) {
      case "kind": {
        const next = this._haFormModel(this._haDefaultConfig(el.value));
        next.entity = m.entity;
        m.above = undefined; m.below = undefined;
        Object.assign(m, next);
        structural = true;
        break;
      }
      case "entity":
        if (isInputEvent) return; // wait for the value to be committed (change)
        m.entity = el.value.trim();
        m.attribute = "";
        if (m.kind === "state") m.states = [];
        structural = true;
        break;
      case "attribute":
        m.attribute = el.value;
        if (m.kind === "state") m.states = [];
        structural = true;
        break;
      case "negate":
        m.negate = el.value === "1";
        structural = true;
        break;
      case "for":
        m.forMinutes = toNum(el.value);
        break;
      case "operator":
        m.operator = el.value;
        structural = true;
        break;
      case "above":
        m.above = toNum(el.value);
        break;
      case "below":
        m.below = toNum(el.value);
        break;
      default:
        return;
    }
    p.config = this._haFormToConfig(m);
    p.op = m.kind === "numeric" ? m.operator : undefined;
    p.yaml = ""; // regenerated from config when switching to YAML
    if (structural) this._rerenderCondCard(ruleId, idx);
    else this._refreshHaStatusBox(ruleId, idx);
    this._scheduleHaValidate(ruleId, idx);
  }

  _onHaStateToggle(el, forceAdd = null) {
    const ruleId = el.dataset.rule, idx = parseInt(el.dataset.idx, 10);
    const cond = this._haCond(ruleId, idx);
    if (!cond) return;
    const m = this._haFormModel(cond.params.config);
    if (!m || m.kind !== "state") return;
    const val = forceAdd != null ? forceAdd : el.dataset.val;
    if (!val) return;
    if (m.states.includes(val)) {
      if (forceAdd == null) m.states = m.states.filter(s => s !== val);
    } else {
      m.states.push(val);
    }
    cond.params.config = this._haFormToConfig(m);
    cond.params.yaml = "";
    this._rerenderCondCard(ruleId, idx);
    this._scheduleHaValidate(ruleId, idx);
  }

  _onHaStateAdd(el) {
    const key = el.dataset.rule + ":" + el.dataset.idx;
    const input = this.shadowRoot.querySelector(`[data-ha-other="${CSS.escape(key)}"]`);
    const val = input ? input.value.trim() : "";
    if (val) this._onHaStateToggle(el, val);
  }

  _onHaYamlInput(el) {
    const ruleId = el.dataset.rule, idx = parseInt(el.dataset.idx, 10);
    const cond = this._haCond(ruleId, idx);
    if (!cond) return;
    cond.params.yaml = el.value;
    (this._haLive = this._haLive || {})[ruleId + ":" + idx] = { pending: true };
    this._refreshHaStatusBox(ruleId, idx);
    this._scheduleHaValidate(ruleId, idx, 600);
  }
};

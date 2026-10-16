// CoverAutomatic panel -- Rule conditions: groups, cards, parameters, live preview.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).
import { MAX_CONDITION_GROUPS, CONDITION_PARAMS, CONDITION_MENU, CONTEXT_DEPENDENT_TYPES } from "./constants.js";

export const ConditionsMixin = (Base) => class extends Base {
  // Operators per condition group and number of groups of a rule.
  _ruleGroups(rule) {
    const ops = Array.isArray(rule.group_operators) && rule.group_operators.length
      ? [...rule.group_operators] : [rule.condition_operator === "or" ? "or" : "and"];
    let n = ops.length;
    for (const c of rule.conditions || []) n = Math.max(n, (parseInt(c.group, 10) || 0) + 1);
    while (ops.length < n) ops.push("and");
    return { ops, n, between: rule.condition_operator === "or" ? "or" : "and" };
  }

  _opSelect(attrs, value) {
    return `<select ${attrs}>
        <option value="and"${value === "and" ? " selected" : ""}>${this._t("rule_operator_and")}</option>
        <option value="or"${value === "or" ? " selected" : ""}>${this._t("rule_operator_or")}</option>
      </select>`;
  }

  _renderConditionAdd(rule, group) {
    return `<div class="rule-condition-add">
      <select class="rule-condition-type-select" data-action="rule-add-condition-type" data-rule="${this._esc(rule.id)}" data-group="${group}">
        <option value="">${this._t("rule_add_condition")}...</option>
        ${CONDITION_MENU.map(g => `<optgroup label="${this._esc(this._t(g.label))}">${g.items.map(it => `<option value="${it.value}">${this._esc(this._t(it.label))}</option>`).join("")}</optgroup>`).join("")}
      </select>
    </div>`;
  }

  // Compact up/down buttons (reordering conditions and groups).
  _moveBtns(attrs, actUp, actDown, tipUp, tipDown, firstPos, lastPos) {
    return `<span class="move-btns">
      <button class="btn-icon btn-move" data-action="${actUp}" ${attrs} title="${this._esc(this._t(tipUp))}" aria-label="${this._esc(this._t(tipUp))}"${firstPos ? " disabled" : ""}>&#9650;</button>
      <button class="btn-icon btn-move" data-action="${actDown}" ${attrs} title="${this._esc(this._t(tipDown))}" aria-label="${this._esc(this._t(tipDown))}"${lastPos ? " disabled" : ""}>&#9660;</button>
    </span>`;
  }

  // Indices (in rule.conditions) of the conditions of one group, in order.
  _groupCondIndices(conditions, group) {
    const out = [];
    (conditions || []).forEach((c, i) => { if ((parseInt(c.group, 10) || 0) === group) out.push(i); });
    return out;
  }

  _renderConditionGroups(rule) {
    const rid = this._esc(rule.id);
    const { ops, n, between } = this._ruleGroups(rule);
    const conds = rule.conditions || [];
    let html = "";
    if (n === 1) {
      html += `<div class="rule-inline-row">
        <span class="rule-inline-label rule-inline-label-auto">${this._t("rule_operator")}${this._hintToggle(rule.id, "rule_operator_hint")}</span>
        <div class="rule-inline-select">${this._opSelect(`data-action="rule-group-op" data-rule="${rid}" data-group="0"`, ops[0])}</div>
        ${this._hintPanel(rule.id, "rule_operator_hint")}
      </div>`;
      if (conds.length > 0) {
        for (const [i] of conds.entries()) html += this._renderConditionCard(rule, i, 1);
      } else {
        html += `<div class="rule-no-conditions">${this._t("rule_no_conditions")}</div>`;
      }
      html += this._renderConditionAdd(rule, 0);
    } else {
      html += `<div class="rule-inline-row">
        <span class="rule-inline-label rule-inline-label-auto">${this._t("rule_groups_operator")}${this._hintToggle(rule.id, "rule_groups_hint")}</span>
        <div class="rule-inline-select">${this._opSelect(`data-action="rule-field" data-id="${rid}" data-field="condition_operator"`, between)}</div>
        ${this._hintPanel(rule.id, "rule_groups_hint")}
      </div>`;
      for (let g = 0; g < n; g++) {
        if (g > 0) html += `<div class="cond-group-sep" data-group-sep="${rid}">${this._t(between === "or" ? "rule_op_short_or" : "rule_op_short_and")}</div>`;
        html += `<div class="cond-group">
          <div class="cond-group-head">
            <span class="cond-group-title">${this._t("rule_group")} ${g + 1}</span>
            <span class="cond-group-op"><span>${this._t("rule_group_joined_by")}</span>
              ${this._opSelect(`data-action="rule-group-op" data-rule="${rid}" data-group="${g}"`, ops[g])}</span>
            <span class="cond-preview cond-group-preview" data-group-preview="${g}"></span>
            ${this._moveBtns(`data-rule="${rid}" data-group="${g}"`, "rule-group-up", "rule-group-down", "rule_group_up", "rule_group_down", g === 0, g === n - 1)}
            <button class="btn-icon" data-action="rule-group-delete" data-rule="${rid}" data-group="${g}" title="${this._esc(this._t("rule_group_delete"))}">&#10005;</button>
          </div>`;
        let count = 0;
        for (const [i, c] of conds.entries()) {
          if ((parseInt(c.group, 10) || 0) !== g) continue;
          html += this._renderConditionCard(rule, i, n);
          count++;
        }
        if (!count) html += `<div class="rule-no-conditions">${this._t("rule_group_empty")}</div>`;
        html += this._renderConditionAdd(rule, g);
        html += '</div>';
      }
    }
    if (n < MAX_CONDITION_GROUPS) {
      html += `<div class="rule-inline-row cond-group-add-row">
        <button class="btn btn-secondary btn-sm cond-group-add" data-action="rule-group-add" data-rule="${rid}">+ ${this._t("rule_group_add")}</button>
        ${n === 1 ? this._hintToggle(rule.id, "rule_group_add_hint") + this._hintPanel(rule.id, "rule_group_add_hint") : ""}
      </div>`;
    }
    return html;
  }

  // Collapsed condition cards (per rule and condition index, kept while the panel is open).
  _isCondCollapsed(ruleId, idx) {
    return !!(this._collapsedConds && this._collapsedConds.has(ruleId + ":" + idx));
  }

  _setCondCollapsed(ruleId, idx, collapsed) {
    if (!this._collapsedConds) this._collapsedConds = new Set();
    const key = ruleId + ":" + idx;
    if (collapsed) this._collapsedConds.add(key); else this._collapsedConds.delete(key);
    const root = this.shadowRoot;
    const card = root && root.querySelector(`.condition-card[data-cond-card="${CSS.escape(key)}"]`);
    if (!card) return;
    card.classList.toggle("collapsed", collapsed);
    const chev = card.querySelector(".cond-chevron");
    if (chev) {
      chev.setAttribute("aria-expanded", collapsed ? "false" : "true");
      chev.title = this._t(collapsed ? "cond_expand" : "cond_collapse");
    }
    // Refresh the one-line summary with the values edited meanwhile.
    const rule = this._edRule(ruleId);
    const sum = card.querySelector(".cond-summary");
    if (sum && rule && rule.conditions && rule.conditions[idx]) sum.textContent = this._condSummary(rule.conditions[idx]);
  }

  _onCondCollapseAll(ruleId) {
    const rule = this._edRule(ruleId);
    if (!rule || !rule.conditions) return;
    const anyOpen = rule.conditions.some((_, i) => !this._isCondCollapsed(ruleId, i));
    rule.conditions.forEach((_, i) => this._setCondCollapsed(ruleId, i, anyOpen));
    const btn = this.shadowRoot && this.shadowRoot.querySelector(`[data-action="rule-cond-collapse-all"][data-rule="${CSS.escape(ruleId)}"]`);
    if (btn) btn.textContent = this._t(anyOpen ? "cond_expand_all" : "cond_collapse_all");
  }

  // Index shift after a condition is deleted (collapsed state follows its card).
  _shiftCollapsedConds(ruleId, removedIdx) {
    if (!this._collapsedConds) return;
    const next = new Set();
    for (const key of this._collapsedConds) {
      const sep = key.lastIndexOf(":");
      const rid = key.slice(0, sep);
      const i = parseInt(key.slice(sep + 1), 10);
      if (rid !== ruleId) { next.add(key); continue; }
      if (i === removedIdx) continue;
      next.add(rid + ":" + (i > removedIdx ? i - 1 : i));
    }
    this._collapsedConds = next;
  }

  // One-line summary of a condition's settings, shown when it is collapsed.
  _condSummary(c) {
    const p = c.params || {};
    const off = v => { const n = Number(v) || 0; return n === 0 ? "" : (n > 0 ? "+" : "−") + Math.abs(n) + " min"; };
    switch (c.type) {
      case "ha_condition": return this._condChipLabel(c);
      case "sun_elevation_above": return "> " + (p.elevation ?? p.value ?? "") + "°";
      case "sun_elevation_below": return "< " + (p.elevation ?? p.value ?? "") + "°";
      case "temperature_above": return "> " + (p.temperature ?? p.value ?? "") + " °C";
      case "temperature_below": return "< " + (p.temperature ?? p.value ?? "") + " °C";
      case "temperature_comfort": return this._optionLabel("mode", p.mode || "cooling");
      case "outdoor_vs_indoor": {
        const d = Math.abs(Number(p.delta) || 0);
        return this._optionLabel("operator", p.operator === "warmer" ? "warmer" : "cooler") + (d ? " (≥ " + d + " °C)" : "");
      }
      case "time_between": return (p.start_time || "") + " – " + (p.end_time || "");
      case "state_is": return (p.entity_id ? this._haEntityName(p.entity_id) : "?") + " = " + (p.state ?? "");
      case "numeric_state": return (p.entity_id ? this._haEntityName(p.entity_id) : "?") + (p.operator === "below" ? " < " : " > ") + (p.value ?? "");
      case "weather_is": {
        const w = Array.isArray(p.weather) ? p.weather : (p.weather ? [p.weather] : (p.states || []));
        return w.map(v => this._optionLabel("weather", v)).join(", ");
      }
      case "day_of_week": return (p.days || []).map(d => this._i18nOr("day_" + d, d)).join(" ");
      case "workday": return this._optionLabel("state", p.state || "on");
      default:
        return c.type && c.type.startsWith("time_") ? off(p.offset) : "";
    }
  }

  _renderConditionCard(rule, idx, groupCount = null) {
    const cond = rule.conditions[idx];
    const nGroups = groupCount ?? this._ruleGroups(rule).n;
    const negated = !!cond.negate;
    const cGroup = parseInt(cond.group, 10) || 0;
    const groupMove = nGroups > 1
      ? `<select class="cond-group-move" data-action="rule-cond-group" data-rule="${this._esc(rule.id)}" data-idx="${idx}" title="${this._esc(this._t("rule_cond_move"))}">${Array.from({ length: nGroups }, (_, g) => `<option value="${g}"${g === cGroup ? " selected" : ""}>${this._t("rule_group")} ${g + 1}</option>`).join("")}</select>`
      : "";
    const siblings = this._groupCondIndices(rule.conditions, cGroup);
    const pos = siblings.indexOf(idx);
    const moveBtns = this._moveBtns(`data-rule="${this._esc(rule.id)}" data-idx="${idx}"`, "rule-cond-up", "rule-cond-down",
      "rule_cond_up", "rule_cond_down", pos <= 0, pos === siblings.length - 1);
    const notBtn = `<button class="cond-not${negated ? " active" : ""}" data-action="rule-cond-negate" data-rule="${this._esc(rule.id)}" data-idx="${idx}" title="${this._esc(this._t("rule_cond_not_hint"))}">${this._t("rule_cond_not")}</button>`;
    const paramDefs = CONDITION_PARAMS[cond.type] || [];

    const isContextCond = CONTEXT_DEPENDENT_TYPES.includes(cond.type);
    const previewCell = isContextCond
      ? `<span class="cond-preview cond-preview-context">${this._t("cond_preview_context")}</span>`
      : `<span class="cond-preview" data-cond-preview="${idx}"></span>`;
    const isHa = cond.type === "ha_condition";
    const title = isHa ? this._haCondTitle(cond) : this._t("cond_" + cond.type);
    const collapsed = this._isCondCollapsed(rule.id, idx);
    let html = `<div class="condition-card${isHa ? " ha-card" : ""}${negated ? " negated" : ""}${collapsed ? " collapsed" : ""}" data-cond-card="${this._esc(rule.id)}:${idx}">
      <div class="cond-header">
        <span class="cond-head-left">
          <button class="cond-chevron" data-action="rule-cond-collapse" data-rule="${this._esc(rule.id)}" data-idx="${idx}" title="${this._esc(this._t(collapsed ? "cond_expand" : "cond_collapse"))}" aria-expanded="${collapsed ? "false" : "true"}">&#9662;</button>
          ${notBtn}
          <span class="cond-type" data-action="rule-cond-collapse" data-rule="${this._esc(rule.id)}" data-idx="${idx}">${this._esc(title)}</span>
          <span class="cond-summary" data-cond-summary="${idx}">${this._esc(this._condSummary(cond))}</span>
          ${previewCell}
        </span>
        <span class="cond-head-right">
          ${groupMove}
          ${moveBtns}
          <button class="btn-icon" data-action="rule-delete-condition" data-rule="${this._esc(rule.id)}" data-idx="${idx}" title="${this._t("delete")}">&#10005;</button>
        </span>
      </div>`;

    if (isHa) {
      html += this._renderHaConditionBody(rule, idx, cond);
      return html + '</div>';
    }

    // Legacy entity conditions can be converted to the richer HA condition
    const legacyHyst = cond.type === "numeric_state" && Number((cond.params || {}).hysteresis) > 0;
    if ((cond.type === "state_is" || cond.type === "numeric_state") && !legacyHyst) {
      html += `<div class="ha-convert"><button type="button" class="btn btn-secondary btn-small" data-action="cond-convert" data-rule="${this._esc(rule.id)}" data-idx="${idx}">${this._t("cond_convert")}</button>
        <span class="ha-help">${this._esc(this._t("cond_convert_hint"))}</span></div>`;
    }

    if (paramDefs.length > 0) {
      html += '<div class="cond-params">';
      for (const p of paramDefs) {
        const val = (cond.params && cond.params[p.key] != null) ? cond.params[p.key] : p.default;
        html += '<div class="form-group">';
        html += `<label>${this._t("param_" + p.key)}</label>`;
        if (p.type === "select") {
          html += `<select data-action="cond-param" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}">`;
          for (const opt of p.options) {
            const optLabel = this._t("opt_" + opt);
            html += `<option value="${opt}"${val === opt ? " selected" : ""}>${optLabel}</option>`;
          }
          html += '</select>';
        } else if (p.type === "multiselect") {
          const selected = Array.isArray(val) ? val : (val ? [val] : p.default);
          html += `<div class="day-select" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}">`;
          for (const opt of p.options) {
            const active = selected.includes(opt);
            html += `<button type="button" class="day-btn${active ? " selected" : ""}" data-action="multiselect-toggle" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}" data-val="${this._esc(opt)}">${this._esc(this._optionLabel(p.key, opt))}</button>`;
          }
          html += '</div>';
        } else if (p.type === "time") {
          html += `<input type="time" value="${this._esc(String(val))}" data-action="cond-param" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}">`;
        } else if (p.type === "dayselect") {
          const ALL_DAYS = ["mon","tue","wed","thu","fri","sat","sun"];
          const selected = Array.isArray(val) ? val : p.default;
          html += `<div class="day-select" data-action="cond-param" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}">`;
          for (const d of ALL_DAYS) {
            const active = selected.includes(d);
            html += `<button type="button" class="day-btn${active ? " selected" : ""}" data-action="day-toggle" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}" data-day="${d}">${this._t("day_" + d)}</button>`;
          }
          html += '</div>';
        } else if (p.type === "number") {
          html += `<input type="number" value="${this._num(val)}" step="${p.step ? p.step : "any"}" data-action="cond-param" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}">`;
        } else if (p.type === "entity") {
          html += this._renderCondEntitySelect(rule, idx, p.key, val);
        } else {
          html += `<input type="text" value="${this._esc(String(val))}" data-action="cond-param" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${p.key}">`;
        }
        html += '</div>';
      }
      html += '</div>';
    }

    // Sun time conditions: window covered and complementary condition
    if (/^time_(after|before)_(sunrise|sunset|dawn|dusk)$/.test(cond.type || "")) {
      const sunHint = this._t("cond_" + cond.type + "_hint");
      if (sunHint !== "cond_" + cond.type + "_hint") {
        const other = cond.type.startsWith("time_after_") ? cond.type.replace("time_after_", "time_before_") : cond.type.replace("time_before_", "time_after_");
        html += `<div class="ha-help cond-type-hint">${this._esc(sunHint.replace("{other}", this._t("cond_" + other)))}</div>`;
      }
    }

    html += '</div>';
    return html;
  }

  // Convert a legacy state_is / numeric_state condition into an ha_condition.
  _onCondConvert(el) {
    const ruleId = el.dataset.rule, idx = parseInt(el.dataset.idx, 10);
    const rule = this._edRule(ruleId);
    const cond = rule && rule.conditions ? rule.conditions[idx] : null;
    if (!cond) return;
    const p = cond.params || {};
    const entity = p.entity_id || p.entity || "";
    let config;
    if (cond.type === "state_is") {
      config = { condition: "state", entity_id: entity, state: p.state != null ? String(p.state) : [] };
    } else if (cond.type === "numeric_state") {
      config = { condition: "numeric_state", entity_id: entity };
      const v = Number(p.value);
      if (Number.isFinite(v)) {
        if (String(p.operator || "above") === "below") config.below = v; else config.above = v;
      }
    } else {
      return;
    }
    const prev = rule.conditions[idx] || {};
    rule.conditions[idx] = { type: "ha_condition", params: { ui: "form", config, yaml: "" }, group: prev.group || 0, negate: !!prev.negate };
    this._rerenderCondCard(ruleId, idx);
    this._scheduleHaValidate(ruleId, idx, 0);
  }

  // Readable summary of a condition for the collapsed rule chips.
  _condChipLabel(c) {
    if (c.type !== "ha_condition") return this._t("cond_" + c.type);
    const cfg = c.params && c.params.config;
    const m = this._haFormModel(cfg, c.params && c.params.op);
    const fill = (tpl, values) => tpl.replace(/\{(\w+)\}/g, (mm, n) => (values[n] != null ? String(values[n]) : mm));
    if (m && m.entity) {
      const stateObj = this._hass?.states ? this._hass.states[m.entity] : null;
      let name = this._haEntityName(m.entity);
      if (m.attribute) name += " · " + this._haAttributeLabel(stateObj, m.attribute);
      if (m.kind === "state") {
        const states = m.states.map(s => "« " + this._haStateLabel(stateObj, m.attribute, s) + " »").join(this._t("ha_chip_or"));
        let txt = fill(this._t(m.negate ? "ha_chip_is_not" : "ha_chip_is"), { entity: name, states });
        if (!m.negate && m.forMinutes) txt += fill(this._t("ha_chip_for"), { min: Math.round(m.forMinutes * 100) / 100 });
        return txt;
      }
      if (m.operator === "between") return fill(this._t("ha_chip_between"), { entity: name, min: m.above, max: m.below });
      return fill(this._t(m.operator === "below" ? "ha_chip_below" : "ha_chip_above"), { entity: name, value: m.operator === "below" ? m.below : m.above });
    }
    if (cfg && cfg.condition) {
      let type = this._i18nOr("ha_ctype_" + cfg.condition, String(cfg.condition));
      if (Array.isArray(cfg.conditions)) type += " (" + cfg.conditions.length + ")";
      return fill(this._t("ha_chip_other"), { type });
    }
    return this._t("cond_ha_condition");
  }

  // Entity picker for rule conditions (state_is). Not domain-restricted: any
  // entity can be checked. A plain <select> grows unsearchably long, so this
  // is a text input backed by a <datalist> -- typing filters suggestions by
  // friendly name or entity id, and free text stays allowed (entities that are
  // not loaded yet, future entities).
  _renderCondEntitySelect(rule, idx, key, currentValue) {
    const attrs = `data-action="cond-param" data-rule="${this._esc(rule.id)}" data-idx="${idx}" data-key="${this._esc(key)}"`;
    const cur = currentValue || "";
    if (!this._hass || !this._hass.states) {
      return `<input type="text" value="${this._esc(String(cur))}" ${attrs}>`;
    }
    const listId = `ca-ent-${this._esc(rule.id)}-${idx}`;
    const entities = Object.values(this._hass.states)
      .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id));
    let html = `<input type="text" list="${listId}" value="${this._esc(String(cur))}" placeholder="${this._t("param_entity_search")}" autocomplete="off" ${attrs}>`;
    html += `<datalist id="${listId}">`;
    for (const e of entities) {
      const name = e.attributes.friendly_name || e.entity_id;
      // value is the entity id (what gets stored); label shows the friendly name
      html += `<option value="${this._esc(e.entity_id)}">${this._esc(name)}</option>`;
    }
    html += "</datalist>";
    return html;
  }

  /* ---------- Rule editor: live condition preview ---------- */
  _startCondPreview() {
    this._stopCondPreview();
    this._refreshCondPreview();
    this._condPreviewTimer = setInterval(() => this._refreshCondPreview(), 10000);
  }

  _stopCondPreview() {
    if (this._condPreviewTimer) {
      clearInterval(this._condPreviewTimer);
      this._condPreviewTimer = null;
    }
  }

  async _refreshCondPreview() {
    if (!this._config || this._activeTab !== "rules" || !this._expandedRule) {
      this._stopCondPreview();
      return;
    }
    const ruleId = this._expandedRule;
    const rule0 = this._edRule(ruleId);
    if (!rule0 || !rule0.conditions || rule0.conditions.length === 0) return;
    const conditions = rule0.conditions.map(c => ({ type: c.type, params: c.params || {}, group: parseInt(c.group, 10) || 0, negate: !!c.negate }));
    // Only the latest request may paint (responses can arrive out of order,
    // and structural changes bump the sequence to void older ones).
    const seq = ++this._previewSeq;
    let result;
    try {
      result = await this._ws("cover_automatic/rule/preview_conditions", { conditions });
    } catch (e) { return; }
    if (seq !== this._previewSeq) return;
    // The editor may have collapsed or switched tabs during the await.
    if (!result || !Array.isArray(result.results) || this._activeTab !== "rules" || this._expandedRule !== ruleId) return;
    // Re-read the rule: its conditions may have changed meanwhile.
    const rule = this._edRule(ruleId);
    if (!rule || !rule.conditions || rule.conditions.length !== result.results.length
      || rule.conditions.some((c, i) => c.type !== conditions[i].type)) return;
    const root = this.shadowRoot;
    if (!root) return;
    result.results.forEach((res, idx) => {
      const el = root.querySelector('.cond-preview[data-cond-preview="' + idx + '"]');
      if (el) this._applyCondPreview(el, res);
    });
    // Group results (only when every condition of the group is evaluable)
    const { ops } = this._ruleGroups(rule);
    root.querySelectorAll(".cond-group-preview[data-group-preview]").forEach(el => {
      const g = parseInt(el.dataset.groupPreview, 10);
      const res = result.results.filter((_, i) => (parseInt(rule.conditions[i]?.group, 10) || 0) === g);
      if (!res.length || res.some(r => !r || r.evaluable === false)) { el.className = "cond-preview cond-group-preview"; el.textContent = ""; return; }
      const matched = ops[g] === "or" ? res.some(r => r.matched) : res.every(r => r.matched);
      this._applyCondPreview(el, { evaluable: true, matched, actual: null });
      el.classList.add("cond-group-preview");
    });
  }

  _applyCondPreview(el, res) {
    if (!res || res.evaluable === false) {
      el.className = "cond-preview cond-preview-context";
      el.textContent = this._t("cond_preview_context");
      return;
    }
    const matched = !!res.matched;
    el.className = "cond-preview " + (matched ? "cond-preview-on" : "cond-preview-off");
    const label = this._t(matched ? "cond_preview_active" : "cond_preview_inactive");
    const actual = this._formatCondActual(res);
    // DOM API (not innerHTML) to satisfy the security hook on live updates.
    el.textContent = "";
    const dot = document.createElement("span");
    dot.className = "cond-preview-dot";
    el.appendChild(dot);
    const txt = document.createElement("span");
    txt.textContent = actual ? (label + " · " + actual) : label;
    el.appendChild(txt);
  }

  _formatCondActual(res) {
    const v = res.actual;
    if (v == null) return "";
    switch (res.kind) {
      case "temp": return v + " °C";
      case "elevation": return v + "°";
      case "weather": return this._i18nOr("weather_" + String(v).replace(/-/g, "_"), String(v));
      case "day": return this._i18nOr("day_" + v, String(v));
      case "workday": return this._i18nOr("opt_" + v, String(v));
      case "ha_reading": {
        const stateObj = this._hass?.states ? this._hass.states[v.entity_id] : null;
        return this._haStateLabel(stateObj, v.attribute, v.value);
      }
      default: return String(v);
    }
  }

  _onRuleCondNegate(btn) {
    const rule = this._edRule(btn.dataset.rule);
    const idx = parseInt(btn.dataset.idx, 10);
    const cond = rule && rule.conditions ? rule.conditions[idx] : null;
    if (!cond) return;
    cond.negate = !cond.negate;
    btn.classList.toggle("active", cond.negate);
    btn.closest(".condition-card")?.classList.toggle("negated", cond.negate);
    this._refreshCondPreview();
  }

  async _onRuleGroupAdd(ruleId) {
    await this._flushHaValidations(ruleId);
    const rule = this._edRule(ruleId);
    if (!rule) return;
    const { ops, n, between } = this._ruleGroups(rule);
    if (n >= MAX_CONDITION_GROUPS) return;
    // From one group to two: the groups are joined by the opposite operator,
    // e.g. (A or B) and (C or D), and the new group copies the first one's.
    const nextBetween = n === 1 ? (ops[0] === "or" ? "and" : "or") : between;
    await this._saveRuleStructure(ruleId, null, { ops: [...ops, ops[n - 1]], between: nextBetween });
  }

  _onRuleGroupDelete(ruleId, group) {
    const rule = this._edRule(ruleId);
    const g = parseInt(group, 10);
    if (!rule || !Number.isFinite(g)) return;
    const inGroup = (c) => (parseInt(c.group, 10) || 0) === g;
    // Built from the draft when confirmed: the confirm dialog re-renders the
    // editor, the draft keeps every unsaved edit meanwhile.
    const run = async () => {
      await this._flushHaValidations(ruleId);
      const r = this._edRule(ruleId);
      if (!r) return false;
      const { ops, between } = this._ruleGroups(r);
      const conds = (r.conditions || [])
        .filter(c => !inGroup(c))
        .map(c => { const cg = parseInt(c.group, 10) || 0; return { ...c, group: cg > g ? cg - 1 : cg }; });
      const nextOps = ops.filter((_, i) => i !== g);
      // Old index -> new index of the kept conditions
      const kept = (r.conditions || []).map((c, i) => (inGroup(c) ? -1 : i)).filter(i => i >= 0);
      return this._saveRuleStructure(ruleId, conds, { ops: nextOps.length ? nextOps : ["and"], between },
        (i) => { const k = kept.indexOf(i); return k < 0 ? null : k; });
    };
    const removed = (rule.conditions || []).filter(inGroup).length;
    if (removed > 0) this._showConfirm(this._t("rule_group_delete_confirm"), run);
    else run();
  }

  async _onRuleCondMove(ruleId, idx, group, el = null) {
    await this._flushHaValidations(ruleId);
    const rule = this._edRule(ruleId);
    if (!rule || !rule.conditions || !rule.conditions[idx]) return;
    const prevGroup = parseInt(rule.conditions[idx].group, 10) || 0;
    const conds = rule.conditions.map((c, i) => (i === idx ? { ...c, group } : c));
    const ok = await this._saveRuleStructure(ruleId, conds, null, (i) => i);
    if (!ok && el && el.isConnected) el.value = String(prevGroup);
  }

  // Move a condition up (dir -1) or down (dir 1) within its group: it swaps
  // places with the previous/next condition of the same group; the other
  // conditions keep their positions.
  async _onRuleCondReorder(ruleId, idx, dir) {
    await this._flushHaValidations(ruleId);
    const rule = this._edRule(ruleId);
    if (!rule || !rule.conditions || !rule.conditions[idx]) return;
    const siblings = this._groupCondIndices(rule.conditions, parseInt(rule.conditions[idx].group, 10) || 0);
    const pos = siblings.indexOf(idx);
    const other = siblings[pos + dir];
    if (pos < 0 || other === undefined) return;
    const perm = rule.conditions.map((_, i) => (i === idx ? other : i === other ? idx : i));
    const conds = perm.map(i => rule.conditions[i]);
    await this._saveRuleStructure(ruleId, conds, null, (i) => perm.indexOf(i));
  }

  // Move a whole group up/down: swaps its index (conditions' group and
  // group_operators entry) with the neighbouring group.
  async _onRuleGroupReorder(ruleId, g, dir) {
    await this._flushHaValidations(ruleId);
    const rule = this._edRule(ruleId);
    if (!rule || !Number.isFinite(g)) return;
    const { ops, n, between } = this._ruleGroups(rule);
    const h = g + dir;
    if (g < 0 || g >= n || h < 0 || h >= n) return;
    const conds = (rule.conditions || []).map(c => {
      const cg = parseInt(c.group, 10) || 0;
      return cg === g ? { ...c, group: h } : cg === h ? { ...c, group: g } : c;
    });
    const nextOps = [...ops];
    [nextOps[g], nextOps[h]] = [nextOps[h], nextOps[g]];
    // Flat condition order is unchanged: per-index state stays valid.
    await this._saveRuleStructure(ruleId, conds, { ops: nextOps, between }, (i) => i);
  }

  async _onRuleAddCondition(ruleId, condType, group = 0, el = null) {
    if (!condType) return;
    await this._flushHaValidations(ruleId);
    const rule = this._edRule(ruleId);
    if (!rule) { if (el) el.value = ""; return; }
    let newCond;
    if (condType.startsWith("ha:")) {
      const kind = condType.slice(3);
      newCond = kind === "yaml"
        ? { type: "ha_condition", params: { ui: "yaml", config: null, yaml: "" } }
        : { type: "ha_condition", params: { ui: "form", config: this._haDefaultConfig(kind), yaml: "" } };
    } else {
      const paramDefs = CONDITION_PARAMS[condType] || [];
      const params = {};
      for (const p of paramDefs) params[p.key] = p.default;
      newCond = { type: condType, params: params };
    }
    newCond.group = group;
    newCond.negate = false;
    const nextConditions = [...(rule.conditions || []), newCond];
    const ok = await this._saveRuleStructure(ruleId, nextConditions, null, (i) => i);
    if (!ok && el && el.isConnected) el.value = "";
  }

  async _onRuleDeleteCondition(ruleId, idx) {
    await this._flushHaValidations(ruleId);
    const rule = this._edRule(ruleId);
    if (!rule || !rule.conditions) return;
    const idxInt = parseInt(idx, 10);
    if (!Number.isFinite(idxInt)) return;
    const nextConditions = rule.conditions.filter((_, i) => i !== idxInt);
    await this._saveRuleStructure(ruleId, nextConditions, null,
      (i) => (i === idxInt ? null : i > idxInt ? i - 1 : i));
  }

  _updateConditionParam(el) {
    const ruleId = el.dataset.rule;
    const idx = parseInt(el.dataset.idx, 10);
    const key = el.dataset.key;
    const rule = this._edRule(ruleId);
    if (rule && rule.conditions && rule.conditions[idx]) {
      let val = el.value;
      if (el.type === "number") {
        // Empty or "-" while typing: keep the previous value, mark the field
        const n = val === "" ? NaN : Number(val);
        if (!Number.isFinite(n)) {
          this._setInputInvalid(el, this._t("input_invalid_number"));
          return;
        }
        this._setInputInvalid(el, null);
        val = n;
      }
      if (!rule.conditions[idx].params) rule.conditions[idx].params = {};
      rule.conditions[idx].params[key] = val;
    }
  }

  _onDayToggle(el) {
    const ruleId = el.dataset.rule;
    const idx = parseInt(el.dataset.idx, 10);
    const key = el.dataset.key;
    const day = el.dataset.day;
    const rule = this._edRule(ruleId);
    if (rule && rule.conditions && rule.conditions[idx]) {
      if (!rule.conditions[idx].params) rule.conditions[idx].params = {};
      let days = rule.conditions[idx].params[key];
      if (!Array.isArray(days)) days = [];
      if (days.includes(day)) {
        days = days.filter(d => d !== day);
      } else {
        days.push(day);
      }
      rule.conditions[idx].params[key] = days;
      el.classList.toggle("selected");
    }
  }

  _onMultiselectToggle(el) {
    const ruleId = el.dataset.rule;
    const idx = parseInt(el.dataset.idx, 10);
    const key = el.dataset.key;
    const val = el.dataset.val;
    const rule = this._edRule(ruleId);
    if (rule && rule.conditions && rule.conditions[idx]) {
      if (!rule.conditions[idx].params) rule.conditions[idx].params = {};
      let arr = rule.conditions[idx].params[key];
      if (!Array.isArray(arr)) arr = arr ? [arr] : [];
      if (arr.includes(val)) {
        arr = arr.filter(v => v !== val);
      } else {
        arr.push(val);
      }
      rule.conditions[idx].params[key] = arr;
      el.classList.toggle("selected");
    }
  }
};

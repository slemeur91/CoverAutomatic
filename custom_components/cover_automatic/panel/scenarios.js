// CoverAutomatic panel -- Scenarios tab.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).
import { SCENARIO_ICON_CHOICES } from "./constants.js";

export const ScenariosMixin = (Base) => class extends Base {
  /* ============================================================
   * TAB: Scenarios
   * ============================================================ */
  _renderScenarios() {
    const scenarios = this._config.scenarios || {};
    const rules = this._config.rules || {};
    const activeId = (this._config.settings || {}).active_scenario || this._config.active_scenario;
    const entries = Object.values(scenarios);

    let html = '<div class="card-grid">';

    for (const sc of entries) {
      const isActive = sc.id === activeId;
      const isEditing = this._editingScenario === sc.id;

      if (isEditing) {
        html += this._renderScenarioEditForm(sc, rules, isActive);
      } else {
        html += this._renderScenarioCard(sc, rules, isActive);
      }
    }

    // Add
    if (this._addingScenario) {
      html += this._renderScenarioAddForm();
    } else {
      html += `<button class="add-card" data-action="scenario-add-start">+ ${this._t("scenario_add")}</button>`;
    }

    html += '</div>';
    return html;
  }

  // Rules in the order of the Rules tab: highest priority first, ties broken
  // by rule id -- the same order the engine uses to pick the winning rule.
  _rulesByPriority(rules) {
    return Object.values(rules || {}).sort((a, b) =>
      // Same tie-break as the engine (plain code point order of the ids)
      ((b.priority ?? 0) - (a.priority ?? 0)) || (String(a.id) < String(b.id) ? -1 : String(a.id) > String(b.id) ? 1 : 0));
  }

  // Rules that belong to a scenario (scenario_ids null = every scenario).
  _ruleInScenario(rule, scenarioId) {
    return !Array.isArray(rule.scenario_ids) || rule.scenario_ids.includes(scenarioId);
  }

  _renderScenarioCard(sc, rules, isActive) {
    const ruleEntries = this._rulesByPriority(rules).filter(r => this._ruleInScenario(r, sc.id));
    let html = `<div class="scenario-card${isActive ? " active-scenario" : ""}">
      <div class="sc-header">
        <div class="sc-name">
          ${sc.icon ? `<ha-icon icon="${this._esc(sc.icon)}" class="scenario-card-icon"></ha-icon>` : ""}${this._esc(sc.name)}
          ${isActive ? `<span class="chip">${this._t("active")}</span>` : ""}
        </div>
        <div class="sc-actions">
          ${!isActive ? `<button class="btn btn-primary btn-sm" data-action="scenario-activate" data-id="${this._esc(sc.id)}">${this._t("activate")}</button>` : ""}
          <button class="btn btn-secondary btn-sm" data-action="scenario-edit" data-id="${this._esc(sc.id)}">${this._t("edit")}</button>
          <button class="btn btn-danger btn-sm" data-action="scenario-delete" data-id="${this._esc(sc.id)}">${this._t("delete")}</button>
        </div>
      </div>`;

    // Rules list with enabled/disabled toggles
    html += '<div class="sc-rules">';
    if (ruleEntries.length === 0) {
      html += `<div class="scenario-no-rules">${this._t(Object.keys(rules || {}).length ? "scenario_no_member_rules" : "scenario_no_rules")}</div>`;
    } else {
      for (const [ri, r] of ruleEntries.entries()) {
        const disabled = (sc.rules_disabled || []).includes(r.id);
        // A rule switched off in the Rules tab never runs, whatever the
        // scenario says: show it greyed out. Its scenario toggle stays usable
        // and takes effect once the rule is enabled again.
        const ruleOff = r.enabled === false;
        html += `<div class="sc-rule-row${ruleOff ? " sc-rule-off" : ""}"${ruleOff ? ` title="${this._esc(this._t("scenario_rule_off_hint"))}"` : ""}>
          <span class="sc-rule-label"><span class="priority-badge">#${ri + 1}</span><span${disabled ? ' class="sc-rule-disabled"' : ""}>${this._esc(r.name)}</span>${r.safety ? `<span class="rule-safety-badge" title="${this._esc(this._t("rule_safety"))}">${this._lucideIcon("shield", 12)}${this._esc(this._t("rule_safety_badge"))}</span>` : ""}${ruleOff ? `<span class="sc-rule-off-badge">${this._esc(this._t("scenario_rule_off"))}</span>` : ""}</span>
          <label class="toggle">
            <input type="checkbox" ${!disabled ? "checked" : ""} data-action="scenario-rule-toggle" data-scenario="${this._esc(sc.id)}" data-rule="${this._esc(r.id)}">
            <span class="toggle-slider"></span>
          </label>
        </div>`;
      }
    }
    html += '</div></div>';
    return html;
  }

  _renderScenarioIconPicker(currentIcon) {
    const selected = (currentIcon || "").trim();
    const inGrid = SCENARIO_ICON_CHOICES.includes(selected);
    const customValue = inGrid ? "" : selected;
    let grid = "";
    for (const ic of SCENARIO_ICON_CHOICES) {
      const cls = ic === selected ? "icon-picker-btn selected" : "icon-picker-btn";
      grid += `<button type="button" class="${cls}" data-action="scenario-icon-pick" data-icon="${this._esc(ic)}" title="${this._esc(ic)}"><ha-icon icon="${this._esc(ic)}"></ha-icon></button>`;
    }
    return `
      <input type="hidden" data-scenario-field="icon" value="${this._esc(selected)}">
      <div class="icon-picker-grid">${grid}</div>
      <details class="icon-picker-custom"${customValue ? " open" : ""}>
        <summary>${this._t("scenario_icon_custom")}</summary>
        <div class="icon-picker-custom-body">
          <input type="text" data-scenario-icon-custom value="${this._esc(customValue)}" placeholder="mdi:lightbulb">
          <div class="icon-picker-custom-hint">${this._t("scenario_icon_custom_hint")}</div>
        </div>
      </details>`;
  }

  _renderScenarioEditForm(sc, rules, isActive) {
    let html = `<div class="inline-form">
      <div class="form-group">
        <label>${this._t("name")}</label>
        <input type="text" value="${this._esc(sc.name)}" data-scenario-field="name">
      </div>
      <div class="form-group">
        <label>${this._t("scenario_icon")}</label>
        ${this._renderScenarioIconPicker(sc.icon || "")}
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" data-action="scenario-edit-cancel">${this._t("cancel")}</button>
        <button class="btn btn-primary" data-action="scenario-edit-save" data-id="${this._esc(sc.id)}">${this._t("save")}</button>
      </div>
    </div>`;
    return html;
  }

  _renderScenarioAddForm() {
    let html = `<div class="inline-form">
      <div class="form-group">
        <label>${this._t("name")}</label>
        <input type="text" value="" data-scenario-field="name" placeholder="${this._t("name")}">
      </div>
      <div class="form-group">
        <label>${this._t("scenario_icon")}</label>
        ${this._renderScenarioIconPicker("mdi:home")}
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" data-action="scenario-add-cancel">${this._t("cancel")}</button>
        <button class="btn btn-primary" data-action="scenario-add-save">${this._t("add")}</button>
      </div>
    </div>`;
    return html;
  }

  async _onScenarioActivate(scenarioId) {
    try {
      const result = await this._ws("cover_automatic/scenario/update", { scenario_id: scenarioId, activate: true });
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }

  // Calls are serialized per scenario: each one starts from the list the
  // previous call returned, so quick successive clicks are all kept.
  _onScenarioRuleToggle(scenarioId, ruleId, checked, el = null) {
    if (!this._scRuleQueue) this._scRuleQueue = {};
    if (!this._scRuleQueueLen) this._scRuleQueueLen = {};
    this._scRuleQueueLen[scenarioId] = (this._scRuleQueueLen[scenarioId] || 0) + 1;
    const run = async () => {
      let rerender = false;
      try {
        const scenario = (this._config.scenarios || {})[scenarioId];
        if (!scenario) return;
        let disabled = [...(scenario.rules_disabled || [])];
        if (checked) {
          disabled = disabled.filter(id => id !== ruleId);
        } else if (!disabled.includes(ruleId)) {
          disabled.push(ruleId);
        }
        const result = await this._ws("cover_automatic/scenario/update", { scenario_id: scenarioId, rules_disabled: disabled });
        // More clicks queued: keep their checkboxes as clicked until the last one
        const more = this._scRuleQueueLen[scenarioId] > 1;
        this._updateConfigFromResult(result, more ? { render: false } : {});
      } catch (e) {
        console.error(e);
        if (el && el.isConnected) el.checked = !checked;
        rerender = true;
        this._showError(e);
      } finally {
        this._scRuleQueueLen[scenarioId] -= 1;
        // Last queued call failed or an earlier result was not rendered
        if (rerender && this._scRuleQueueLen[scenarioId] === 0) this._render();
      }
    };
    const prev = this._scRuleQueue[scenarioId] || Promise.resolve();
    const next = prev.then(run, run);
    this._scRuleQueue[scenarioId] = next;
    return next;
  }

  _onScenarioIconPick(btn) {
    const form = btn.closest(".inline-form");
    if (!form) return;
    const icon = btn.dataset.icon || "";
    const hidden = form.querySelector('[data-scenario-field="icon"]');
    if (hidden) hidden.value = icon;
    const custom = form.querySelector('[data-scenario-icon-custom]');
    if (custom) custom.value = "";
    form.querySelectorAll('[data-action="scenario-icon-pick"]').forEach(el => {
      el.classList.toggle("selected", el === btn);
    });
  }

  _readScenarioIcon(form, fallback) {
    const custom = form.querySelector('[data-scenario-icon-custom]')?.value || "";
    if (custom.trim()) return custom.trim();
    const picked = form.querySelector('[data-scenario-field="icon"]')?.value || "";
    return picked.trim() || fallback;
  }

  async _onScenarioAddSave(btn) {
    const form = btn.closest(".inline-form");
    if (!form) return;
    const name = form.querySelector('[data-scenario-field="name"]')?.value || "";
    if (!name.trim()) return;
    const icon = this._readScenarioIcon(form, "mdi:home");
    try {
      const result = await this._ws("cover_automatic/scenario/add", { name: name.trim(), icon: icon });
      this._addingScenario = false;
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }

  async _onScenarioEditSave(btn) {
    const scenarioId = btn.dataset.id;
    const form = btn.closest(".inline-form");
    if (!form) return;
    const name = form.querySelector('[data-scenario-field="name"]')?.value || "";
    if (!name.trim()) return;
    const icon = this._readScenarioIcon(form, "mdi:home");
    try {
      const result = await this._ws("cover_automatic/scenario/update", { scenario_id: scenarioId, name: name.trim(), icon: icon });
      this._editingScenario = null;
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }

  _onScenarioDelete(scenarioId) {
    this._showConfirm(this._t("confirm_delete"), async () => {
      try {
        const result = await this._ws("cover_automatic/scenario/delete", { scenario_id: scenarioId });
        this._updateConfigFromResult(result);
      } catch (e) { console.error(e); this._showError(e); }
    });
  }
};

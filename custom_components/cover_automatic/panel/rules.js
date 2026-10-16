// CoverAutomatic panel -- Rules tab: list, filters, editor, drafts, ordering.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).

export const RulesMixin = (Base) => class extends Base {
  // Covers targeted by a rule (all covers when it names none) that can tilt
  _ruleUsesTilt(facadeIds, coverIds) {
    const covers = Object.values((this._config && this._config.covers) || {});
    const targeted = (!facadeIds.length && !coverIds.length)
      ? covers
      : covers.filter(c => coverIds.includes(c.entity_id) || (c.facade_id && facadeIds.includes(c.facade_id)));
    return targeted.some(c => c.supports_tilt);
  }

  // Shows the tilt field once a cover able to tilt is targeted (chips toggled)
  _refreshRuleTilt(ruleId) {
    const root = this.shadowRoot;
    const row = root && root.querySelector(`[data-rule-top="${CSS.escape(ruleId)}"]`);
    if (!row) return;
    const ids = (action, key) => Array.from(root.querySelectorAll(`[data-action="${action}"][data-rule="${CSS.escape(ruleId)}"].selected`))
      .map(el => el.dataset[key]);
    const input = row.querySelector('[data-field="target_tilt_position"]');
    const show = this._ruleUsesTilt(ids("rule-facade-toggle", "facade"), ids("rule-cover-toggle", "cover"))
      || (input && input.value !== "");
    row.classList.toggle("no-tilt", !show);
    const group = row.querySelector(".rule-tilt-group");
    if (group) group.hidden = !show;
  }

  /* ============================================================
   * TAB: Rules
   * ============================================================ */
  // Rules tab filter: a rule without facade and cover applies to every cover,
  // a rule without scenario list belongs to every scenario.
  _ruleMatchesFilter(r, f) {
    const covers = this._config.covers || {};
    const coverIds = r.cover_ids || [], facadeIds = r.facade_ids || [];
    const everywhere = !coverIds.length && !facadeIds.length;
    if (f.facade && !everywhere && !facadeIds.includes(f.facade)
      && !coverIds.some(id => covers[id] && covers[id].facade_id === f.facade)) return false;
    if (f.cover && !everywhere && !coverIds.includes(f.cover)
      && !(covers[f.cover] && facadeIds.includes(covers[f.cover].facade_id))) return false;
    if (f.scenario && Array.isArray(r.scenario_ids) && !r.scenario_ids.includes(f.scenario)) return false;
    return true;
  }

  _renderRuleFilterBar(f, shown, total) {
    const select = (key, allKey, options) => `<select data-action="rule-filter" data-filter-key="${key}" aria-label="${this._esc(this._t(allKey))}">
        <option value="">${this._esc(this._t(allKey))}</option>
        ${options.map(([value, label]) => `<option value="${this._esc(value)}"${f[key] === value ? " selected" : ""}>${this._esc(label)}</option>`).join("")}
      </select>`;
    const byName = (a, b) => String(a[1]).localeCompare(String(b[1]));
    const facades = Object.values(this._config.facades || {}).map(x => [x.id, x.name]).sort(byName);
    const covers = Object.values(this._config.covers || {}).map(c => [c.entity_id, c.name]).sort(byName);
    const scenarios = Object.values(this._config.scenarios || {}).map(sc => [sc.id, sc.name]);
    const filtering = Object.values(f).some(Boolean);
    return `<div class="log-cover-filter rule-filter-bar">
      ${select("scenario", "rule_filter_all_scenarios", scenarios)}
      ${select("facade", "rule_filter_all_facades", facades)}
      ${select("cover", "log_filter_all_covers", covers)}
      ${filtering ? `<button class="btn btn-sm" data-action="rule-filter-clear">${this._esc(this._t("rule_filter_clear"))}</button>
      <span class="rule-filter-count">${shown} / ${total}</span>` : ""}
    </div>`;
  }

  // Filter actually applied: a choice pointing at a deleted facade, cover or
  // scenario is ignored (the stored choice is left alone while rendering).
  _effectiveRuleFilter() {
    const f = this._ruleFilter, c = this._config;
    return {
      facade: f.facade && (c.facades || {})[f.facade] ? f.facade : "",
      cover: f.cover && (c.covers || {})[f.cover] ? f.cover : "",
      scenario: f.scenario && (c.scenarios || {})[f.scenario] ? f.scenario : "",
    };
  }

  _renderRules() {
    const rules = this._config.rules || {};
    const all = this._rulesByPriority(rules);
    const f = this._effectiveRuleFilter();
    const filtering = Object.values(f).some(Boolean);
    const matching = filtering ? all.filter(r => this._ruleMatchesFilter(r, f)) : all;
    // The rule being edited stays visible so its draft is never hidden
    // (it is not counted when it does not match)
    const sorted = filtering ? all.filter(r => r.id === this._expandedRule || matching.includes(r)) : all;

    let html = all.length ? this._renderRuleFilterBar(f, matching.length, all.length) : "";
    // Reordering a partial list would be ambiguous: only without filter
    html += filtering
      ? `<div class="rule-reorder-hint">${this._t("rule_filter_reorder_hint")}</div>`
      : `<div class="rule-reorder-hint">${this._t("rule_reorder_hint")}</div>`;

    if (sorted.length === 0 && !this._addingRule) {
      html += `<div class="empty-state">${this._t(filtering ? "rule_filter_none" : "none")}</div>`;
    }

    const activeRules = this._config.active_rules || {};

    for (let idx = 0; idx < sorted.length; idx++) {
      const r = sorted[idx];
      const isExpanded = this._expandedRule === r.id;
      const dragging = this._dragRuleId === r.id ? " dragging" : "";
      const dragOver = this._dragOverId === r.id ? " drag-over" : "";
      const matchedCovers = activeRules[r.id] || [];
      const isActive = matchedCovers.length > 0;

      const activeClass = isActive ? " rule-active" : "";
      html += filtering
        ? `<div class="rule-row${activeClass}" data-rule-id="${this._esc(r.id)}">`
        : `<div class="rule-row${activeClass}${dragging}${dragOver}" draggable="true" data-rule-id="${this._esc(r.id)}" data-action="rule-drag">`;
      html += `<span class="drag-handle${filtering ? " drag-handle-off" : ""}"${filtering ? "" : ` title="${this._esc(this._t("drag_handle"))}"`}>&#9783;</span>`;
      // Keyboard/touch alternative to drag & drop
      html += this._moveBtns(`data-id="${this._esc(r.id)}"`, "rule-prio-up", "rule-prio-down", "rule_priority_up", "rule_priority_down", filtering || idx === 0, filtering || idx === sorted.length - 1)
        .replace('class="move-btns"', 'class="move-btns move-btns-v"');
      html += `<div class="rule-info" data-action="rule-expand" data-id="${this._esc(r.id)}" tabindex="0" role="button" aria-expanded="${isExpanded ? "true" : "false"}">`;
      html += `<div class="rule-name">`;
      html += `<span class="rule-active-dot ${isActive ? "active" : ""}" title="${isActive ? this._t("rule_active_for") + " " + matchedCovers.length + " " + this._t("rule_covers_count") : this._t("rule_inactive")}"></span>`;
      html += `${this._esc(r.name)}`;
      if (r.safety) {
        html += `<span class="rule-safety-badge" title="${this._esc(this._t("rule_safety"))}">${this._lucideIcon("shield", 12)}${this._esc(this._t("rule_safety_badge"))}</span>`;
      }
      html += this._renderRuleScenarios(r);
      html += '</div>';
      html += '<div class="rule-meta">';
      // Real priority, also in a filtered list
      html += `<span class="priority-badge">#${all.indexOf(r) + 1}</span>`;
      const rg = this._ruleGroups(r);
      html += rg.n > 1
        ? `<span>${this._t("rule_groups_count").replace("{n}", rg.n)}</span>`
        : `<span>${this._t(rg.ops[0] === "or" ? "rule_op_short_or" : "rule_op_short_and")}</span>`;
      html += `<span class="rule-target">${this._t("rule_target_pos")}${this._colon()}${this._posBar(r.target_position, "compact")}</span>`;
      if (r.target_tilt_position != null) {
        html += `<span class="rule-target">${this._t("rule_target_tilt")}${this._colon()}${this._posBar(r.target_tilt_position, "compact")}</span>`;
      }
      html += '</div>';
      // Condition chips
      if (r.conditions && r.conditions.length > 0) {
        html += '<div class="chip-group mt-6">';
        const chip = (c, ci) => {
          const invalid = c.type === "ha_condition" && this._config.condition_status?.[r.id]?.[String(ci)]?.valid === false;
          const not = c.negate ? `<b class="chip-not">${this._t("rule_cond_not")}</b> ` : "";
          return `<span class="chip${invalid ? " chip-error" : ""}">${not}${this._esc(this._condChipLabel(c))}</span>`;
        };
        if (rg.n > 1) {
          // One bracketed block per group, joined by the between-groups operator
          const parts = [];
          for (let g = 0; g < rg.n; g++) {
            const members = [...r.conditions.entries()].filter(([, c]) => (parseInt(c.group, 10) || 0) === g);
            if (!members.length) continue;
            const inner = this._t(rg.ops[g] === "or" ? "rule_op_short_or" : "rule_op_short_and");
            parts.push(`<span class="chip-block">${members.map(([ci, c]) => chip(c, ci)).join(`<span class="chip-op">${inner}</span>`)}</span>`);
          }
          html += parts.join(`<span class="chip-op chip-op-between">${this._t(rg.between === "or" ? "rule_op_short_or" : "rule_op_short_and")}</span>`);
        } else {
          for (const [ci, c] of r.conditions.entries()) html += chip(c, ci);
        }
        html += '</div>';
      }
      html += '</div>'; // rule-info

      // Enable toggle
      html += `<label class="toggle">
        <input type="checkbox" ${r.enabled ? "checked" : ""} data-action="rule-toggle-enabled" data-id="${this._esc(r.id)}" aria-label="${this._esc(this._t("rule_enabled_aria").replace("{name}", r.name || r.id))}">
        <span class="toggle-slider"></span>
      </label>`;

      html += `<button class="btn-icon" data-action="rule-duplicate" data-id="${this._esc(r.id)}" title="${this._esc(this._t("rule_duplicate"))}" aria-label="${this._esc(this._t("rule_duplicate"))}">${this._lucideIcon("copy", 16)}</button>`;
      html += `<button class="btn-icon" data-action="rule-delete" data-id="${this._esc(r.id)}" title="${this._t("delete")}">&#10005;</button>`;
      html += '</div>'; // rule-row

      // Expanded editor
      html += `<div class="rule-editor${isExpanded ? " expanded" : ""}">`;
      if (isExpanded) {
        // The editor works on the draft; the row above shows the saved rule.
        html += this._renderRuleEditor(this._edRule(r.id) || r);
      }
      html += '</div>';
    }

    // Add rule button/form
    if (this._addingRule) {
      html += this._renderRuleAddForm();
    } else {
      html += `<button class="btn btn-primary mt-16" data-action="rule-add-start">+ ${this._t("rule_add")}</button>`;
    }

    return html;
  }

  // Scenarios a rule applies to, shown after its name. A scenario where the
  // rule is switched off (Scenarios tab) is struck through.
  _renderRuleScenarios(rule) {
    const scenarios = (this._config && this._config.scenarios) || {};
    const ids = Object.keys(scenarios);
    const member = rule.scenario_ids == null ? ids : ids.filter(id => rule.scenario_ids.includes(id));
    if (!member.length) {
      return `<span class="rule-scen rule-scen-none">${this._esc(this._t("rule_scen_none"))}</span>`;
    }
    const off = (id) => (scenarios[id].rules_disabled || []).includes(rule.id);
    if (member.length === ids.length && !member.some(off)) {
      return `<span class="rule-scen">${this._esc(this._t("rule_filter_all_scenarios"))}</span>`;
    }
    return member.map(id => off(id)
      ? `<span class="rule-scen rule-scen-off" title="${this._esc(this._t("rule_scen_off"))}">${this._esc(scenarios[id].name || id)}</span>`
      : `<span class="rule-scen">${this._esc(scenarios[id].name || id)}</span>`).join("");
  }

  _renderRuleEditor(rule) {
    const facades = this._config.facades || {};
    const covers = this._config.covers || {};

    let html = '';

    const rid = this._esc(rule.id);
    const hasTilt = this._ruleUsesTilt(rule.facade_ids || [], rule.cover_ids || [])
      || rule.target_tilt_position != null;

    // Name, target position and tilt on one line. The tilt only shows when a
    // cover of the rule can tilt its slats (or a tilt is already set).
    html += `<div class="form-group rule-top-row${hasTilt ? "" : " no-tilt"}" data-rule-top="${rid}">
      <span class="rule-inline-label">${this._t("name")}</span>
      <input type="text" class="rule-name-input" value="${this._esc(rule.name)}" data-action="rule-field" data-id="${rid}" data-field="name" maxlength="100" aria-label="${this._esc(this._t("name"))}">
      <span class="rule-top-field">
        <span class="rule-top-label">${this._t("rule_target_pos")}${this._hintToggle(rule.id, "rule_target_pos_hint")}</span>
        <input type="number" min="0" max="100" value="${this._num(rule.target_position)}" data-action="rule-field" data-id="${rid}" data-field="target_position" aria-label="${this._esc(this._t("rule_target_pos"))}">
      </span>
      <span class="rule-top-field rule-tilt-group"${hasTilt ? "" : " hidden"}>
        <span class="rule-top-label">${this._t("rule_target_tilt")}</span>
        <input type="number" min="0" max="100" value="${this._num(rule.target_tilt_position, "")}" placeholder="${this._t("none")}" data-action="rule-field" data-id="${rid}" data-field="target_tilt_position" aria-label="${this._esc(this._t("rule_target_tilt"))}">
      </span>
      ${this._hintPanel(rule.id, "rule_target_pos_hint")}
    </div>`;

    // Scenarios (null = all) and safety switch on one line
    const scenarios = Object.values(this._config.scenarios || {});
    html += `<div class="rule-inline-row">
      <span class="rule-inline-label">${this._t("rule_scenarios")}${this._hintToggle(rule.id, "rule_scenarios_hint")}</span>
      <div class="multi-select">${scenarios.map(sc => {
        const member = !Array.isArray(rule.scenario_ids) || rule.scenario_ids.includes(sc.id);
        return `<button class="ms-item${member ? " selected" : ""}" data-action="rule-scenario-toggle" data-rule="${rid}" data-scenario="${this._esc(sc.id)}">${this._esc(sc.name)}</button>`;
      }).join("")}</div>
      <div class="rule-safety-inline">
        <span>${this._t("rule_safety")}${this._hintToggle(rule.id, "rule_safety_hint")}</span>
        <label class="toggle">
          <input type="checkbox" ${rule.safety ? "checked" : ""} data-action="rule-field" data-id="${rid}" data-field="safety">
          <span class="toggle-slider"></span>
        </label>
      </div>
      ${this._hintPanel(rule.id, "rule_scenarios_hint")}
      ${this._hintPanel(rule.id, "rule_safety_hint")}
    </div>`;

    // Facades and covers the rule applies to
    html += `<div class="rule-inline-row">
      <span class="rule-inline-label">${this._t("rule_facades")}${this._hintToggle(rule.id, "rule_assignment_hint")}</span>
      <div class="multi-select">${Object.values(facades).map(f => {
        const sel = (rule.facade_ids || []).includes(f.id) ? " selected" : "";
        return `<button class="ms-item${sel}" data-action="rule-facade-toggle" data-rule="${rid}" data-facade="${this._esc(f.id)}">${this._esc(f.name)}</button>`;
      }).join("")}</div>
      ${this._hintPanel(rule.id, "rule_assignment_hint")}
    </div>`;
    html += `<div class="rule-inline-row">
      <span class="rule-inline-label">${this._t("rule_covers")}</span>
      <div class="multi-select">${Object.values(covers).map(c => {
        const sel = (rule.cover_ids || []).includes(c.entity_id) ? " selected" : "";
        return `<button class="ms-item${sel}" data-action="rule-cover-toggle" data-rule="${rid}" data-cover="${this._esc(c.entity_id)}">${this._esc(c.name)}</button>`;
      }).join("")}</div>
    </div>`;

    // Conditions, organised in groups
    const condCount = (rule.conditions || []).length;
    const allCollapsed = condCount > 0 && rule.conditions.every((_, i) => this._isCondCollapsed(rule.id, i));
    html += `<div class="rule-conditions-label"><span>${this._t("rule_conditions")}</span>${condCount > 1
      ? `<button class="cond-collapse-all" data-action="rule-cond-collapse-all" data-rule="${this._esc(rule.id)}">${this._t(allCollapsed ? "cond_expand_all" : "cond_collapse_all")}</button>` : ""}</div>`;
    html += this._renderConditionGroups(rule);

    // Save button
    html += `<div class="rule-editor-actions">
      <button class="btn btn-primary" data-action="rule-save" data-id="${this._esc(rule.id)}">${this._t("save")}</button>
    </div>`;

    return html;
  }

  _renderRuleAddForm() {
    let html = `<div class="inline-form mt-16">
      <div class="form-group">
        <label>${this._t("name")}</label>
        <input type="text" value="" data-rule-new-field="name" maxlength="100" placeholder="${this._t("name")}">
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>${this._t("rule_target_pos")}</label>
          <input type="number" min="0" max="100" value="0" data-rule-new-field="target_position">
        </div>
        <div class="form-group">
          <label>${this._t("rule_target_tilt")}</label>
          <input type="number" min="0" max="100" value="" placeholder="${this._t("none")}" data-rule-new-field="target_tilt_position">
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" data-action="rule-add-cancel">${this._t("cancel")}</button>
        <button class="btn btn-primary" data-action="rule-add-save">${this._t("add")}</button>
      </div>
    </div>`;
    return html;
  }

  /* ---------- Drag delegation ---------- */
  _handleDragStart(e) {
    const row = e.target.closest('[data-action="rule-drag"]');
    if (!row) return;
    this._dragRuleId = row.dataset.ruleId;
    row.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", row.dataset.ruleId);
  }

  _handleDragEnd(e) {
    const row = e.target.closest('[data-action="rule-drag"]');
    if (!row) return;
    this._dragRuleId = null;
    this._dragOverId = null;
    this.shadowRoot.querySelectorAll(".rule-row").forEach(r => {
      r.classList.remove("dragging");
      r.classList.remove("drag-over");
    });
  }

  _handleDragOver(e) {
    const row = e.target.closest('[data-action="rule-drag"]');
    if (!row) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (row.dataset.ruleId !== this._dragRuleId) {
      this._dragOverId = row.dataset.ruleId;
      this.shadowRoot.querySelectorAll(".rule-row").forEach(r => r.classList.remove("drag-over"));
      row.classList.add("drag-over");
    }
  }

  _handleDragLeave(e) {
    const row = e.target.closest('[data-action="rule-drag"]');
    if (row) row.classList.remove("drag-over");
  }

  async _handleDrop(e) {
    const row = e.target.closest('[data-action="rule-drag"]');
    if (!row) return;
    e.preventDefault();
    row.classList.remove("drag-over");
    const draggedId = e.dataTransfer.getData("text/plain");
    const targetId = row.dataset.ruleId;
    if (draggedId && targetId && draggedId !== targetId) {
      const rules = this._config.rules || {};
      const sorted = this._rulesByPriority(rules);
      const ids = sorted.map(r => r.id);
      const fromIdx = ids.indexOf(draggedId);
      const toIdx = ids.indexOf(targetId);
      if (fromIdx !== -1 && toIdx !== -1) {
        ids.splice(fromIdx, 1);
        ids.splice(toIdx, 0, draggedId);
        await this._reorderRules(ids);
      }
    }
    this._dragRuleId = null;
    this._dragOverId = null;
  }

  async _reorderRules(ids) {
    try {
      const result = await this._ws("cover_automatic/rule/reorder", { rule_ids: ids });
      this._updateConfigFromResult(result);
      return true;
    } catch (err) { console.error(err); this._showError(err); return false; }
  }

  // Up/down buttons: move a rule one step in priority.
  async _onRuleMove(ruleId, delta) {
    if (this._ruleMoving) return;
    const ids = this._rulesByPriority(this._config.rules || {}).map(r => r.id);
    const from = ids.indexOf(ruleId);
    const to = from + delta;
    if (from === -1 || to < 0 || to >= ids.length) return;
    ids.splice(from, 1);
    ids.splice(to, 0, ruleId);
    this._ruleMoving = true;
    let ok = false;
    try { ok = await this._reorderRules(ids); } finally { this._ruleMoving = false; }
    if (!ok) return;
    // Keep keyboard focus on the moved rule (fall back to the other arrow at the ends)
    const row = this.shadowRoot.querySelector(`.rule-row[data-rule-id="${CSS.escape(ruleId)}"]`);
    if (!row) return;
    const want = row.querySelector(`[data-action="${delta < 0 ? "rule-prio-up" : "rule-prio-down"}"]`);
    const other = row.querySelector(`[data-action="${delta < 0 ? "rule-prio-down" : "rule-prio-up"}"]`);
    (want && !want.disabled ? want : other)?.focus();
  }

  async _onRuleToggleEnabled(ruleId, checked, el = null) {
    try {
      const result = await this._ws("cover_automatic/rule/update", { rule_id: ruleId, enabled: checked });
      this._updateConfigFromResult(result);
    } catch (e) {
      console.error(e);
      if (el) el.checked = !checked;
      this._showError(e);
    }
  }

  _onRuleDelete(ruleId) {
    this._showConfirm(this._t("confirm_delete"), async () => {
      try {
        const result = await this._ws("cover_automatic/rule/delete", { rule_id: ruleId });
        if (this._expandedRule === ruleId) this._setExpandedRule(null);
        this._updateConfigFromResult(result);
      } catch (e) { console.error(e); this._showError(e); }
    });
  }

  // First invalid field of the open rule editor (marked red), or null.
  // An empty/invalid number would otherwise silently keep its old value.
  _ruleEditorInvalid(ruleId) {
    const row = this.shadowRoot.querySelector(`.rule-row[data-rule-id="${CSS.escape(ruleId)}"]`);
    const editor = row && row.nextElementSibling && row.nextElementSibling.classList.contains("rule-editor") ? row.nextElementSibling : null;
    if (!editor) return null;
    let first = null;
    for (const el of editor.querySelectorAll("input, select, textarea")) {
      if (el.disabled || el.type === "hidden") continue;
      let bad = el.classList.contains("input-invalid") || this._fieldBadValidity(el);
      // The target position is required (empty = old value kept)
      if (!bad && el.dataset.field === "target_position" && el.value.trim() === "") bad = true;
      if (bad) {
        if (!el.classList.contains("input-invalid")) this._setInputInvalid(el, this._t("input_invalid_number"));
        if (!first) first = el;
      }
    }
    return first;
  }

  async _onRuleSave(ruleId) {
    const invalid = this._ruleEditorInvalid(ruleId);
    if (invalid) {
      this._showToast(this._t("rule_invalid_fields"), true);
      // Field hidden in a collapsed condition card: expand that card first
      const card = invalid.closest && invalid.closest(".condition-card.collapsed");
      if (card && card.dataset.condCard) {
        const key = card.dataset.condCard;
        const cut = key.lastIndexOf(":");
        const idx = parseInt(key.slice(cut + 1), 10);
        if (Number.isInteger(idx)) this._setCondCollapsed(key.slice(0, cut), idx, false);
      }
      if (invalid.offsetParent !== null) {
        invalid.scrollIntoView({ block: "center", behavior: "smooth" });
        invalid.focus({ preventScroll: true });
      }
      return;
    }
    // YAML conditions: wait until params.config matches the typed YAML
    await this._flushHaValidations(ruleId);
    const data = this._collectRuleEditorData(this.shadowRoot, ruleId);
    if (!data) return;
    // A valid YAML condition the form can show goes back to the form view
    // (templates and other complex conditions stay in YAML).
    (data.conditions || []).forEach((c, idx) => {
      if (!c || c.type !== "ha_condition" || !c.params || c.params.ui !== "yaml") return;
      const live = this._haLive && this._haLive[ruleId + ":" + idx];
      if (live && (live.pending || live.valid === false)) return;
      if (this._haFormModel(c.params.config, c.params.op)) c.params = { ...c.params, ui: "form" };
    });
    try {
      const result = await this._ws("cover_automatic/rule/update", data);
      this._updateConfigFromResult(result, { resetDraft: true });
      this._refreshCondPreview();
    } catch (e) { console.error(e); this._showError(e); }
  }

  // Apply a structural change (conditions/groups) to the editor draft only:
  // like every other edit it reaches the server with "Save". Callers flush
  // pending HA validations first. indexMap(oldIdx) -> newIdx | null keeps the
  // collapsed state and live HA status of each card with its condition.
  // Resolves to true when applied.
  async _saveRuleStructure(ruleId, conditions, groups, indexMap = null) {
    if (ruleId === this._expandedRule) this._syncRuleDraftFromDom();
    const rule = this._edRule(ruleId);
    if (!rule) { this._render(); return false; }
    // Indices may change: void pending validations and previews.
    this._cancelHaTimers(ruleId);
    this._previewSeq++;
    if (conditions) rule.conditions = conditions.map(c => ({ ...c }));
    if (groups) {
      rule.group_operators = [...groups.ops];
      rule.condition_operator = groups.between;
    }
    // A single group left: its own operator is the rule's operator (the
    // "between groups" one no longer applies).
    const info = this._ruleGroups(rule);
    if (info.n === 1) {
      rule.group_operators = [info.ops[0]];
      rule.condition_operator = info.ops[0];
    }
    if (indexMap) this._remapRuleIndexState(ruleId, indexMap);
    // The DOM still shows the old structure: don't read it back into the
    // draft while re-rendering (indices changed).
    this._noDomSync = true;
    try { this._render(); } finally { this._noDomSync = false; }
    this._refreshCondPreview();
    return true;
  }

  // Move per-condition editor state (collapsed cards, live HA status) to the
  // new condition indices; null drops the entry.
  _remapRuleIndexState(ruleId, indexMap) {
    const pre = ruleId + ":";
    const remap = (keys, put) => {
      for (const key of keys) {
        if (!key.startsWith(pre)) continue;
        const next = indexMap(parseInt(key.slice(pre.length), 10));
        if (next != null) put(pre + next, key);
      }
    };
    if (this._collapsedConds) {
      const old = this._collapsedConds;
      const next = new Set([...old].filter(k => !k.startsWith(pre)));
      remap(old, (k) => next.add(k));
      this._collapsedConds = next;
    }
    if (this._haLive) {
      const old = this._haLive;
      const next = {};
      for (const [k, v] of Object.entries(old)) if (!k.startsWith(pre)) next[k] = v;
      remap(Object.keys(old), (k, from) => { if (!old[from].pending) next[k] = old[from]; });
      this._haLive = next;
    }
  }

  async _onRuleAddSave(btn) {
    const form = btn.closest(".inline-form");
    if (!form) return;
    const name = form.querySelector('[data-rule-new-field="name"]')?.value || "";
    if (!name.trim()) return;
    const tp = (() => { const v = form.querySelector('[data-rule-new-field="target_position"]')?.value; return v !== "" && v != null ? parseInt(v, 10) : 0; })();
    const ttp = form.querySelector('[data-rule-new-field="target_tilt_position"]')?.value;
    try {
      const data = { name: name.trim(), target_position: tp };
      if (ttp !== "" && ttp != null) {
        const n = parseInt(ttp, 10);
        if (Number.isFinite(n)) data.target_tilt_position = n;
      }
      const result = await this._ws("cover_automatic/rule/add", data);
      this._addingRule = false;
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }

  // Rule as the editor sees it: the draft of the open rule, else the saved one.
  _edRule(ruleId) {
    if (ruleId == null) return null;
    const d = this._ruleDraft;
    if (d && d.id === ruleId) return d.rule;
    const saved = (this._config && this._config.rules || {})[ruleId] || null;
    // The open editor always works on a draft (created on first use)
    if (saved && ruleId === this._expandedRule) {
      this._ruleDraft = { id: ruleId, rule: this._clone(saved) };
      return this._ruleDraft.rule;
    }
    return saved;
  }

  // Open another rule editor (or none): the previous draft is discarded.
  // Copy placed right below the original, active, and opened for editing.
  async _onRuleDuplicate(ruleId) {
    const rule = (this._config.rules || {})[ruleId];
    if (!rule) return;
    try {
      const suffix = " - " + this._t("rule_copy_suffix");
      // Rule names are limited to 100 characters (room left for " 2", " 3"...)
      const name = rule.name.slice(0, Math.max(1, 97 - suffix.length)).trimEnd() + suffix;
      const result = await this._ws("cover_automatic/rule/duplicate", { rule_id: ruleId, name });
      this._setExpandedRule(null);
      this._updateConfigFromResult(result);
      if (result.new_rule_id) {
        this._setExpandedRule(result.new_rule_id);
        this._render();
        this._startCondPreview();
        setTimeout(() => this.shadowRoot.querySelector(`.rule-row[data-rule-id="${CSS.escape(result.new_rule_id)}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 50);
      }
    } catch (e) { console.error(e); this._showError(e); }
  }

  _setExpandedRule(ruleId) {
    this._discardRuleDraft();
    this._expandedRule = ruleId || null;
    const saved = ruleId ? (this._config && this._config.rules || {})[ruleId] : null;
    if (saved) {
      this._ruleDraft = { id: ruleId, rule: this._clone(saved) };
      // Existing conditions open collapsed; conditions added afterwards open expanded.
      if (!this._collapsedConds) this._collapsedConds = new Set();
      const pre = ruleId + ":";
      for (const k of [...this._collapsedConds]) if (k.startsWith(pre)) this._collapsedConds.delete(k);
      (saved.conditions || []).forEach((_, i) => this._collapsedConds.add(pre + i));
    }
  }

  _discardRuleDraft() {
    const d = this._ruleDraft;
    if (!d) return;
    this._ruleDraft = null;
    // Pending validations/previews refer to the discarded conditions
    this._cancelHaTimers(d.id);
    this._previewSeq++;
    if (this._haLive) {
      const pre = d.id + ":";
      for (const k of Object.keys(this._haLive)) if (k.startsWith(pre)) delete this._haLive[k];
    }
  }

  // Copy the editor fields that live only in the DOM (name, targets,
  // scenario/facade/cover chips) into the draft.
  _syncRuleDraftFromDom() {
    const d = this._ruleDraft;
    if (!d || this._noDomSync || !this.shadowRoot) return;
    const root = this.shadowRoot;
    const id = CSS.escape(d.id);
    const field = (f) => root.querySelector(`[data-action="rule-field"][data-id="${id}"][data-field="${f}"]`);
    const nameEl = field("name");
    if (!nameEl) return; // editor not rendered
    const r = d.rule;
    r.name = nameEl.value;
    const safetyEl = field("safety");
    if (safetyEl) r.safety = !!safetyEl.checked;
    const tpEl = field("target_position");
    if (tpEl && tpEl.value !== "") {
      const n = parseInt(tpEl.value, 10);
      if (Number.isFinite(n)) r.target_position = n;
    }
    const ttpEl = field("target_tilt_position");
    if (ttpEl) {
      if (ttpEl.value === "" && !(ttpEl.validity && ttpEl.validity.badInput)) r.target_tilt_position = null;
      else {
        const n = parseInt(ttpEl.value, 10);
        if (Number.isFinite(n)) r.target_tilt_position = n;
      }
    }
    const chips = (action, attr) => [...root.querySelectorAll(`[data-action="${action}"][data-rule="${id}"].selected`)].map(el => el.dataset[attr]);
    r.scenario_ids = chips("rule-scenario-toggle", "scenario");
    r.facade_ids = chips("rule-facade-toggle", "facade");
    r.cover_ids = chips("rule-cover-toggle", "cover");
  }

  // True when the open rule's draft differs from the saved rule.
  _ruleDraftDirty() {
    const d = this._ruleDraft;
    if (!d) return false;
    const saved = (this._config && this._config.rules || {})[d.id];
    if (!saved) return false;
    this._syncRuleDraftFromDom();
    // Chip order is not meaningful
    const norm = (p) => JSON.stringify({ ...p, scenario_ids: [...p.scenario_ids].sort(), facade_ids: [...p.facade_ids].sort(), cover_ids: [...p.cover_ids].sort() });
    return norm(this._buildRulePayload(d.id, d.rule)) !== norm(this._buildRulePayload(d.id, saved));
  }

  // Run `then` after the user agreed to drop unsaved rule edits (if any).
  _confirmLeaveRule(then) {
    if (this._ruleDraftDirty()) this._showConfirm(this._t("rule_unsaved_confirm"), then, this._t("discard"));
    else then();
  }

  _buildRulePayload(ruleId, rule, overrideConditions = null, overrideGroups = null) {
    const groupInfo = this._ruleGroups(rule);
    let op = groupInfo.between;
    let groupOps = groupInfo.ops;
    if (overrideGroups) { groupOps = overrideGroups.ops; op = overrideGroups.between; }
    // scenario_ids null = member of every scenario (all chips selected)
    const scenarioIds = Array.isArray(rule.scenario_ids)
      ? [...rule.scenario_ids] : Object.values(this._config.scenarios || {}).map(sc => sc.id);
    const ttp = rule.target_tilt_position;
    // Conditions from override (pending add/delete) or the draft
    const source = overrideConditions ?? (rule.conditions || []);
    const conditions = source.map(c => ({
      type: c.type, params: c.params || {},
      group: Math.min(parseInt(c.group, 10) || 0, Math.max(groupOps.length - 1, 0)),
      negate: !!c.negate,
    }));
    return {
      rule_id: ruleId,
      name: String(rule.name ?? "").trim(),
      target_position: rule.target_position,
      target_tilt_position: Number.isFinite(ttp) ? ttp : null,
      condition_operator: op,
      group_operators: groupOps,
      scenario_ids: scenarioIds,
      facade_ids: [...(rule.facade_ids || [])],
      cover_ids: [...(rule.cover_ids || [])],
      safety: !!rule.safety,
      conditions: conditions
    };
  }

  // Payload of rule/update for the open editor (draft + DOM-only fields).
  _collectRuleEditorData(root, ruleId, overrideConditions = null, overrideGroups = null) {
    if (ruleId === this._expandedRule) this._syncRuleDraftFromDom();
    const rule = this._edRule(ruleId);
    if (!rule) return null;
    return this._buildRulePayload(ruleId, rule, overrideConditions, overrideGroups);
  }
};

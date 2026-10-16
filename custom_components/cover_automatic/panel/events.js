// CoverAutomatic panel -- Event delegation: clicks, changes, inputs, keyboard, tab switch.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).
import { FACADE_BEARINGS } from "./constants.js";

export const EventsMixin = (Base) => class extends Base {
  /* ============================================================
   * Event delegation (bound once, routes all events)
   * ============================================================ */
  _setupDelegation() {
    if (this._delegationBound) return;
    this._delegationBound = true;
    const root = this.shadowRoot;

    root.addEventListener("click", (e) => this._handleClick(e));
    root.addEventListener("change", (e) => { this._handleChange(e); this._refreshDeps(); });
    root.addEventListener("input", (e) => { this._handleInput(e); this._refreshDeps(); });
    root.addEventListener("dragstart", (e) => this._handleDragStart(e));
    root.addEventListener("dragend", (e) => this._handleDragEnd(e));
    root.addEventListener("dragover", (e) => this._handleDragOver(e));
    root.addEventListener("dragleave", (e) => this._handleDragLeave(e));
    root.addEventListener("drop", (e) => this._handleDrop(e));
    root.addEventListener("pointerdown", (e) => this._handleHouseDragStart(e));
    root.addEventListener("focusout", (e) => this._onSlideFocusOut(e));
    // Enter/Space activate non-native interactive elements (rows, sort headers)
    root.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const el = e.composedPath()[0];
      if (!el || !el.closest) return;
      const target = el.closest('[data-action][tabindex]');
      if (!target || ["BUTTON", "A", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"].includes(el.tagName)) return;
      e.preventDefault();
      target.click();
    });
  }

  /* ---------- Keyboard (window-level) ---------- */
  _handleKeyDown(e) {
    if (e.key !== "Escape") return;
    if (this._confirmCallback) {
      e.stopPropagation();
      this._hideConfirm();
      return;
    }
    if (this._slideOpen) {
      e.stopPropagation();
      this._slideOpen = false;
      this._render();
    }
  }

  /* ---------- Click delegation ---------- */
  _handleClick(e) {
    // Remember the last clicked control of the slide-out (focus is restored
    // to it after a rebuild; iOS does not focus clicked buttons).
    const clicked = e.target && e.target.closest ? e.target.closest("[data-action], input, select, button") : null;
    if (clicked && clicked.closest(".slide-panel")) {
      const key = this._slideElKey(clicked);
      this._slideClick = key ? { key, t: Date.now() } : null;
    }
    // Tab clicks
    const tabBtn = e.target.closest("[data-tab]");
    if (tabBtn) {
      const tab = tabBtn.dataset.tab;
      this._confirmLeaveRule(() => this._confirmLeaveSettings(() => this._switchTab(tab)));
      return;
    }
    this._handleActionClick(e);
  }

  _switchTab(tab) {
    this._activeTab = tab;
    this._selectedCover = null;
    this._slideOpen = false;
    this._setExpandedRule(null);
    this._settingsDraft = null;
    this._editingFacade = null;
    this._addingCover = false;
    this._addingFacade = false;
    this._addingRule = false;
    this._addingScenario = false;
    this._editingScenario = null;
    this._logEntries = null;
    if (this._activeTab === "covers") {
      this._startLiveRefresh();
    } else {
      this._stopLiveRefresh();
    }
    this._stopCondPreview();
    this._render();
  }

  _handleActionClick(e) {
    // Route by data-action
    const actionEl = e.target.closest("[data-action]");
    if (!actionEl) return;
    const action = actionEl.dataset.action;

    switch (action) {
      case "toggle-menu":
        // Standard HA event (like ha-menu-button): opens the sidebar/drawer
        // without navigating away (unsaved drafts stay).
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "retry": this._loadConfig(); break;
      case "profile-scenario": this._onProfileScenario(actionEl); break;
      case "explain-toggle": {
        const d = actionEl.closest("details");
        this._explainOpen = this._explainOpen || {};
        this._explainOpen[actionEl.dataset.key] = d ? !d.open : false;
        break;
      }
      case "sun-explain-toggle": {
        // Native <details> toggles after the click: remember the new state
        const d = actionEl.closest("details");
        this._sunExplainOpen = d ? !d.open : false;
        break;
      }
      case "cover-add-start": this._addingCover = true; this._render(); break;
      case "cover-sort": {
        const key = actionEl.dataset.sort;
        if (this._coverSort.key === key) {
          this._coverSort.dir = this._coverSort.dir === "asc" ? "desc" : "asc";
        } else {
          this._coverSort = { key, dir: "asc" };
        }
        this._render();
        break;
      }
      case "cover-add-cancel": this._addingCover = false; this._render(); break;
      case "cover-add": this._onCoverAdd(); break;
      case "cover-resume": this._onCoverResume(actionEl.dataset.id); break;
      case "cover-delete": this._onCoverDelete(actionEl.dataset.id); break;
      case "select-cover":
        this._selectedCover = actionEl.dataset.id;
        this._slideOpen = true;
        this._expandedSections = { base: true };
        this._render();
        // Move focus into the slide-out so Tab order continues inside the dialog
        setTimeout(() => this.shadowRoot.querySelector(".slide-header .btn-icon")?.focus(), 0);
        break;
      case "goto-rule": {
        e.preventDefault();
        e.stopPropagation();
        const ruleId = actionEl.dataset.ruleId;
        this._activeTab = "rules";
        this._slideOpen = false;
        this._selectedCover = null;
        this._setExpandedRule(null);
        this._stopLiveRefresh();
        this._render();
        // Scroll-to + highlight after the new tab has rendered
        setTimeout(() => {
          if (!ruleId) return;
          const rEl = this.shadowRoot.querySelector('.rule-row[data-rule-id="' + CSS.escape(ruleId) + '"]');
          if (!rEl) return;
          rEl.scrollIntoView({ behavior: "smooth", block: "center" });
          rEl.classList.add("rule-highlight");
          setTimeout(() => rEl.classList.remove("rule-highlight"), 2000);
        }, 60);
        break;
      }
      case "close-slide":
        if (e.target === actionEl || actionEl.classList.contains("btn-icon")) {
          this._slideOpen = false;
          this._render();
        }
        break;
      case "toggle-section":
        {
          // Accordion: opening a section closes the others -- unless
          // several are open ("expand all"): then only this one toggles.
          const id = actionEl.dataset.section;
          const open = !this._expandedSections[id];
          const openCount = Object.values(this._expandedSections).filter(Boolean).length;
          if (openCount > 1) this._expandedSections = { ...this._expandedSections, [id]: open };
          else this._expandedSections = { [id]: open };
        }
        this._render();
        break;
      case "settings-section":
        // _render() keeps the unsaved inputs of the section left (settings draft)
        this._captureSettingsDraft();
        this._activeSettingsSection = actionEl.dataset.section;
        this._render();
        this._centerActiveSettingsPill();
        break;
      case "rotate-by": {
        const input = this.shadowRoot.querySelector("#house-rotation-input");
        if (!input) break;
        const setRaw = actionEl.dataset.set;
        if (setRaw !== undefined) {
          input.value = parseFloat(setRaw);
        } else {
          const cur = parseFloat(input.value);
          const base = Number.isFinite(cur) ? cur : 0;
          const delta = parseFloat(actionEl.dataset.delta || "0");
          let next = base + delta;
          // Normalize into -180..180
          while (next > 180) next -= 360;
          while (next < -180) next += 360;
          input.value = next;
        }
        input.dispatchEvent(new Event("input", { bubbles: true }));
        break;
      }
      case "facade-add-start": this._addingFacade = true; this._render(); break;
      case "facade-add-cancel": this._addingFacade = false; this._render(); break;
      case "facade-edit": this._editingFacade = actionEl.dataset.id; this._render(); break;
      case "facade-edit-cancel": this._editingFacade = null; this._render(); break;
      case "day-toggle": this._onDayToggle(actionEl); break;
      case "multiselect-toggle": this._onMultiselectToggle(actionEl); break;
      case "ha-ui": this._onHaUi(actionEl); break;
      case "ha-state-toggle": this._onHaStateToggle(actionEl); break;
      case "ha-state-add": this._onHaStateAdd(actionEl); break;
      case "cond-convert": this._onCondConvert(actionEl); break;
      case "cover-travel-reset": this._onCoverTravelReset(actionEl.dataset.id); break;
      case "cover-occ-toggle": {
        const v = actionEl.dataset.val;
        this._onOccupancyStates(actionEl.dataset.id, (list) => list.some(x => x.toLowerCase() === v.toLowerCase())
          ? list.filter(x => x.toLowerCase() !== v.toLowerCase()) : [...list, v]);
        break;
      }
      case "cover-occ-add": {
        const input = this.shadowRoot.querySelector(`[data-occ-other="${CSS.escape(actionEl.dataset.id)}"]`);
        const v = input ? input.value.trim() : "";
        if (v) this._onOccupancyStates(actionEl.dataset.id, (list) => list.some(x => x.toLowerCase() === v.toLowerCase()) ? list : [...list, v]);
        break;
      }
      case "sections-toggle-all": {
        const ids = (actionEl.dataset.ids || "").split(",").filter(Boolean);
        const allOpen = ids.every(id => this._expandedSections[id]);
        this._expandedSections = allOpen ? {} : Object.fromEntries(ids.map(id => [id, true]));
        this._render();
        break;
      }
      case "cover-occ-reset": this._onOccupancyStates(actionEl.dataset.id, () => null); break;
      case "facade-cover-toggle": actionEl.classList.toggle("selected"); break;
      case "facade-add-save": this._onFacadeAddSave(actionEl); break;
      case "facade-edit-save": this._onFacadeEditSave(actionEl); break;
      case "facade-delete": this._onFacadeDelete(actionEl.dataset.id); break;
      case "rule-expand": {
        const next = this._expandedRule === actionEl.dataset.id ? null : actionEl.dataset.id;
        this._confirmLeaveRule(() => {
          this._setExpandedRule(next);
          this._render();
          if (this._expandedRule) this._startCondPreview(); else this._stopCondPreview();
        });
        break;
      }
      case "rule-prio-up":
      case "rule-prio-down": this._onRuleMove(actionEl.dataset.id, action === "rule-prio-up" ? -1 : 1); break;
      case "rule-delete": this._onRuleDelete(actionEl.dataset.id); break;
      case "rule-duplicate": {
        const id = actionEl.dataset.id;
        this._confirmLeaveRule(() => this._onRuleDuplicate(id));
        break;
      }
      case "rule-save": this._onRuleSave(actionEl.dataset.id); break;
      case "rule-delete-condition": this._onRuleDeleteCondition(actionEl.dataset.rule, actionEl.dataset.idx); break;
      case "rule-cond-negate": this._onRuleCondNegate(actionEl); break;
      case "rule-cond-collapse": {
        const idx = parseInt(actionEl.dataset.idx, 10);
        this._setCondCollapsed(actionEl.dataset.rule, idx, !this._isCondCollapsed(actionEl.dataset.rule, idx));
        break;
      }
      case "rule-cond-collapse-all": this._onCondCollapseAll(actionEl.dataset.rule); break;
      case "rule-group-add": this._onRuleGroupAdd(actionEl.dataset.rule); break;
      case "rule-group-delete": this._onRuleGroupDelete(actionEl.dataset.rule, actionEl.dataset.group); break;
      case "rule-cond-up":
      case "rule-cond-down":
        this._onRuleCondReorder(actionEl.dataset.rule, parseInt(actionEl.dataset.idx, 10), action === "rule-cond-up" ? -1 : 1);
        break;
      case "rule-group-up":
      case "rule-group-down":
        this._onRuleGroupReorder(actionEl.dataset.rule, parseInt(actionEl.dataset.group, 10), action === "rule-group-up" ? -1 : 1);
        break;
      case "rule-facade-toggle":
      case "rule-scenario-toggle":
      case "rule-cover-toggle":
        actionEl.classList.toggle("selected");
        this._syncRuleDraftFromDom();
        if (action !== "rule-scenario-toggle") this._refreshRuleTilt(actionEl.dataset.rule);
        break;
      case "hint-toggle": {
        // Panel of the same row: shown or hidden, remembered across renders
        const key = actionEl.dataset.hint;
        this._openHints = this._openHints || new Set();
        const panel = this.shadowRoot.querySelector(`[data-hint-panel="${CSS.escape(key)}"]`);
        const open = !this._openHints.has(key);
        if (open) this._openHints.add(key); else this._openHints.delete(key);
        if (panel) panel.hidden = !open;
        actionEl.classList.toggle("open", open);
        actionEl.setAttribute("aria-expanded", open ? "true" : "false");
        break;
      }
      case "rule-add-start": this._addingRule = true; this._render(); break;
      case "rule-filter-clear":
        this._ruleFilter = { facade: "", cover: "", scenario: "" };
        this._render();
        break;
      case "rule-add-cancel": this._addingRule = false; this._render(); break;
      case "rule-add-save": this._onRuleAddSave(actionEl); break;
      case "scenario-add-start": this._addingScenario = true; this._render(); break;
      case "scenario-add-cancel": this._addingScenario = false; this._render(); break;
      case "scenario-edit": this._editingScenario = actionEl.dataset.id; this._render(); break;
      case "scenario-edit-cancel": this._editingScenario = null; this._render(); break;
      case "scenario-activate": this._onScenarioActivate(actionEl.dataset.id); break;
      case "scenario-add-save": this._onScenarioAddSave(actionEl); break;
      case "scenario-edit-save": this._onScenarioEditSave(actionEl); break;
      case "scenario-delete": this._onScenarioDelete(actionEl.dataset.id); break;
      case "scenario-icon-pick": this._onScenarioIconPick(actionEl); break;
      case "settings-save": this._onSettingsSave(); break;
      case "backup-export": this._onBackupExportClick(); break;
      case "backup-import": { const fi = this.shadowRoot.querySelector('[data-action="backup-file"]'); if (fi) fi.click(); break; }
      case "backup-file": this._onBackupFileSelected(actionEl); break;
      case "cover-show-log": {
        const id = actionEl.dataset.id;
        this._confirmLeaveRule(() => this._confirmLeaveSettings(() => {
          this._logCover = id || null;
          this._logFilter = null;
          this._switchTab("log");
        }));
        break;
      }
      case "log-filter":
        this._logFilter = actionEl.dataset.filter || null;
        this._render();
        break;
      case "log-clear":
        // The backend clears the whole log, even with a cover filter: say so
        this._showConfirm(this._t(this._logCover ? "log_clear_confirm_all" : "log_clear_confirm"), async () => {
          try {
            await this._ws("cover_automatic/log/clear");
            this._logSeq = (this._logSeq || 0) + 1;
            this._logLoading = false;
            this._logEntries = [];
            this._render();
          } catch (err) { console.error(err); this._showError(err); }
        });
        break;
      case "confirm-ok": {
        const cb = this._confirmCallback;
        this._hideConfirm();
        if (cb) cb();
        break;
      }
      case "confirm-cancel":
        if (e.target === actionEl) this._hideConfirm();
        break;
    }
  }

  /* ---------- Change delegation ---------- */
  _handleChange(e) {
    const el = e.target;

    // Threshold entity picked: show its current value right away
    if (el.matches("[data-threshold-entity]")) {
      const out = el.closest(".threshold-entity")?.querySelector(".threshold-entity-value");
      if (out) out.innerHTML = this._thresholdEntityValue(el.value.trim());
    }

    // Master toggle
    if (el.matches('[data-action="master-toggle"]')) {
      this._onMasterToggle(el.checked, el);
      return;
    }
    // Cover select (dropdown) changes
    if (el.matches('[data-action="cover-select"]')) {
      this._debouncedCoverSave(el.dataset.id, el.dataset.field, el.value || null);
      return;
    }

    // Activity log: one cover or all (reloaded from the backend so the
    // entry limit applies to that cover only)
    // Rules tab filter
    if (el.matches('[data-action="rule-filter"]')) {
      const key = el.dataset.filterKey;
      if (!(key in this._ruleFilter)) return;
      const value = el.value || "";
      const apply = () => {
        this._ruleFilter[key] = value;
        // The open rule is closed when the new filter no longer shows it
        const open = this._expandedRule && (this._config.rules || {})[this._expandedRule];
        const f = this._effectiveRuleFilter();
        if (open && Object.values(f).some(Boolean) && !this._ruleMatchesFilter(open, f)) {
          this._setExpandedRule(null);
          this._stopCondPreview();
        }
        this._render();
        this.shadowRoot.querySelector('[data-action="rule-filter"][data-filter-key="' + key + '"]')?.focus();
      };
      const next = { ...this._ruleFilter, [key]: value };
      const open = this._expandedRule && (this._config.rules || {})[this._expandedRule];
      const hides = open && Object.values(next).some(Boolean) && !this._ruleMatchesFilter(open, next);
      // Unsaved edits of a rule the filter would hide: confirm first (the
      // select goes back to its previous value when the user cancels)
      if (hides && this._ruleDraftDirty()) this._showConfirm(this._t("rule_unsaved_confirm"), apply, this._t("discard"));
      else apply();
      return;
    }

    if (el.matches('[data-action="log-cover"]')) {
      this._logCover = el.value || null;
      this._logEntries = null;
      this._render();
      return;
    }

    // Settings radio group: mirrored into its hidden draft field
    if (el.matches("[data-settings-radio]")) {
      const hidden = this.shadowRoot.querySelector(`[data-settings-field="${el.dataset.settingsRadio}"]`);
      if (hidden && el.checked) hidden.value = el.value;
      return;
    }

    // Cover tri-state select: "" = follow global (null)
    if (el.matches('[data-action="cover-tristate"]')) {
      const value = el.value === "true" ? true : (el.value === "false" ? false : null);
      this._debouncedCoverSave(el.dataset.id, el.dataset.field, value);
      return;
    }

    // Cover toggle (checkbox) changes
    if (el.matches('[data-action="cover-toggle"]')) {
      this._debouncedCoverSave(el.dataset.id, el.dataset.field, el.checked);
      if (el.dataset.field === "lock_hold_position") {
        // The lock position is not used while the cover keeps its position
        const pos = this.shadowRoot.querySelector(`[data-action="cover-input"][data-id="${CSS.escape(el.dataset.id)}"][data-field="lock_position"]`);
        if (pos) pos.disabled = el.checked;
      }
      return;
    }

    // Cover input (select elements also fire change)
    if (el.matches('[data-action="cover-input"]') && el.tagName === "SELECT") {
      let value = el.value;
      if (value === "") value = null;
      this._debouncedCoverSave(el.dataset.id, el.dataset.field, value);
      return;
    }

    // Rule enabled toggle
    if (el.matches('[data-action="rule-toggle-enabled"]')) {
      this._onRuleToggleEnabled(el.dataset.id, el.checked, el);
      return;
    }

    // Add condition type selector
    if (el.matches('[data-action="rule-add-condition-type"]')) {
      this._onRuleAddCondition(el.dataset.rule, el.value, parseInt(el.dataset.group, 10) || 0, el);
      return;
    }

    // Operator inside a condition group (kept locally until saved)
    if (el.matches('[data-action="rule-group-op"]')) {
      const rule = this._edRule(el.dataset.rule);
      if (rule) {
        const { ops } = this._ruleGroups(rule);
        ops[parseInt(el.dataset.group, 10) || 0] = el.value;
        rule.group_operators = ops;
        if (ops.length === 1) rule.condition_operator = el.value;
        this._refreshCondPreview();
      }
      return;
    }

    // Operator between groups: update the separators live
    if (el.matches('[data-action="rule-field"][data-field="condition_operator"]')) {
      const rule = this._edRule(el.dataset.id);
      if (rule) rule.condition_operator = el.value;
      this.shadowRoot.querySelectorAll(".cond-group-sep").forEach(sep => {
        sep.textContent = this._t(el.value === "or" ? "rule_op_short_or" : "rule_op_short_and");
      });
      return;
    }

    // Move a condition to another group
    if (el.matches('[data-action="rule-cond-group"]')) {
      this._onRuleCondMove(el.dataset.rule, parseInt(el.dataset.idx, 10), parseInt(el.value, 10) || 0, el);
      return;
    }

    // Condition param change
    if (el.matches('[data-action="cond-param"]')) {
      this._updateConditionParam(el);
      return;
    }

    // Native HA condition form
    if (el.matches('[data-action="ha-form"]')) {
      this._onHaFormChange(el, false);
      return;
    }

    // Backup file selected
    if (el.matches('[data-action="backup-file"]')) {
      this._onBackupFileSelected(el);
      return;
    }

    // Scenario rule toggle
    if (el.matches('[data-action="scenario-rule-toggle"]')) {
      this._onScenarioRuleToggle(el.dataset.scenario, el.dataset.rule, el.checked, el);
      return;
    }

    // Facade direction preset (applies house rotation to get real compass bearings)
    if (el.matches('[data-facade-field="direction"]')) {
      const form = el.closest(".inline-form");
      if (form && FACADE_BEARINGS[el.value] != null) {
        // Same prefill when creating and when editing a facade
        const span = this._facadeMaxSpan(el.value);
        const startInput = form.querySelector('[data-facade-field="azimuth_start"]');
        const endInput = form.querySelector('[data-facade-field="azimuth_end"]');
        if (startInput) startInput.value = span.start;
        if (endInput) endInput.value = span.end;
      }
      return;
    }
  }

  /* ---------- Input delegation ---------- */
  _handleInput(e) {
    const el = e.target;

    // Rule editor field marked invalid on save: unmark once corrected
    // (condition numbers are checked again just below).
    if (el.classList && el.classList.contains("input-invalid") && el.closest && el.closest(".rule-editor")
      && !this._fieldBadValidity(el) && !(el.dataset.field === "target_position" && el.value.trim() === "")) {
      this._setInputInvalid(el, null);
    }

    // Cover input fields (debounced save)
    if (el.matches('[data-action="cover-input"]')) {
      let value = el.value;
      if (el.type === "number") {
        const check = this._checkCoverNumber(el);
        if (!check.ok) {
          // Invalid or intermediate value: mark it and send nothing
          this._cancelCoverSave(`${el.dataset.id}.${el.dataset.field}`);
          return;
        }
        value = check.value;
      }
      if (el.type === "text" && value === "") value = null;
      this._debouncedCoverSave(el.dataset.id, el.dataset.field, value);
      return;
    }

    // Rule editor fields kept only in the DOM: mirror them into the draft
    if (el.matches('[data-action="rule-field"]')) {
      this._syncRuleDraftFromDom();
      return;
    }

    // Condition param input (live update local state)
    if (el.matches('[data-action="cond-param"]')) {
      this._updateConditionParam(el);
      return;
    }

    // Native HA condition: YAML editor and number fields (live)
    if (el.matches('[data-action="ha-yaml"]')) {
      this._onHaYamlInput(el);
      return;
    }
    if (el.matches('input[type="number"][data-action="ha-form"]')) {
      this._onHaFormChange(el, true);
      return;
    }

    // Live compass update
    if (el.id === "house-rotation-input") {
      const parsed = parseFloat(el.value);
      const val = Number.isFinite(parsed) ? parsed : 0;
      const svg = this.shadowRoot.querySelector("#compass-svg");
      if (svg && svg.parentElement) {
        svg.parentElement.innerHTML = this._renderCompassSVG(val);
      }
      return;
    }
  }

  // Native validity without stepMismatch: decimals like 25.5 or 0.5 min are
  // valid values even where the input has an integer step.
  _fieldBadValidity(el) {
    const v = el.validity;
    if (!v) return false;
    return !!(v.badInput || v.rangeUnderflow || v.rangeOverflow || v.valueMissing || v.typeMismatch || v.patternMismatch);
  }

  _setInputInvalid(el, message) {
    if (message) {
      el.classList.add("input-invalid");
      el.setAttribute("aria-invalid", "true");
      el.title = message;
    } else if (el.classList.contains("input-invalid")) {
      el.classList.remove("input-invalid");
      el.removeAttribute("aria-invalid");
      el.removeAttribute("title");
    }
  }
};

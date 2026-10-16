// CoverAutomatic panel -- Covers tab: table, live cells, position bars, cover saves.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).
import { COVER_INT_LIMITS } from "./constants.js";

export const CoversMixin = (Base) => class extends Base {
  /* ---------- Debounced save for covers ---------- */
  // field may be an object { field: value, ... } to save several at once
  //   hooks.onSettled(ok): called once the save finished (not when a newer
  //   edit of the same fields replaced it).
  _debouncedCoverSave(entityId, field, value, hooks = null) {
    const fields = typeof field === "object" && field !== null ? field : { [field]: value };
    const key = `${entityId}.${Object.keys(fields).join("+")}`;
    this._cancelCoverSave(key);
    const fn = async () => {
      try {
        const data = { entity_id: entityId, ...fields };
        const result = await this._ws("cover_automatic/cover/update", data);
        if (this._slideHasFocus()) {
          // The user is still typing in the slide-out: rebuilding it would
          // drop focus and keystrokes. Update the data, refresh everything
          // around it and patch the derived texts inside it.
          this._updateConfigFromResult(result, { render: false });
          this._refreshAroundSlideOut();
        } else {
          this._updateConfigFromResult(result);
        }
        if (hooks && hooks.onSettled) hooks.onSettled(true);
      } catch (e) {
        console.error("Save error:", e);
        this._showError(e);
        if (hooks && hooks.onSettled) hooks.onSettled(false);
      }
    };
    const timer = setTimeout(() => {
      if (this._saveTimers[key] && this._saveTimers[key].timer === timer) delete this._saveTimers[key];
      fn();
    }, 500);
    this._saveTimers[key] = { timer, fn };
  }

  _cancelCoverSave(key) {
    const pending = this._saveTimers[key];
    if (!pending) return;
    clearTimeout(pending.timer);
    delete this._saveTimers[key];
  }

  // Send every pending debounced cover edit right away.
  _flushCoverSaves() {
    const pending = Object.values(this._saveTimers || {});
    this._saveTimers = {};
    for (const p of pending) {
      clearTimeout(p.timer);
      p.fn();
    }
  }

  _posBar(pos, variant) {
    if (pos == null) return '\u2013';
    const p = Math.max(0, Math.min(100, pos));
    const cls = variant ? ' pos-bar-' + variant : '';
    return '<span class="pos-bar' + cls + '"><span class="pos-bar-track"><span class="pos-bar-fill" style="width:' + p + '%"></span></span><span class="pos-bar-label">' + pos + '%</span></span>';
  }

  // Current position in the rules' (logical) frame: inverted covers are
  // mirrored like the coordinator does. Returns { pos, raw } (raw = HA value).
  _coverCurrentPos(cover, haState) {
    let v = haState && haState.attributes ? haState.attributes.current_position : null;
    // Open/close-only covers: read the position from the state
    if (v == null && haState) v = { open: 100, closed: 0 }[haState.state] ?? null;
    const raw = v == null || v === "" || isNaN(Number(v)) ? null : Number(v);
    if (raw == null) return { pos: null, raw: null };
    return { pos: cover && cover.inverted ? 100 - raw : raw, raw };
  }

  // Position cell: current (logical) vs target, with the raw HA value in a
  // tooltip for inverted covers.
  _posCellHtml(cover, haState, target) {
    const { pos, raw } = this._coverCurrentPos(cover, haState);
    // Unknown current position (cover unavailable): don't draw the target
    // as if it were the current position.
    if (pos == null) return '\u2013';
    const bar = this._posBarCombined(pos, target);
    if (!(cover && cover.inverted) || raw == null) return bar;
    const tip = this._t("cover_position_inverted_tip").replace("{raw}", raw);
    return `<span class="pos-inverted" title="${this._esc(tip)}">${bar}<span class="pos-inverted-mark" aria-label="${this._esc(tip)}">\u21C5</span></span>`;
  }

  // Combined position bar: single column shows current + target with a marker when they differ
  _posBarCombined(current, target) {
    if (current == null && target == null) return '\u2013';
    const diverges = current != null && target != null && Math.abs(current - target) >= 1;
    if (!diverges) {
      const p = current ?? target;
      return this._posBar(p);
    }
    // Two-stop fill: solid up to min(current,target), striped from min to max, empty beyond.
    // The solid portion is the position that is "guaranteed" reached; the striped portion is the delta in flux.
    const c = Math.max(0, Math.min(100, current));
    const t = Math.max(0, Math.min(100, target));
    const lo = Math.min(c, t);
    const hi = Math.max(c, t);
    const rangeWidth = hi - lo;
    const title = this._t("cover_position_target_label") + this._colon() + target + "%";
    return '<span class="pos-bar pos-bar-diverges" title="' + this._esc(title) + '">'
      + '<span class="pos-bar-track">'
        + '<span class="pos-bar-fill" style="width:' + lo + '%"></span>'
        + '<span class="pos-bar-range" style="left:' + lo + '%;width:' + rangeWidth + '%"></span>'
      + '</span>'
      + '<span class="pos-bar-label"><span class="pos-bar-current-val">' + current + '%</span><span class="pos-bar-arrow">\u2192</span><span class="pos-bar-target-val">' + target + '%</span></span>'
    + '</span>';
  }

  _renderRuleCell(live) {
    const ruleId = live && live.rule_id;
    const ruleName = (live && live.rule_name) || this._t("cover_no_rule");
    if (ruleId && this._config && this._config.rules && this._config.rules[ruleId]) {
      return '<a class="rule-link" data-action="goto-rule" data-rule-id="' + this._esc(ruleId) + '" title="' + this._esc(this._t("cover_goto_rule")) + '">' + this._esc(ruleName) + '</a>'
        + (this._config.rules[ruleId].safety ? this._ruleSafetyIcon() : "");
    }
    return this._esc(ruleName);
  }

  // Red shield shown after the name of a safety rule (cover list).
  _ruleSafetyIcon() {
    return '<span class="rule-safety-icon" title="' + this._esc(this._t("rule_safety")) + '">' + this._lucideIcon("shield", 13) + '</span>';
  }

  // Room temperature cell of the cover list: text colour, icon and tooltip
  // for the comfort mode. The icon (snowflake / sun thermometer) carries the
  // meaning; the colours follow the chosen convention: "action" (default:
  // cold room red = to heat, hot room blue = to cool) or thermometer (cold
  // blue, hot red).
  _tempCellParts(cm, tempVal) {
    const cold = cm === "heating", hot = cm === "cooling";
    const thermo = (this._config?.settings || {}).temp_color_thermometer === true;
    const red = "var(--ca-danger)", blue = "var(--ca-info)";
    const color = cold ? (thermo ? blue : red) : hot ? (thermo ? red : blue) : "";
    const icon = cold || hot
      ? '<span class="temp-icon" aria-hidden="true">' + this._lucideIcon(cold ? "thermometer_snowflake" : "thermometer_sun", 14) + '</span>'
      : "";
    const text = tempVal != null ? tempVal.toFixed(1) + " \u00B0C" : "\u2013";
    return { color, html: icon + this._esc(text), title: cm ? this._t("comfort_" + cm) : "" };
  }

  /* ============================================================
   * TAB: Covers
   * ============================================================ */
  _renderCovers() {
    const covers = this._config.covers || {};
    const entries = Object.values(covers);
    const available = this._config.available_covers || [];

    let html = '';

    // Collapsible add covers section
    if (available.length > 0) {
      if (this._addingCover) {
        html += '<div class="card mb-16"><div class="card-header">';
        html += `<span>${this._t("cover_add")}</span>`;
        html += `<button class="btn-icon" data-action="cover-add-cancel" title="${this._t("cancel")}">&#10005;</button>`;
        html += '</div>';
        html += '<div class="card-body"><div class="form-row">';
        html += `<select id="cover-add-select" class="add-cover-select" multiple>`;
        for (const a of available) {
          html += `<option value="${this._esc(a.entity_id)}">${this._esc(a.name)} (${this._esc(a.entity_id)})</option>`;
        }
        html += '</select></div>';
        html += `<div class="form-row mt-8"><button class="btn btn-primary" data-action="cover-add">${this._t("add")}</button></div>`;
        html += '</div></div>';
      } else {
        html += `<div class="mb-12"><button class="btn btn-sm" data-action="cover-add-start">+ ${this._t("cover_add")}</button></div>`;
      }
    }

    if (entries.length === 0 && !this._addingCover) {
      return html + `<div class="empty-state">${this._t("none")}</div>`;
    }

    html += '<div class="card"><div class="table-scroll"><table class="data-table">';
    html += '<thead><tr>';
    const sk = this._coverSort.key, sd = this._coverSort.dir;
    const sth = (key, label) => {
      const active = sk === key;
      const arrow = active ? (sd === "asc" ? "\u25B2" : "\u25BC") : "\u2195";
      const ariaSort = active ? ` aria-sort="${sd === "asc" ? "ascending" : "descending"}"` : "";
      return `<th class="sortable${active ? " sorted" : ""}" data-action="cover-sort" data-sort="${key}" tabindex="0"${ariaSort}>${label}<span class="sort-arrow">${arrow}</span></th>`;
    };
    html += sth("name", this._t("name"));
    html += sth("facade", this._t("cover_facade"));
    html += sth("status", this._t("cover_status"));
    html += sth("temp", this._t("cover_temp"));
    html += `<th>${this._t("cover_position")}</th>`;
    html += `<th>${this._t("cover_rule")}</th>`;
    html += `<th>${this._t("cover_last_change")}</th>`;
    html += '<th class="row-chevron-head" aria-hidden="true"></th>';
    html += '</tr></thead><tbody>';

    // Sort entries
    const sorted = [...entries].sort((a, b) => {
      let va, vb;
      switch (sk) {
        case "name": va = a.name || ""; vb = b.name || ""; break;
        case "facade": va = this._getFacadeName(a.facade_id); vb = this._getFacadeName(b.facade_id); break;
        case "status": va = a.status || "auto"; vb = b.status || "auto"; break;
        case "temp": {
          const sa = a.indoor_temp_sensor || (this._config.settings || {}).indoor_temp_sensor;
          const sb = b.indoor_temp_sensor || (this._config.settings || {}).indoor_temp_sensor;
          const ta = sa && this._hass?.states && this._hass.states[sa] ? parseFloat(this._hass.states[sa].state) : -999;
          const tb = sb && this._hass?.states && this._hass.states[sb] ? parseFloat(this._hass.states[sb].state) : -999;
          va = isNaN(ta) ? -999 : ta; vb = isNaN(tb) ? -999 : tb;
          return sd === "asc" ? va - vb : vb - va;
        }
        default: va = a.name || ""; vb = b.name || "";
      }
      const cmp = String(va).localeCompare(String(vb), "de", { sensitivity: "base" });
      return sd === "asc" ? cmp : -cmp;
    });

    for (const c of sorted) {
      const facadeName = this._getFacadeName(c.facade_id);
      const selected = this._selectedCover === c.entity_id ? " selected" : "";
      const statusClass = "status-" + (c.status || "auto");
      const haState = this._hass?.states ? this._hass.states[c.entity_id] : null;
      const live = (this._config.live_covers || {})[c.entity_id] || {};
      const targetPos = live.target_position;
      const hysteresis = live.hysteresis;
      let infoIcon = '';
      if (hysteresis === "position") {
        infoIcon = ' <span class="status-badge status-paused hysteresis-badge" title="' + this._esc(this._t("cover_hysteresis_position")) + '">&#8597;</span>';
      } else if (hysteresis === "time") {
        infoIcon = ' <span class="status-badge status-paused hysteresis-badge" title="' + this._esc(this._t("cover_hysteresis_time")) + '">&#9202;</span>';
      }
      const cm = live.comfort_mode;
      // Rule name -- if a rule is matching, render as link to Rules tab
      const ruleCellHtml = this._renderRuleCell(live);
      // Sun on facade
      const liveFacade = c.facade_id ? ((this._config.live_facades || {})[c.facade_id] || {}) : {};
      const sunIcon = liveFacade.sun_on_facade ? ' <span class="live-icon-sun" title="' + this._esc(this._t("facade_sun_active")) + '">' + this._sunIconSvg(12) + '</span>' : '';
      // Last change
      const lastChange = live.last_change ? this._formatTimeAgo(live.last_change) : "";
      // Pause info
      const pauseLeft = (c.status === "paused" && live.pause_until) ? this._formatPauseRemaining(live.pause_until) : "";
      const resumeBtn = c.status === "paused" ? '<button class="btn-icon resume-x" data-action="cover-resume" data-id="' + this._esc(c.entity_id) + '" title="' + this._esc(this._t("cover_resume")) + '">&#10005;</button>' : '';
      html += `<tr class="${selected}" data-action="select-cover" data-id="${this._esc(c.entity_id)}" tabindex="0">`;
      html += `<td data-live-name="${this._esc(c.entity_id)}">${this._esc(c.name)}</td>`;
      html += `<td class="nowrap" data-live-facade="${this._esc(c.entity_id)}">${this._esc(facadeName)}${sunIcon}</td>`;
      html += `<td class="nowrap" data-live-status="${this._esc(c.entity_id)}"><span class="status-badge ${statusClass}">${this._esc(this._t("status_" + (c.status || "auto")) || c.status || "auto")}</span>${pauseLeft ? '<span class="pause-remaining">' + pauseLeft + '</span>' : ''}${resumeBtn}</td>`;
      const tempSensor = c.indoor_temp_sensor || (this._config.settings || {}).indoor_temp_sensor;
      const tempState = tempSensor && this._hass?.states ? this._hass.states[tempSensor] : null;
      const tempVal = tempState && tempState.state !== "unavailable" && tempState.state !== "unknown" ? parseFloat(tempState.state) : null;
      const tp = this._tempCellParts(cm, tempVal);
      html += `<td class="nowrap${tp.color ? ' temp-mode' : ''}" data-live-temp="${this._esc(c.entity_id)}"${tp.color ? ' style="color:' + tp.color + '"' : ''}${tp.title ? ' title="' + this._esc(tp.title) + '"' : ''}>${tp.html}</td>`;
      html += `<td class="pos-cell" data-live-position="${this._esc(c.entity_id)}">${this._posCellHtml(c, haState, targetPos)}${infoIcon}</td>`;
      html += `<td data-live-rule="${this._esc(c.entity_id)}">${ruleCellHtml}</td>`;
      html += `<td class="last-change" data-live-lastchange="${this._esc(c.entity_id)}">${lastChange}</td>`;
      html += '<td class="row-chevron" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg></td>';
      html += '</tr>';
    }

    html += '</tbody></table></div></div>';
    return html;
  }

  _renderCoverEntitySelect(field, currentValue, coverId, domain, deviceClass) {
    if (!this._hass || !this._hass.states) return `<input type="text" value="${this._esc(currentValue || "")}" data-action="cover-input" data-id="${this._esc(coverId)}" data-field="${field}">`;
    const entities = Object.values(this._hass.states)
      .filter(s => {
        const domains = Array.isArray(domain) ? domain : [domain];
        if (!domains.some(d => s.entity_id.startsWith(d + "."))) return false;
        if (deviceClass && s.attributes.device_class !== deviceClass) return false;
        return true;
      })
      .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id));
    let html = `<select data-action="cover-input" data-id="${this._esc(coverId)}" data-field="${field}">`;
    html += `<option value="">-- ${this._t("none")} --</option>`;
    for (const e of entities) {
      const name = e.attributes.friendly_name || e.entity_id;
      const sel = e.entity_id === currentValue ? " selected" : "";
      html += `<option value="${this._esc(e.entity_id)}"${sel}>${this._esc(name)} (${this._esc(e.entity_id)})</option>`;
    }
    // A configured entity outside the filter (other device class, not loaded
    // yet, removed) stays shown and selected instead of reading as "none".
    if (currentValue && !entities.some(e => e.entity_id === currentValue)) {
      html += `<option value="${this._esc(currentValue)}" selected>${this._esc(currentValue)}</option>`;
    }
    html += "</select>";
    return html;
  }

  _updateLiveCells() {
    const root = this.shadowRoot;
    if (!root || !this._config) return;
    const covers = this._config.covers || {};
    const liveCvrs = this._config.live_covers || {};
    for (const eid of Object.keys(covers)) {
      // Combined position cell: current + target with optional divergence marker, plus hysteresis badge
      const haState = this._hass?.states ? this._hass.states[eid] : null;
      const live = liveCvrs[eid] || {};
      const tgtPos = live.target_position;
      const hyst = live.hysteresis;
      const posCell = root.querySelector('[data-live-position="' + CSS.escape(eid) + '"]');
      if (posCell) {
        let barHtml = this._posCellHtml(covers[eid], haState, tgtPos);
        if (hyst === "position" || hyst === "time") {
          barHtml += ' <span class="status-badge status-paused hysteresis-badge" title="' + this._esc(this._t(hyst === "position" ? "cover_hysteresis_position" : "cover_hysteresis_time")) + '">' + (hyst === "position" ? "\u2195" : "\u23F2") + '</span>';
        }
        posCell.innerHTML = barHtml;
      }
      // Status + pause remaining + resume button
      const c = covers[eid];
      const sCell = root.querySelector('[data-live-status="' + CSS.escape(eid) + '"]');
      if (sCell && c) {
        const st = c.status || "auto";
        const badge = sCell.querySelector(".status-badge");
        if (badge) {
          badge.className = "status-badge status-" + st;
          badge.textContent = this._t("status_" + st) || st;
        }
        let pauseSpan = sCell.querySelector(".pause-remaining");
        let resumeBtn = sCell.querySelector(".resume-x");
        if (st === "paused") {
          if (live.pause_until) {
            const txt = this._formatPauseRemaining(live.pause_until);
            if (txt) {
              if (!pauseSpan) {
                pauseSpan = document.createElement("span");
                pauseSpan.className = "pause-remaining";
                sCell.appendChild(pauseSpan);
              }
              pauseSpan.textContent = txt;
            } else if (pauseSpan) {
              pauseSpan.remove();
            }
          }
          if (!resumeBtn) {
            resumeBtn = document.createElement("button");
            resumeBtn.className = "btn-icon resume-x";
            resumeBtn.dataset.action = "cover-resume";
            resumeBtn.dataset.id = eid;
            resumeBtn.title = this._t("cover_resume");
            resumeBtn.textContent = "\u2715";
            sCell.appendChild(resumeBtn);
          }
        } else {
          if (pauseSpan) pauseSpan.remove();
          if (resumeBtn) resumeBtn.remove();
        }
      }
      // Cover name
      const nCell = root.querySelector('[data-live-name="' + CSS.escape(eid) + '"]');
      if (nCell && c) {
        nCell.textContent = c.name;
      }
      // Facade name + sun icon
      const fCell = root.querySelector('[data-live-facade="' + CSS.escape(eid) + '"]');
      if (fCell && c) {
        const facadeName = this._getFacadeName(c.facade_id);
        const liveFacade = c.facade_id ? ((this._config.live_facades || {})[c.facade_id] || {}) : {};
        fCell.textContent = "";
        fCell.appendChild(document.createTextNode(facadeName));
        if (liveFacade.sun_on_facade) {
          const sun = document.createElement("span");
          sun.className = "live-icon-sun";
          sun.title = this._t("facade_sun_active");
          // SVG from internal _sunIconSvg() - no user input
          sun.innerHTML = this._sunIconSvg(12);
          fCell.appendChild(document.createTextNode(" "));
          fCell.appendChild(sun);
        }
      }
      // Rule name -- preserve clickable rule-link markup via DOM API (avoids innerHTML)
      const rCell = root.querySelector('[data-live-rule="' + CSS.escape(eid) + '"]');
      if (rCell) {
        rCell.textContent = "";
        const ruleId = live.rule_id;
        const ruleName = live.rule_name || this._t("cover_no_rule");
        if (ruleId && this._config && this._config.rules && this._config.rules[ruleId]) {
          const a = document.createElement("a");
          a.className = "rule-link";
          a.dataset.action = "goto-rule";
          a.dataset.ruleId = ruleId;
          a.title = this._t("cover_goto_rule");
          a.textContent = ruleName;
          rCell.appendChild(a);
          if (this._config.rules[ruleId].safety) {
            // Markup from internal _ruleSafetyIcon() - no user input besides the escaped label
            rCell.insertAdjacentHTML("beforeend", this._ruleSafetyIcon());
          }
        } else {
          rCell.textContent = ruleName;
        }
      }
      // Temperature with comfort color
      const tempCell = root.querySelector('[data-live-temp="' + CSS.escape(eid) + '"]');
      if (tempCell) {
        const c2 = covers[eid];
        const ts = (c2 && c2.indoor_temp_sensor) || ((this._config.settings || {}).indoor_temp_sensor);
        const tst = ts && this._hass?.states ? this._hass.states[ts] : null;
        const tv = tst && tst.state !== "unavailable" && tst.state !== "unknown" ? parseFloat(tst.state) : null;
        const tp = this._tempCellParts(live.comfort_mode, tv);
        if (tempCell.innerHTML !== tp.html) tempCell.innerHTML = tp.html;
        tempCell.style.color = tp.color;
        tempCell.classList.toggle("temp-mode", !!tp.color);
        tempCell.title = tp.title;
      }
      // Last change
      const lcCell = root.querySelector('[data-live-lastchange="' + CSS.escape(eid) + '"]');
      if (lcCell) lcCell.textContent = live.last_change ? this._formatTimeAgo(live.last_change) : "";
    }
  }

  _formatTimeAgo(ts) {
    const sec = Math.max(0, Math.round(Date.now() / 1000 - ts));
    if (sec < 60) return this._t("cover_just_now");
    const min = Math.floor(sec / 60);
    if (min < 60) return this._t("time_ago_min").replace("{n}", min);
    const h = Math.floor(min / 60);
    const m = min % 60;
    if (m === 0) return this._t("time_ago_h").replace("{n}", h);
    return this._t("time_ago_h_m").replace("{h}", h).replace("{m}", m);
  }

  _formatPauseRemaining(pauseUntil) {
    const remaining = Math.max(0, Math.round(pauseUntil - Date.now() / 1000));
    if (remaining <= 0) return "";
    const min = Math.floor(remaining / 60);
    const sec = remaining % 60;
    return "(" + min + ":" + (sec < 10 ? "0" : "") + sec + ")";
  }

  _startLiveRefresh() {
    this._stopLiveRefresh();
    this._refreshLiveCovers();
    this._liveRefreshTimer = setInterval(() => this._refreshLiveCovers(), 60000);
  }

  _stopLiveRefresh() {
    if (this._liveRefreshTimer) {
      clearInterval(this._liveRefreshTimer);
      this._liveRefreshTimer = null;
    }
  }

  async _refreshLiveCovers() {
    if (!this._config || this._activeTab !== "covers") {
      this._stopLiveRefresh();
      return;
    }
    // Drop stale answers: a newer refresh was started, or the config was
    // replaced (save, import...) while this request was running.
    const seq = this._liveSeq = (this._liveSeq || 0) + 1;
    const epoch = this._cfgEpoch || 0;
    try {
      const result = await this._ws("cover_automatic/config");
      if (seq !== this._liveSeq || epoch !== (this._cfgEpoch || 0) || !this._config) return;
      if (result) {
        if (result.live_covers) this._config.live_covers = result.live_covers;
        if (result.live_facades) this._config.live_facades = result.live_facades;
        if (result.active_rules) this._config.active_rules = result.active_rules;
        if (result.covers) this._config.covers = result.covers;
        this._updateLiveCells();
      }
    } catch (e) { /* silent */ }
  }

  /* ---------- Action handlers ---------- */
  async _onCoverResume(entityId) {
    try {
      const result = await this._ws("cover_automatic/cover/resume", { entity_id: entityId });
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }

  async _onCoverAdd() {
    const select = this.shadowRoot.querySelector("#cover-add-select");
    if (!select) return;
    const ids = Array.from(select.selectedOptions).map(o => o.value);
    if (ids.length === 0) return;
    try {
      const result = await this._ws("cover_automatic/cover/add", { entity_ids: ids });
      this._addingCover = false;
      this._updateConfigFromResult(result);
      this._showToast();
    } catch (e) { console.error(e); this._showError(e); }
  }

  _onCoverDelete(entityId) {
    this._showConfirm(this._t("confirm_delete"), async () => {
      try {
        const result = await this._ws("cover_automatic/cover/delete", { entity_id: entityId });
        if (this._selectedCover === entityId) { this._selectedCover = null; this._slideOpen = false; }
        this._updateConfigFromResult(result);
      } catch (e) { console.error(e); this._showError(e); }
    });
  }

  // Validate a cover number input against the cover/update schema.
  // Returns { ok, value } (value null = cleared, falls back to the default).
  _checkCoverNumber(el) {
    const lim = COVER_INT_LIMITS[el.dataset.field];
    if (el.value === "" && !(el.validity && el.validity.badInput)) {
      this._setInputInvalid(el, null);
      return { ok: true, value: null };
    }
    const n = el.value === "" ? NaN : Number(el.value);
    let msg = null;
    if (!Number.isFinite(n)) msg = this._t("input_invalid_number");
    else if (lim && (!Number.isInteger(n) || n < lim[0] || n > lim[1])) {
      msg = this._t("input_invalid_range").replace("{min}", lim[0]).replace("{max}", lim[1]);
    }
    this._setInputInvalid(el, msg);
    return msg ? { ok: false, value: null } : { ok: true, value: n };
  }
};

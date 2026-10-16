// CoverAutomatic panel -- Cover sheet (slide-out panel) and its sections.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).

export const SlideCoverMixin = (Base) => class extends Base {
  _slideHasFocus() {
    const a = this.shadowRoot && this.shadowRoot.activeElement;
    return !!(this._slideOpen && a && a.closest && a.closest(".slide-panel"));
  }

  // Re-render everything except the slide-out, then update the texts inside
  // the slide-out that derive from the saved values (focus stays intact).
  _refreshAroundSlideOut() {
    const shell = this.shadowRoot.querySelector(".panel-container");
    if (!shell || !shell.querySelector("[data-region]")) return;
    this._updateRegion(shell, "header", this._renderHeaderContent());
    this._updateRegion(shell, "content", this._renderContent());
    const cover = (this._config.covers || {})[this._selectedCover];
    if (!cover) { this._render(); return; }
    const info = this._travelInfo(cover);
    const id = CSS.escape(cover.entity_id);
    const input = shell.querySelector(`[data-action="cover-input"][data-id="${id}"][data-field="travel_time"]`);
    if (input) input.placeholder = info.placeholder;
    const used = shell.querySelector(`[data-travel-used="${id}"]`);
    if (used) used.textContent = info.usedTxt;
  }

  // Travel-time texts of a cover: placeholder, measured value, effective value.
  _travelInfo(cover) {
    const num = (v) => (typeof v === "number" && v > 0 ? v : null);
    const measured = num(cover.measured_travel_time);
    const manual = num(cover.travel_time);
    const globalTravel = num(this._config.settings?.default_travel_time);
    const fmtS = (v) => String(Math.round(v));
    const placeholder = measured != null
      ? this._t("cover_travel_auto_measured").replace("{s}", fmtS(measured))
      : (globalTravel != null ? this._t("cover_travel_auto_default").replace("{s}", fmtS(globalTravel)) : this._t("cover_travel_auto"));
    // Effective value, same order as the integration: entered > measured > default
    let used = null, usedSrc = "none";
    if (manual != null) { used = manual; usedSrc = "manual"; }
    else if (measured != null) { used = measured; usedSrc = "measured"; }
    else if (globalTravel != null) { used = globalTravel; usedSrc = "default"; }
    const settle = used != null ? Math.max(30, used + 5) : 30;
    const usedTxt = (used != null
      ? this._t("cover_travel_used").replace("{s}", fmtS(used)).replace("{src}", this._t("cover_travel_src_" + usedSrc))
      : this._t("cover_travel_used_none")).replace("{wait}", fmtS(settle));
    return { measured, placeholder, usedTxt, fmtS };
  }

  /* ---------- Slide-out: keep scroll position and focus ---------- */
  // Structure of the slide-out HTML without the parts that are patched in
  // place (control values, placeholders, section summaries, travel text).
  _slideSig(html) {
    return String(html)
      .replace(/\s(?:value|placeholder)="[^"]*"/g, "")
      .replace(/\s(?:checked|selected|disabled)(?=[\s>])/g, "")
      .replace(/(<span class="section-summary">)[^<]*(<\/span>)/g, "$1$2")
      .replace(/(data-travel-used="[^"]*">)[^<]*(<\/div>)/g, "$1$2");
  }

  // Selector finding "the same" element again after a rebuild.
  _slideElKey(el) {
    if (!el || !el.tagName) return null;
    const attrs = ["data-action", "data-id", "data-field", "data-section", "data-val", "data-occ-other", "data-ids", "id", "name"];
    let sel = el.tagName.toLowerCase();
    let any = false;
    for (const a of attrs) {
      const v = el.getAttribute(a);
      if (v != null) { sel += `[${a}="${CSS.escape(v)}"]`; any = true; }
    }
    if (el.type === "radio" && el.value) sel += `[value="${CSS.escape(el.value)}"]`;
    return any ? sel : null;
  }

  _updateSlideOutRegion(el, html) {
    const prevHtml = this._slideHtml;
    this._slideHtml = html;
    const oldPanel = el.querySelector(".slide-panel");
    const oldCover = oldPanel && oldPanel.classList.contains("open") ? oldPanel.dataset.cover : null;
    const sameCover = !!(oldCover && this._slideOpen && this._selectedCover === oldCover);
    if (!sameCover) { el.innerHTML = html; return; }
    if (prevHtml === html) return; // nothing changed: keep the DOM as is
    if (prevHtml != null && this._slideSig(prevHtml) === this._slideSig(html)) {
      this._patchSlideOut(el, prevHtml, html);
      return;
    }
    // Structural change: rebuild, then restore scroll and focus.
    const body = el.querySelector(".slide-body");
    const scroll = body ? body.scrollTop : 0;
    const active = this.shadowRoot.activeElement;
    let key = null, selStart = null, selEnd = null;
    if (active && el.contains(active)) {
      key = this._slideElKey(active);
      try { selStart = active.selectionStart; selEnd = active.selectionEnd; } catch (e) { /* not a text field */ }
    } else if (this._slideClick && Date.now() - this._slideClick.t < 2000) {
      // iOS Safari does not focus clicked buttons: use the last click instead
      key = this._slideClick.key;
    }
    el.innerHTML = html;
    const nbody = el.querySelector(".slide-body");
    if (nbody) nbody.scrollTop = scroll;
    if (key) {
      let target = null;
      try { target = el.querySelector(key); } catch (e) { target = null; }
      if (target) {
        try { target.focus({ preventScroll: true }); } catch (e) { target.focus(); }
        if (selStart != null) { try { target.setSelectionRange(selStart, selEnd); } catch (e) { /* ignore */ } }
        if (nbody) nbody.scrollTop = scroll;
      }
    }
  }

  // Same structure: update only what differs between the previous and the
  // new HTML. Controls the user is editing (focused, pending save, invalid)
  // keep their value.
  _patchSlideOut(el, prevHtml, html) {
    const parse = (h) => { const t = document.createElement("template"); t.innerHTML = h; return t.content; };
    const oldT = parse(prevHtml), newT = parse(html);
    const active = this.shadowRoot.activeElement;
    const pendingKeys = Object.keys(this._saveTimers || {});
    const pending = (id, field) => pendingKeys.some(k => k.startsWith(id + ".") && k.slice(id.length + 1).split("+").includes(field));
    const ctrlState = (c) => {
      if (!c) return null;
      if (c.tagName === "SELECT") {
        const o = c.querySelector("option[selected]") || c.querySelector("option");
        return o ? (o.getAttribute("value") ?? o.textContent) : "";
      }
      if (c.type === "checkbox" || c.type === "radio") return c.hasAttribute("checked");
      return c.getAttribute("value") ?? "";
    };
    for (const nc of newT.querySelectorAll("input, select, textarea")) {
      const key = this._slideElKey(nc);
      if (!key) continue;
      const oc = oldT.querySelector(key);
      const live = el.querySelector(key);
      if (!oc || !live) continue;
      const ph = nc.getAttribute("placeholder");
      if (ph !== oc.getAttribute("placeholder")) { if (ph == null) live.removeAttribute("placeholder"); else live.setAttribute("placeholder", ph); }
      const nv = ctrlState(nc);
      if (nv === ctrlState(oc)) continue;
      if (live === active) {
        // Focused control keeps what it shows; the new server value is
        // applied on blur if the user did not change it (_onSlideFocusOut).
        const dom = typeof nv === "boolean" ? live.checked : live.value;
        live._caStale = { value: nv, dom: live._caStale ? live._caStale.dom : dom };
        continue;
      }
      if (live.classList.contains("input-invalid")) continue;
      if (live.dataset.id && live.dataset.field && pending(live.dataset.id, live.dataset.field)) continue;
      delete live._caStale;
      if (typeof nv === "boolean") live.checked = nv; else live.value = nv;
    }
    for (const ns of newT.querySelectorAll(".section-header[data-section]")) {
      const sel = `.section-header[data-section="${CSS.escape(ns.dataset.section)}"] .section-summary`;
      const n = ns.querySelector(".section-summary");
      const live = el.querySelector(sel);
      if (n && live && live.textContent !== n.textContent) live.textContent = n.textContent;
    }
    for (const nt of newT.querySelectorAll("[data-travel-used]")) {
      const live = el.querySelector(`[data-travel-used="${CSS.escape(nt.dataset.travelUsed)}"]`);
      if (live && live.textContent !== nt.textContent) live.textContent = nt.textContent;
    }
  }

  // A slide-out control skipped by _patchSlideOut while focused: once blurred,
  // show the server value unless the user changed it meanwhile.
  _onSlideFocusOut(e) {
    const el = e.target;
    if (!el || !el._caStale) return;
    const stale = el._caStale;
    delete el._caStale;
    if (!el.isConnected || !el.closest || !el.closest(".slide-panel")) return;
    if (el.classList.contains("input-invalid")) return;
    const pendingKeys = Object.keys(this._saveTimers || {});
    const id = el.dataset.id, field = el.dataset.field;
    if (id && field && pendingKeys.some(k => k.startsWith(id + ".") && k.slice(id.length + 1).split("+").includes(field))) return;
    if (typeof stale.value === "boolean") {
      if (el.checked === stale.dom) el.checked = stale.value;
    } else if (el.value === stale.dom) {
      el.value = stale.value;
    }
  }

  /* ---------- Slide-out for cover editing ---------- */
  _renderSlideOut() {
    const open = this._slideOpen && this._selectedCover;
    const cover = open ? (this._config.covers || {})[this._selectedCover] : null;

    let html = `<div class="slide-overlay${open ? " open" : ""}" data-action="close-slide" aria-hidden="true"></div>`;
    html += `<div class="slide-panel${open ? " open" : ""}"${cover ? ` data-cover="${this._esc(cover.entity_id)}"` : ""}${cover ? ` role="dialog" aria-modal="true" aria-label="${this._esc(cover.name)}"` : ' aria-hidden="true"'}>`;

    if (cover) {
      html += `<div class="slide-header">
        <button class="btn-icon slide-back" data-action="close-slide" title="${this._t("close")}" aria-label="${this._t("close")}">&#8592;</button>
        <h2>${this._esc(cover.name)}</h2>
        <button class="btn-icon slide-close" data-action="close-slide" title="${this._t("close")}" aria-label="${this._t("close")}">&#10005;</button>
      </div>`;
      html += '<div class="slide-body">';

      const cid = this._esc(cover.entity_id);
      const cs = this._config.settings || {};
      const ctl = (field) => `[data-field="${field}"][data-id="${cover.entity_id.replace(/["\\]/g, "\\$&")}"]`;
      const sum = this._coverSectionSummaries(cover);
      const allIds = ["base", "window", "room", "sun", "automation"];
      const allOpen = allIds.every(id => this._expandedSections[id]);
      html += `<div class="slide-expand-bar"><button type="button" class="btn-link" data-action="sections-toggle-all" data-ids="${allIds.join(",")}">${
        this._t(allOpen ? "cover_collapse_all" : "cover_expand_all")}</button></div>`;

      // Section: General
      html += this._renderSection("base", this._t("cover_section_base"), () => {
        const items = [
          this._renderToggle("cover_auto_enabled", cover.auto_enabled, "cover-toggle", cover.entity_id, "auto_enabled"),
          this._renderFacadeDropdown(cover) + this._hint("cover_facade_hint"),
          this._renderToggle("cover_inverted", cover.inverted, "cover-toggle", cover.entity_id, "inverted", "cover_inverted_hint"),
        ];
        if (cover.supports_tilt) {
          items.push(this._renderToggle("cover_inverted_tilt", cover.inverted_tilt, "cover-toggle", cover.entity_id, "inverted_tilt"));
        }
        return this._sepList(items);
      }, sum.base);

      // Section: Window (open = lock, tilted = ventilation)
      html += this._renderSection("window", this._t("cover_section_window"), () => {
        let s = '';
        const globalLockPos = cs.lock_position ?? 100;
        const lockTilt = cover.supports_tilt ? `<div class="form-group">
                <label>${this._t("cover_lock_tilt")}</label>
                <input type="number" min="0" max="100" value="${this._num(cover.lock_tilt_position, "")}" placeholder="${this._t("none")}" data-action="cover-input" data-id="${cid}" data-field="lock_tilt_position">
              </div>` : "";
        s += this._optBox({
          title: this._t("cover_lock_box_title"),
          dep: ctl("lock_sensor"), mode: "value",
          head: `<div class="form-group">
            <label>${this._t("cover_lock_sensor")}</label>
            ${this._renderCoverEntitySelect("lock_sensor", cover.lock_sensor, cover.entity_id, "binary_sensor", null)}
            ${this._renderSensorValue(cover.lock_sensor)}
            ${this._hint("cover_lock_sensor_hint")}
          </div>`,
          offNote: this._t("cover_lock_off_note"),
          body: `${this._renderToggle("cover_lock_hold", !!cover.lock_hold_position, "cover-toggle", cover.entity_id, "lock_hold_position", "cover_lock_hold_hint")}
            ${this._optBox({
              cls: "opt-box-flat",
              dep: ctl("lock_hold_position"), mode: "unchecked",
              body: `<div class="form-group">
                <label>${this._t("cover_lock_position")}</label>
                <input type="number" min="0" max="100" value="${this._num(cover.lock_position, "")}" placeholder="${globalLockPos}" data-action="cover-input" data-id="${cid}" data-field="lock_position">
                ${this._hint("cover_lock_position_hint")}
              </div>${lockTilt}`,
            })}`,
        });
        const globalVentPos = cs.vent_position ?? 30;
        const ventTilt = cover.supports_tilt ? `<div class="form-group">
            <label>${this._t("cover_vent_tilt")}</label>
            <input type="number" min="0" max="100" value="${this._num(cover.vent_tilt_position, "")}" placeholder="${this._t("none")}" data-action="cover-input" data-id="${cid}" data-field="vent_tilt_position">
          </div>` : "";
        s += this._optBox({
          title: this._t("cover_vent_box_title"),
          dep: ctl("vent_sensor"), mode: "value",
          head: `<div class="form-group">
            <label>${this._t("cover_vent_sensor")}</label>
            ${this._renderCoverEntitySelect("vent_sensor", cover.vent_sensor, cover.entity_id, "binary_sensor", null)}
            ${this._renderSensorValue(cover.vent_sensor)}
            ${this._hint("cover_vent_sensor_hint")}
          </div>`,
          offNote: this._t("cover_vent_off_note"),
          body: `<div class="form-group">
            <label>${this._t("cover_vent_position")}</label>
            <input type="number" min="0" max="100" value="${this._num(cover.vent_position, "")}" placeholder="${globalVentPos}" data-action="cover-input" data-id="${cid}" data-field="vent_position">
            ${this._hint("cover_vent_position_hint")}
          </div>${ventTilt}`,
        });
        return s;
      }, sum.window);

      // Section: Room (indoor temperature setpoints + occupancy)
      html += this._renderSection("room", this._t("cover_section_room"), () => {
        let s = '';
        // Own setpoints per comfort profile; empty = global value of the profile
        const field = (p, base) => p === "b" ? base + "_b" : base;
        const note = (v) => `<div class="ha-help">${this._esc(this._t("cover_default_note").replace("{v}", v + " °C"))}</div>`;
        const profile = (p) => {
          const g = this._profileValues(p, true);
          const names = this._profileScenarioNames(p, true);
          const input = (base, value, step, extra = "") => `<input type="number" step="${step}"${extra} value="${this._num(cover[field(p, base)], "")}" placeholder="${value}" data-action="cover-input" data-id="${cid}" data-field="${field(p, base)}">`;
          // Own value mixed with a global one changed since: min >= max. The
          // engine then uses the global pair of the profile.
          const effMin = cover[field(p, "comfort_temp_min")] ?? g.min;
          const effMax = cover[field(p, "comfort_temp_max")] ?? g.max;
          const invalid = effMin >= effMax;
          return `<div class="cover-profile${names ? "" : " profile-unused"}">
            <div class="cover-profile-title">${this._esc(this._t("profile_title").replace("{p}", p.toUpperCase()))}
              <span class="radio-hint">${this._esc(names || this._t("profile_no_scenario"))}</span></div>
            ${invalid ? `<div class="cover-profile-warn">${this._lucideIcon("info", 14)} ${this._esc(this._t("cover_profile_invalid")
              .replace("{min}", effMin).replace("{max}", effMax).replace("{gmin}", g.min).replace("{gmax}", g.max))}</div>` : ""}
            <div class="form-row">
              <div class="form-group">
                <label>${this._L("cover_comfort_min")}</label>
                ${input("comfort_temp_min", g.min, "0.5")}
                ${note(g.min)}
              </div>
              <div class="form-group">
                <label>${this._L("cover_comfort_max")}</label>
                ${input("comfort_temp_max", g.max, "0.5")}
                ${note(g.max)}
              </div>
            </div>
            <div class="form-group">
              <label>${this._L("cover_comfort_hysteresis")}</label>
              ${input("comfort_hysteresis", g.h, "0.1", ' min="0.1" max="5"')}
              ${note(g.h)}
            </div>
          </div>`;
        };
        s += this._optBox({
          title: this._t("settings_comfort_range_title"),
          body: `<div class="form-group">
            <label>${this._L("cover_indoor_temp")}</label>
            ${this._renderCoverEntitySelect("indoor_temp_sensor", cover.indoor_temp_sensor, cover.entity_id, "sensor", "temperature")}
            ${this._renderSensorValue(cover.indoor_temp_sensor)}
            ${this._hint("cover_indoor_temp_hint")}
          </div>
          ${profile("a")}${profile("b")}
          ${this._hint("cover_comfort_hint")}`,
        });
        s += this._optBox({
          title: this._t("cover_occupancy_box_title"),
          dep: ctl("occupancy_sensor"), mode: "value",
          head: `<div class="form-group">
            <label>${this._t("cover_occupancy_sensor")}</label>
            ${this._renderCoverEntitySelect("occupancy_sensor", cover.occupancy_sensor, cover.entity_id,
              ["binary_sensor", "input_boolean", "input_select", "person", "device_tracker"], null)}
            ${this._renderSensorValue(cover.occupancy_sensor)}
            ${this._hint("cover_occupancy_sensor_hint")}
          </div>`,
          offNote: this._t("cover_occupancy_off_note"),
          body: this._renderOccupancyStates(cover),
        });
        return s;
      }, sum.room);

      // Section: Automation (per-cover overrides of Settings › Automation)
      html += this._renderSection("automation", this._t("cover_section_automation"), () => {
        let s = '';
        const globalPause = cs.pause_duration ?? 10;
        s += `<div class="form-group">
          <label>${this._t("cover_pause_duration")}</label>
          <input type="number" min="1" max="480" value="${this._num(cover.pause_duration)}" placeholder="${globalPause}" data-action="cover-input" data-id="${cid}" data-field="pause_duration">
          <div class="ha-help">${this._esc(this._t("cover_default_note").replace("{v}", globalPause + " min"))}</div>
          ${this._hint("cover_pause_duration_hint")}
        </div>`;
        s += this._renderCoverTristate(cover, "pause_resume_on_match", "pause_resume_on_match", "pause_resume_on_match_hint");
        const globalMinChange = cs.min_position_change ?? 5;
        s += `<div class="form-group">
          <label>${this._L("cover_min_pos_change")}</label>
          <input type="number" min="1" max="50" value="${this._num(cover.min_position_change, "")}" placeholder="${globalMinChange}" data-action="cover-input" data-id="${cid}" data-field="min_position_change">
          <div class="ha-help">${this._esc(this._t("cover_default_note").replace("{v}", globalMinChange + " %"))}</div>
          ${this._hint("cover_min_pos_change_hint")}
        </div>`;
        const globalMinTime = cs.min_time_between_changes ?? 300;
        s += `<div class="form-group">
          <label>${this._L("cover_min_time")}</label>
          <input type="number" min="60" max="3600" value="${this._num(cover.min_time_between_changes, "")}" placeholder="${globalMinTime}" data-action="cover-input" data-id="${cid}" data-field="min_time_between_changes">
          <div class="ha-help">${this._esc(this._t("cover_default_note").replace("{v}", globalMinTime + " s"))}</div>
          ${this._hint("cover_min_time_hint")}
        </div>`;
        const { measured, placeholder: travelPlaceholder, usedTxt, fmtS } = this._travelInfo(cover);
        s += `<div class="form-group">
          <label>${this._t("cover_travel_time")}</label>
          <input type="number" min="1" max="300" value="${this._num(cover.travel_time, "")}" placeholder="${this._esc(travelPlaceholder)}" data-action="cover-input" data-id="${cid}" data-field="travel_time">
          <div class="ha-help">${measured != null
            ? `${this._esc(this._t("cover_travel_measured").replace("{s}", fmtS(measured)))}
               <button type="button" class="btn-link" data-action="cover-travel-reset" data-id="${cid}">${this._t("cover_travel_reset")}</button>`
            : this._esc(this._t("cover_travel_not_measured"))}</div>
          <div class="ha-help" data-travel-used="${cid}">${this._esc(usedTxt)}</div>
          ${this._hint("cover_travel_time_hint")}
        </div>`;
        return `<div class="sep-list">${s}</div>`;
      }, sum.automation);

      html += `<div class="slide-log-link">
        <button class="btn btn-secondary btn-sm" data-action="cover-show-log" data-id="${this._esc(cover.entity_id)}">${this._t("cover_show_log")}</button>
      </div>`;
      html += `<div class="slide-close-bottom">
        <button class="btn btn-secondary" data-action="close-slide">${this._t("close")}</button>
      </div>`;
      html += `<div class="slide-delete-wrap">
        <button class="btn btn-danger" data-action="cover-delete" data-id="${this._esc(cover.entity_id)}">${this._t("cover_remove")}</button>
      </div>`;
      html += '</div>'; // slide-body
    }

    html += '</div>'; // slide-panel
    return html;
  }

  _renderSection(id, title, contentFn, summary = "") {
    const expanded = this._expandedSections[id];
    const arrowClass = expanded ? "arrow expanded" : "arrow";
    const iconMap = { base: "info", window: "app_window", automation: "cog", room: "house", sun: "sun",
      sensors: "gauge", advanced: "sliders", tilt: "move_vertical" };
    const iconName = iconMap[id];
    const icon = iconName ? `<span class="section-icon">${this._lucideIcon(iconName, 16)}</span>` : "";
    return `<div class="section">
      <div class="section-header" data-action="toggle-section" data-section="${id}" tabindex="0" role="button" aria-expanded="${expanded ? "true" : "false"}">
        ${icon}<span class="section-title">${this._esc(title)}${summary && !expanded
          ? `<span class="section-summary">${this._esc(summary)}</span>` : ""}</span>
        <span class="${arrowClass}">&#9654;</span>
      </div>
      <div class="section-body${expanded ? " expanded" : ""}">
        ${contentFn()}
      </div>
    </div>`;
  }

  // Per-cover select: Global (follow settings) or one of the three modes
  // States meaning "occupied" when the cover sets none (mirror of the engine)
  static get OCCUPIED_DEFAULTS() {
    return ["on", "home", "present", "présent", "occupied", "occupé", "detected", "true", "1"];
  }

  // Occupied states of a cover: its own list, else the defaults (null)
  _occupancyOwnStates(cover) {
    // An edit not confirmed by the server yet is shown over the stored value
    const pend = this._occPending;
    const raw = pend && cover.entity_id in pend ? pend[cover.entity_id] : cover.occupancy_states;
    return raw && String(raw).trim() ? String(raw).split(",").map(x => x.trim()).filter(Boolean) : null;
  }

  // State buttons like the rule editor: the sensor's possible states, the
  // selected ones meaning "occupied".
  _renderOccupancyStates(cover) {
    const cid = this._esc(cover.entity_id);
    const stateObj = cover.occupancy_sensor && this._hass?.states ? this._hass.states[cover.occupancy_sensor] : null;
    const own = this._occupancyOwnStates(cover);
    const defaults = this.constructor.OCCUPIED_DEFAULTS;
    const known = this._haKnownStates(stateObj, null);
    (own || []).forEach(v => { if (!known.some(k => k.toLowerCase() === v.toLowerCase())) known.push(v); });
    const isSel = (v) => own
      ? own.some(o => o.toLowerCase() === v.toLowerCase())
      : defaults.includes(v.toLowerCase());
    let html = `<div class="form-group"><label>${this._t("cover_occupancy_states")}</label><div class="day-select">`;
    for (const v of known) {
      html += `<button type="button" class="day-btn${isSel(v) ? " selected" : ""}" data-action="cover-occ-toggle" data-id="${cid}" data-val="${this._esc(v)}" title="${this._esc(v)}">${this._esc(this._haStateLabel(stateObj, null, v))}</button>`;
    }
    html += `</div>`;
    if (!own) html += `<div class="ha-help">${this._esc(this._t("cover_occupancy_default_note"))}</div>`;
    html += `<div class="ha-add-state"><input type="text" placeholder="${this._esc(this._t("ha_state_other"))}" data-occ-other="${cid}">
        <button type="button" class="btn btn-secondary" data-action="cover-occ-add" data-id="${cid}">${this._t("ha_state_add")}</button></div>
      ${own ? `<div class="ha-help"><button type="button" class="btn-link" data-action="cover-occ-reset" data-id="${cid}">${this._t("cover_occupancy_reset")}</button></div>` : ""}
      ${this._hint("cover_occupancy_states_hint")}</div>`;
    return html;
  }

  _onOccupancyStates(entityId, update) {
    const cover = (this._config.covers || {})[entityId];
    if (!cover) return;
    const stateObj = cover.occupancy_sensor && this._hass?.states ? this._hass.states[cover.occupancy_sensor] : null;
    // Start from what is shown selected (explicit list, else the matching defaults)
    let list = this._occupancyOwnStates(cover)
      || this._haKnownStates(stateObj, null).filter(v => this.constructor.OCCUPIED_DEFAULTS.includes(v.toLowerCase()));
    list = update(list);
    const value = list && list.length ? list.join(", ") : null;
    // Not written into the config before the server confirms: shown through
    // _occPending, dropped (stored value shown again) if the save fails.
    if (!this._occPending) this._occPending = {};
    this._occPending[entityId] = value;
    this._render();
    this._debouncedCoverSave(entityId, "occupancy_states", value, {
      onSettled: (ok) => {
        if (!this._occPending || this._occPending[entityId] !== value) return; // newer edit pending
        delete this._occPending[entityId];
        if (!ok) this._render();
      },
    });
  }

  // One-line summaries shown under collapsed section titles of the cover sheet
  _coverSectionSummaries(cover) {
    const s = this._config.settings || {};
    const sep = " · ";
    const facade = cover.facade_id && this._config.facades ? this._config.facades[cover.facade_id] : null;
    const base = [
      this._t(cover.auto_enabled === false ? "cover_sum_auto_off" : "cover_sum_auto_on"),
      facade ? facade.name : this._t("cover_sum_no_facade"),
    ];
    if (cover.inverted) base.push(this._t("cover_inverted"));

    const win = [];
    if (cover.lock_sensor) {
      win.push(this._t("cover_sum_open").replace("{v}", cover.lock_hold_position
        ? this._t("cover_sum_hold")
        : (cover.lock_position ?? s.lock_position ?? 100) + " %"));
    }
    if (cover.vent_sensor) {
      win.push(this._t("cover_sum_tilted").replace("{v}", (cover.vent_position ?? s.vent_position ?? 30) + " %"));
    }

    const auto = [this._t("cover_sum_pause").replace("{n}", cover.pause_duration ?? s.pause_duration ?? 10)];
    const travel = [cover.travel_time, cover.measured_travel_time, s.default_travel_time]
      .find(v => typeof v === "number" && v > 0);
    if (travel) auto.push(this._t("cover_sum_travel").replace("{n}", Math.round(travel)));
    const own = ["pause_duration", "min_position_change", "min_time_between_changes", "travel_time"]
      .filter(k => cover[k] != null).length;
    auto.push(own ? this._t("cover_sum_own").replace("{n}", own) : this._t("cover_sum_all_global"));

    const room = [];
    const indoor = cover.indoor_temp_sensor || s.indoor_temp_sensor;
    room.push(indoor
      ? this._haEntityName(indoor) + (cover.indoor_temp_sensor ? "" : " (" + this._t("cover_sum_global") + ")")
      : this._t("cover_sum_no_indoor"));
    const band = (p) => {
      const g = this._profileValues(p, true), sfx = p === "b" ? "_b" : "";
      return p.toUpperCase() + " " + (cover["comfort_temp_min" + sfx] ?? g.min) + " / " + (cover["comfort_temp_max" + sfx] ?? g.max);
    };
    room.push(band("a") + " · " + band("b") + " °C");
    if (cover.occupancy_sensor) room.push(this._haEntityName(cover.occupancy_sensor));

    return {
      base: base.join(sep),
      window: win.length ? win.join(sep) : this._t("cover_sum_no_window"),
      automation: auto.join(sep),
      room: room.join(sep),
    };
  }

  // Select "Global (value) / On / Off" for a nullable per-cover flag
  _renderCoverTristate(cover, field, labelKey, hintKey) {
    const own = cover[field];
    const globalOn = (this._config.settings || {})[field] !== false;
    const onOff = (on) => this._t(on ? "tristate_on" : "tristate_off");
    const opt = (value, label, selected) =>
      `<option value="${value}"${selected ? " selected" : ""}>${this._esc(label)}</option>`;
    return `<div class="form-group">
      <label>${this._L(labelKey)}</label>
      <select data-action="cover-tristate" data-id="${this._esc(cover.entity_id)}" data-field="${field}">
        ${opt("", this._t("tristate_global").replace("{value}", onOff(globalOn)), own == null)}
        ${opt("true", onOff(true), own === true)}
        ${opt("false", onOff(false), own === false)}
      </select>
      ${this._hint(hintKey)}
    </div>`;
  }

  async _onCoverTravelReset(entityId) {
    try {
      const result = await this._ws("cover_automatic/cover/update", { entity_id: entityId, measured_travel_time: null });
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }
};

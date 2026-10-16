// CoverAutomatic panel -- core: lifecycle, config loading, rendering shell, shared helpers.
import { I18N } from "./i18n.js";
import { PANEL_STYLES } from "./styles.js";

export class PanelCore extends HTMLElement {
  constructor() {
    super();
    this._initialized = false;
    this._delegationBound = false;
    this._hass = null;
    this._panel = null;
    this._config = null;
    this._activeTab = "covers";
    this._selectedCover = null;
    this._slideOpen = false;
    this._expandedRule = null;
    this._editingFacade = null;
    this._addingFacade = false;
    this._addingRule = false;
    this._addingCover = false;
    this._addingScenario = false;
    this._editingScenario = null;
    this._confirmCallback = null;
    this._confirmMessage = "";
    this._toastTimer = null;
    this._saveTimers = {};
    this._dragRuleId = null;
    this._dragOverId = null;
    this._error = null;
    this._latestVersion = null;
    this._upToDate = false;
    this._logEntries = null;
    this._logFilter = null;
    this._logCover = null;
    this._ruleFilter = { facade: "", cover: "", scenario: "" };
    this._coverSort = { key: "name", dir: "asc" };
    this._liveRefreshTimer = null;
    this._condPreviewTimer = null;
    this._eventUnsub = null;
    this._eventDebounce = null;
    this._expandedSections = { base: true };
    this._activeSettingsSection = "house";
    this._keydownListener = (e) => this._handleKeyDown(e);
    // Warn before closing/reloading the page with unsaved rule or settings edits
    this._beforeUnloadListener = (e) => {
      let dirty = false;
      try { dirty = this._ruleDraftDirty() || this._settingsDirty(); } catch (err) { dirty = false; }
      // Debounced cover edits not sent yet: send them now and warn
      // (the page may still close before they reach the server).
      if (this._saveTimers && Object.keys(this._saveTimers).length) {
        dirty = true;
        try { this._flushCoverSaves(); } catch (err) { /* ignore */ }
      }
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    // Working copy of the rule open in the editor ({ id, rule }); every editor
    // change goes here and only reaches _config once saved.
    this._ruleDraft = null;
    // Unsaved settings inputs (field -> { kind, value }), kept across sections.
    this._settingsDraft = null;
    this._haTimers = {};
    this._haInflight = {};
    this._previewSeq = 0;
    this._subscribing = null;
    this._confirmOkLabel = null;


    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    const prevHass = this._hass;
    const prevLang = prevHass?.language;
    this._hass = hass;
    if (!this._initialized) {
      this._initialize();
      return;
    }
    if (hass && hass.language !== prevLang) {
      this._render();
      return;
    }
    // HA assigns a new hass object on every state change anywhere in the
    // system. Only re-render when an entity this panel displays changed.
    if (!this._relevantStatesChanged(prevHass, hass)) return;
    if (this._config) {
      const shell = this.shadowRoot ? this.shadowRoot.querySelector(".panel-container") : null;
      // Only the info bar depends on HA states: patch it alone so the rest
      // of the header (master switch, focus) is not rebuilt.
      if (shell) this._patchInfoBar(shell);
      if (this._activeTab === "covers") this._updateLiveCells();
    }
  }

  _relevantEntityIds() {
    const ids = new Set(["sun.sun"]);
    const cfg = this._config;
    if (!cfg) return ids;
    const s = cfg.settings || {};
    for (const key of ["outdoor_temp_sensor", "indoor_temp_sensor", "weather_entity", "solar_sensor", "wind_sensor", "workday_sensor",
      "solar_threshold_entity"]) {
      if (s[key]) ids.add(s[key]);
    }
    for (const [eid, c] of Object.entries(cfg.covers || {})) {
      ids.add(eid);
      for (const key of ["lock_sensor", "vent_sensor", "indoor_temp_sensor", "occupancy_sensor"]) {
        if (c && c[key]) ids.add(c[key]);
      }
    }
    return ids;
  }

  _relevantStatesChanged(prevHass, hass) {
    if (!prevHass || !hass || !prevHass.states || !hass.states) return true;
    for (const id of this._relevantEntityIds()) {
      if (prevHass.states[id] !== hass.states[id]) return true;
    }
    return false;
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    // Window-level so Escape works regardless of where focus sits
    window.addEventListener("keydown", this._keydownListener);
    window.addEventListener("beforeunload", this._beforeUnloadListener);
    // Re-attach subscriptions when the element is re-inserted (HA caches
    // custom panels and detaches/re-attaches them on navigation). _initialize
    // only runs once, so without this the real-time event push and the live
    // refresh stay dead after the first disconnect. Both calls are idempotent.
    if (this._initialized) {
      this._subscribeUpdates();
      if (this._activeTab === "covers") this._startLiveRefresh();
      if (this._activeTab === "rules" && this._expandedRule) this._startCondPreview();
    }
  }

  disconnectedCallback() {
    window.removeEventListener("keydown", this._keydownListener);
    window.removeEventListener("beforeunload", this._beforeUnloadListener);
    this._stopLiveRefresh();
    this._stopCondPreview();
    this._unsubscribeUpdates();
    this._removeHouseDragListeners();
    // Send pending debounced cover edits now instead of dropping them.
    this._flushCoverSaves();
    // Pending HA-condition validations only refresh the (now hidden) editor.
    for (const t of Object.values(this._haTimers || {})) clearTimeout(t);
    this._haTimers = {};
    if (this._toastTimer) { clearTimeout(this._toastTimer); this._toastTimer = null; }
  }

  /* ---------- i18n helper ---------- */
  _t(key) {
    const lang = (this._hass?.language) || "en";
    const dict = I18N[lang] || I18N.en;
    return dict[key] !== undefined ? dict[key] : (I18N.en[key] !== undefined ? I18N.en[key] : key);
  }

  // Label separator: French typography puts a (narrow no-break) space before ":"
  _colon() {
    const lang = (this._hass?.language) || "en";
    return lang.startsWith("fr") ? "\u202F: " : ": ";
  }

  _tt(section, key) {
    const lang = (this._hass?.language) || "en";
    const dict = I18N[lang] || I18N.en;
    const s = dict[section] || I18N.en[section] || {};
    return s[key] !== undefined ? s[key] : ((I18N.en[section] || {})[key] || key);
  }

  // ⓘ button placed in a label; its text is a separate panel spanning the
  // whole row (_hintPanel), so compact rows keep their layout.
  _hintToggle(scope, key) {
    if (this._t(key) === key) return "";
    const id = this._esc(scope + ":" + key);
    const open = this._openHints && this._openHints.has(scope + ":" + key);
    return `<button type="button" class="hint-btn${open ? " open" : ""}" data-action="hint-toggle" data-hint="${id}" title="${this._esc(this._t("show_hint"))}" aria-label="${this._esc(this._t("show_hint"))}" aria-expanded="${open ? "true" : "false"}">${this._lucideIcon("info", 14)}</button>`;
  }

  _hintPanel(scope, key) {
    const text = this._t(key);
    if (text === key) return "";
    const open = this._openHints && this._openHints.has(scope + ":" + key);
    return `<div class="hint-body hint-panel" data-hint-panel="${this._esc(scope + ":" + key)}"${open ? "" : " hidden"}>${this._esc(text)}</div>`;
  }

  _hint(key) {
    const text = this._t(key);
    if (text === key) return "";
    return `<details class="field-hint"><summary title="${this._t("show_hint")}" aria-label="${this._t("show_hint")}">${this._lucideIcon("info", 14)}</summary><div class="hint-body">${this._esc(text)}</div></details>`;
  }

  /* ---------- Lifecycle ---------- */
  _initialize() {
    this._initialized = true;
    this._subscribeUpdates();
    this._loadConfig();
  }

  _subscribeUpdates() {
    // _subscribing: a subscription request is in flight (a quick
    // disconnect/reconnect must not open a second one).
    if (this._eventUnsub || this._subscribing || !this._hass) return;
    // Dedicated WebSocket subscription (no bus event, so nothing is written
    // to the recorder database on every update cycle).
    const pending = this._hass.connection.subscribeMessage(() => {
      if (!this.isConnected || this._activeTab !== "covers" || !this._config) return;
      // Debounce 500 ms, but refresh at least every 3 s while events keep coming
      const now = Date.now();
      if (!this._eventDebounceStart) this._eventDebounceStart = now;
      if (this._eventDebounce) clearTimeout(this._eventDebounce);
      const wait = Math.max(0, Math.min(500, this._eventDebounceStart + 3000 - now));
      this._eventDebounce = setTimeout(() => {
        this._eventDebounce = null;
        this._eventDebounceStart = null;
        this._refreshLiveCovers();
      }, wait);
    }, { type: "cover_automatic/subscribe" });
    this._subscribing = pending;
    Promise.resolve(pending).then((unsub) => {
      if (this._subscribing === pending) this._subscribing = null;
      // Disconnected while the request was pending (or already subscribed):
      // release it right away instead of leaking it.
      if (!this.isConnected || this._eventUnsub) {
        try { const r = unsub(); if (r && r.catch) r.catch(() => {}); } catch (e) { /* ignore */ }
        return;
      }
      this._eventUnsub = unsub;
    }).catch((err) => {
      if (this._subscribing === pending) this._subscribing = null;
      console.warn("CoverAutomatic: failed to subscribe to update events", err);
    });
  }

  _unsubscribeUpdates() {
    if (this._eventUnsub) {
      this._eventUnsub();
      this._eventUnsub = null;
    }
    if (this._eventDebounce) {
      clearTimeout(this._eventDebounce);
      this._eventDebounce = null;
    }
    this._eventDebounceStart = null;
  }

  /* ---------- WebSocket calls ---------- */
  async _ws(type, data) {
    if (!this._hass) return null;
    try {
      const msg = { type, ...(data ?? {}) };
      const result = await this._hass.callWS(msg);
      return result;
    } catch (err) {
      console.error("CoverAutomatic WS error:", type, err);
      throw err;
    }
  }

  async _loadConfig() {
    this._error = null;
    this._render();
    try {
      this._config = await this._ws("cover_automatic/config");
      this._cfgEpoch = (this._cfgEpoch || 0) + 1;
      if (this._activeTab === "covers") this._startLiveRefresh();
      this._render();
      this._checkForUpdate();
    } catch (e) {
      this._error = e.message || String(e);
      this._render();
    }
  }

  async _checkForUpdate() {
    if (!this._config || !this._config.version) return;
    if (this._config.settings && this._config.settings.update_check_enabled === false) return;
    try {
      const resp = await fetch("https://api.github.com/repos/slemeur91/CoverAutomatic/releases/latest", { headers: { Accept: "application/vnd.github.v3+json" } });
      if (!resp.ok) return;
      const data = await resp.json();
      const latest = (data.tag_name || "").replace(/^v/, "");
      if (!latest) return;
      if (this._compareVersions(latest, this._config.version) > 0) this._latestVersion = latest;
      // Latest published release is not newer than the installed version
      else this._upToDate = true;
      this._updateRegion(this.shadowRoot.querySelector(".panel-container"), "header", this._renderHeaderContent());
    } catch (e) { /* silent */ }
  }

  // Compare dotted numeric versions: >0 if a is newer than b, <0 if older.
  _compareVersions(a, b) {
    const pa = String(a).split(/[.-]/).map(x => parseInt(x, 10));
    const pb = String(b).split(/[.-]/).map(x => parseInt(x, 10));
    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
      const x = Number.isFinite(pa[i]) ? pa[i] : 0;
      const y = Number.isFinite(pb[i]) ? pb[i] : 0;
      if (x !== y) return x > y ? 1 : -1;
    }
    return 0;
  }

  // Apply a configuration returned by a WebSocket call.
  //   opts.resetDraft: the open rule was just saved -> restart its draft from
  //                    the saved version.
  //   opts.render:     false = update the data only (caller patches the DOM).
  //   opts.haLive:     with resetDraft, live HA validation results to keep for
  //                    the open rule, keyed by condition index.
  _updateConfigFromResult(result, opts = {}) {
    if (!result) return;
    // Capture unsaved DOM-only editor fields before the editor is rebuilt.
    if (!opts.resetDraft) this._syncRuleDraftFromDom();
    // The backend renamed the rule id after a name change: the open editor
    // and its per-rule state follow the new id.
    const renamed = result.renamed_rule;
    if (renamed && renamed.from && renamed.to && renamed.from !== renamed.to
      && (result.rules || {})[renamed.to]) {
      this._followRuleRename(renamed.from, renamed.to);
    }
    this._config = result;
    // Live refreshes started before this config are outdated (see _refreshLiveCovers)
    this._cfgEpoch = (this._cfgEpoch || 0) + 1;
    // Settings changed on the server (import, other window): keep only the
    // inputs really edited here, the others show the new stored values.
    this._captureSettingsDraft();
    if (this._settingsDraft) {
      // The settings inputs still show the old values until the next render:
      // do not capture them again (they would overwrite the new ones).
      this._settingsDomStale = true;
      for (const [field, d] of Object.entries(this._settingsDraft)) {
        if (this._draftSame(d)) delete this._settingsDraft[field];
        else d.initial = undefined; // re-read from the next render
      }
    }
    // The open rule no longer exists (deleted or renamed elsewhere)
    if (this._expandedRule && !(result.rules || {})[this._expandedRule]) this._expandedRule = null;
    const d = this._ruleDraft;
    let keepLive = false;
    if (d) {
      const saved = (result.rules || {})[d.id];
      if (!saved || this._expandedRule !== d.id) {
        this._discardRuleDraft();
      } else if (opts.resetDraft) {
        this._ruleDraft = { id: d.id, rule: this._clone(saved) };
      } else {
        keepLive = true; // unrelated change: the open rule keeps its draft
      }
    }
    // Live validation results belong to the draft's conditions; keep them
    // only while that draft is kept as is.
    const live = {};
    if (keepLive && this._haLive) {
      const pre = d.id + ":";
      for (const [k, v] of Object.entries(this._haLive)) if (k.startsWith(pre)) live[k] = v;
    }
    if (opts.haLive && this._ruleDraft) {
      for (const [i, v] of Object.entries(opts.haLive)) live[this._ruleDraft.id + ":" + i] = v;
    }
    this._haLive = live;
    this._showToast();
    if (opts.render === false) return;
    this._noDomSync = !!opts.resetDraft;
    try { this._render(); } finally { this._noDomSync = false; }
  }

  // Move every piece of per-rule editor state from one rule id to another.
  _followRuleRename(from, to) {
    const moveKey = (k) => (k.startsWith(from + ":") ? to + k.slice(from.length) : k);
    if (this._expandedRule === from) this._expandedRule = to;
    if (this._ruleDraft && this._ruleDraft.id === from) {
      this._ruleDraft.id = to;
      if (this._ruleDraft.rule) this._ruleDraft.rule.id = to;
    }
    if (this._collapsedConds) this._collapsedConds = new Set([...this._collapsedConds].map(moveKey));
    if (this._haLive) {
      const next = {};
      for (const [k, v] of Object.entries(this._haLive)) next[moveKey(k)] = v;
      this._haLive = next;
    }
    const restart = [];
    // Running validations were started for the old id: their results are
    // dropped (see _runHaValidate), so they run again for the new id.
    for (const k of Object.keys(this._haInflight || {})) {
      if (k.startsWith(from + ":")) restart.push(parseInt(k.slice(from.length + 1), 10));
    }
    for (const [k, t] of Object.entries(this._haTimers || {})) {
      if (!k.startsWith(from + ":")) continue;
      clearTimeout(t);
      delete this._haTimers[k];
      restart.push(parseInt(k.slice(from.length + 1), 10));
    }
    // Scheduled (not run yet): they run once the new config is in place.
    for (const idx of new Set(restart)) if (Number.isFinite(idx)) this._scheduleHaValidate(to, idx);
    if (this._dragRuleId === from) this._dragRuleId = to;
    if (this._dragOverId === from) this._dragOverId = to;
  }

  _clone(o) {
    return o == null ? o : JSON.parse(JSON.stringify(o));
  }

  /* ---------- Toast ---------- */
  _showToast(message, isError = false) {
    if (this._toastTimer) clearTimeout(this._toastTimer);
    const toast = this.shadowRoot.querySelector(".toast");
    if (!toast) return;
    const msg = toast.querySelector(".toast-msg");
    // Setting the text on show (not statically) makes role="status" announce it
    if (msg) msg.textContent = message || this._t("saved");
    // Force reflow so the countdown animation restarts on rapid re-shows
    toast.classList.remove("show");
    toast.classList.toggle("toast-error", !!isError);
    void toast.offsetWidth;
    toast.classList.add("show");
    this._toastTimer = setTimeout(() => {
      toast.classList.remove("show");
      if (msg) msg.textContent = "";
    }, isError ? 5000 : 2000);
  }

  // Show a localized error toast for a failed WebSocket call. The backend
  // sends a stable error code; its message text is English-only.
  _showError(err) {
    const code = err && err.code ? String(err.code) : "";
    const key = "error_" + code;
    const text = code ? this._t(key) : key;
    let msg = text !== key ? text : this._t("error_generic");
    // Which condition is wrong is only in the backend message: show it too
    if (code === "invalid_conditions" && err.message) msg += " — " + String(err.message);
    this._showToast(msg, true);
  }

  /* ---------- Confirm dialog ---------- */
  _showConfirm(message, callback, okLabel = null) {
    this._confirmMessage = message;
    this._confirmCallback = callback;
    this._confirmOkLabel = okLabel;
    this._render();
    // Move focus into the dialog so keyboard users can act on it
    setTimeout(() => this.shadowRoot.querySelector(".confirm-dialog .btn-secondary")?.focus(), 0);
  }

  _hideConfirm() {
    this._confirmMessage = "";
    this._confirmCallback = null;
    this._confirmOkLabel = null;
    this._render();
  }

  /* ---------- Main render ---------- */
  _render() {
    const root = this.shadowRoot;
    // Unsaved inputs that live only in the DOM survive the rebuild.
    this._syncRuleDraftFromDom();
    this._captureSettingsDraft();

    // Full render when no shell exists, loading/error, or shell has no regions yet
    const shell = root.querySelector(".panel-container");
    if (!shell || !this._config || this._error || !shell.querySelector("[data-region]")) {
      this._fullRender();
    } else {
      // Partial render: update regions individually
      this._updateRegion(shell, "header", this._renderHeaderContent());
      this._updateRegion(shell, "tabs", this._renderTabsContent());
      this._updateRegion(shell, "content", this._renderContent());
      this._updateRegion(shell, "slideout", this._renderSlideOut());
      this._updateRegion(shell, "confirm", this._renderConfirmDialog());
    }
    this._applySettingsDraft();
    this._syncSettingsRadios();
    this._settingsDomStale = false;
    this._refreshDeps();
  }

  _patchInfoBar(shell) {
    const slot = shell.querySelector('[data-region="header"] .info-bar-slot');
    if (!slot) { this._updateRegion(shell, "header", this._renderHeaderContent()); return; }
    const html = this._renderInfoBarInline();
    // Compare with the last generated HTML (innerHTML serialization, SVG
    // included, never matches it exactly and would rewrite every time).
    if (slot._caHtml === html) return;
    slot._caHtml = html;
    slot.innerHTML = html;
  }

  _updateRegion(shell, name, html) {
    const el = shell.querySelector(`[data-region="${name}"]`);
    if (!el) return;
    if (name === "slideout") { this._updateSlideOutRegion(el, html); return; }
    el.innerHTML = html;
  }

  _fullRender() {
    const root = this.shadowRoot;

    let html = `<style>${PANEL_STYLES}</style>`;
    html += '<div class="panel-container">';

    if (!this._config && !this._error) {
      html += `<div class="state-msg"><div class="spinner"></div><div>${this._t("loading")}</div></div>`;
      html += '</div>';
      root.innerHTML = html;
      this._setupDelegation();
      return;
    }

    if (this._error) {
      html += '<div class="state-msg">';
      html += '<div class="state-msg-icon">!</div>';
      html += `<div>${this._t("error_load")}</div>`;
      html += `<button class="btn btn-primary mt-16" data-action="retry">${this._t("retry")}</button>`;
      html += '</div></div>';
      root.innerHTML = html;
      this._setupDelegation();
      return;
    }

    html += `<div class="panel-header" data-region="header" role="banner">${this._renderHeaderContent()}</div>`;
    html += `<div class="tab-bar" data-region="tabs" role="navigation" aria-label="${this._t("nav_label")}">${this._renderTabsContent()}</div>`;
    html += `<div class="tab-content" data-region="content" role="main">${this._renderContent()}</div>`;
    this._slideHtml = this._renderSlideOut();
    html += `<div data-region="slideout">${this._slideHtml}</div>`;
    html += `<div data-region="confirm">${this._renderConfirmDialog()}</div>`;
    html += '</div>';
    html += `<div class="toast" role="status"><span class="toast-msg"></span><span class="toast-progress"></span></div>`;

    root.innerHTML = html;
    this._setupDelegation();
  }

  _renderHeaderContent() {
    const activeScenario = this._getActiveScenario();
    const version = this._config ? this._config.version : "";
    const enabled = this._config ? this._config.enabled !== false : true;
    let html = '<div class="header-left">';
    html += '<button class="menu-btn" data-action="toggle-menu" aria-label="' + this._t("title") + '">' + this._lucideIcon("menu", 24) + '</button>';
    html += '<h1>' + this._t("title") + '</h1>';
    if (this._latestVersion) {
      const v = this._esc(version);
      const latest = this._esc(this._latestVersion);
      html += ' <a class="update-badge" href="https://github.com/slemeur91/CoverAutomatic/releases/tag/v' + latest + '" target="_blank" rel="noopener noreferrer" title="' + this._t("update_badge_title") + '">v' + v + ' → v' + latest + '</a>';
    } else if (version) {
      const v = this._esc(version);
      html += ' <a class="version-info" href="https://github.com/slemeur91/CoverAutomatic/releases/tag/v' + v + '" target="_blank" rel="noopener noreferrer" title="' + this._t("version_link_title") + '">v' + v + '</a>';
      if (this._upToDate && this._config?.settings?.update_check_enabled !== false) html += ' <span class="uptodate-badge">\u2713 ' + this._esc(this._t("update_uptodate")) + '</span>';
    }
    html += '</div><div class="header-right">';
    html += '<span class="info-bar-slot">' + this._renderInfoBarInline() + '</span>';
    if (activeScenario) {
      html += '<span class="scenario-badge">' + (activeScenario.icon ? '<ha-icon icon="' + this._esc(activeScenario.icon) + '" class="scenario-badge-icon"></ha-icon>' : '') + this._esc(activeScenario.name) + '</span>';
    }
    html += '<div class="master-switch" title="' + this._t("master_enabled_hint") + '">';
    html += '<span class="master-label">' + this._t("master_enabled") + '</span>';
    html += '<label class="master-toggle">';
    html += '<input type="checkbox" ' + (enabled ? 'checked ' : '') + 'data-action="master-toggle" aria-label="' + this._esc(this._t("master_enabled")) + '">';
    html += '<span class="toggle-slider"></span>';
    html += '</label>';
    html += '</div>';
    html += '</div>';
    return html;
  }

  _renderTabsContent() {
    const tabs = ["covers", "facades", "rules", "scenarios", "settings", "log"];
    let html = '';
    for (const tab of tabs) {
      const isActive = this._activeTab === tab;
      html += '<button class="' + (isActive ? " active" : "") + '" data-tab="' + tab + '"' + (isActive ? ' aria-current="true"' : '') + '>' + this._tt("tabs", tab) + '</button>';
    }
    return html;
  }

  _renderInfoBarInline() {
    const sunState = this._hass?.states ? this._hass.states["sun.sun"] : null;
    const settings = this._config ? this._config.settings || {} : {};
    const tempEntity = settings.outdoor_temp_sensor;
    const tempState = tempEntity && this._hass?.states ? this._hass.states[tempEntity] : null;
    const tempVal = tempState && tempState.state !== "unavailable" && tempState.state !== "unknown" ? parseFloat(tempState.state) : null;
    const az = sunState && sunState.attributes ? sunState.attributes.azimuth : null;
    const el = sunState && sunState.attributes ? sunState.attributes.elevation : null;
    const weatherEntity = settings.weather_entity;
    const weatherState = weatherEntity && this._hass?.states ? this._hass.states[weatherEntity] : null;
    const weatherVal = weatherState && weatherState.state !== "unavailable" && weatherState.state !== "unknown" ? weatherState.state : null;
    const solarEntity = settings.solar_sensor;
    const solarState = solarEntity && this._hass?.states ? this._hass.states[solarEntity] : null;
    const solarVal = solarState && solarState.state !== "unavailable" && solarState.state !== "unknown" ? parseFloat(solarState.state) : null;
    if (az == null && el == null && tempVal == null && weatherVal == null && solarVal == null) return '';
    const belowHorizon = el != null && el < 0;
    const sunIcon = belowHorizon
      ? '<svg class="info-bar-icon" width="14" height="14" viewBox="0 0 24 24"><path d="M12 2a9.9 9.9 0 00-3.24.53A7 7 0 0015 9a7 7 0 01-6.47 6.97A9.98 9.98 0 0012 22c5.52 0 10-4.48 10-10S17.52 2 12 2z" fill="currentColor" opacity="0.65"/></svg>'
      : this._sunIconSvg(14);
    let widgets = [];
    if (az != null && el != null) {
      const sunTitle = this._t("info_sun_title");
      widgets.push('<span class="info-widget" title="' + this._esc(sunTitle) + '">' + sunIcon + '<span class="info-widget-value">' + Number(az).toFixed(1) + '\u00B0 / ' + Number(el).toFixed(1) + '\u00B0</span></span>');
    }
    if (tempVal != null) {
      const tempTitle = this._t("info_outdoor_title");
      const thermoIcon = '<svg class="info-bar-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/></svg>';
      widgets.push('<span class="info-widget" title="' + this._esc(tempTitle) + '">' + thermoIcon + '<span class="info-widget-value">' + tempVal.toFixed(1) + ' \u00B0C</span></span>');
    }
    if (weatherVal != null) {
      const weatherKey = "weather_" + String(weatherVal).replace(/-/g, "_");
      const translated = this._t(weatherKey);
      const weatherLabel = translated && translated !== weatherKey ? translated : String(weatherVal);
      widgets.push('<span class="info-widget" title="' + this._esc(weatherLabel) + '">' + this._weatherIconSvg(weatherVal) + '<span class="info-widget-value">' + this._esc(weatherLabel) + '</span></span>');
    }
    if (solarVal != null) {
      // The threshold may follow an entity (typed value as fallback)
      const thrState = settings.solar_threshold_entity && this._hass?.states ? this._hass.states[settings.solar_threshold_entity] : null;
      const thrVal = thrState ? parseFloat(thrState.state) : NaN;
      const threshold = Number.isFinite(thrVal) ? thrVal : (settings.solar_threshold ?? 0);
      const exceeded = threshold > 0 && solarVal > threshold;
      const unit = solarState.attributes && solarState.attributes.unit_of_measurement ? ' ' + solarState.attributes.unit_of_measurement : '';
      const solarTitle = exceeded ? this._t("info_solar_exceeded_title") : this._t("info_solar_title");
      const activityIcon = '<svg class="info-bar-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.5.5 0 0 1-.96 0L9.24 2.18a.5.5 0 0 0-.96 0l-2.35 8.36A2 2 0 0 1 4 12H2"/></svg>';
      const cls = exceeded ? 'info-widget info-widget-highlight' : 'info-widget';
      widgets.push('<span class="' + cls + '" title="' + this._esc(solarTitle) + '">' + activityIcon + '<span class="info-widget-value">' + solarVal.toFixed(0) + this._esc(unit) + (exceeded ? ' \u25B2' : '') + '</span></span>');
    }
    return '<span class="info-bar">' + widgets.join('') + '</span>';
  }

  _sunIconSvg(size = 14) {
    return '<svg class="sun-icon-svg" width="' + size + '" height="' + size + '" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="1" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/></g></svg>';
  }

  // Lucide-based weather icon by HA weather state
  _weatherIconSvg(state, size = 14) {
    const a = 'none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round';
    const paths = {
      sunny: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
      clear_night: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
      cloudy: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
      partlycloudy: '<path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="m19.07 4.93-1.41 1.41"/><path d="M15.947 12.65a4 4 0 0 0-5.925-4.128"/><path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z"/>',
      rainy: '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 14v6"/><path d="M8 14v6"/><path d="M12 16v6"/>',
      pouring: '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 14v6"/><path d="M8 14v6"/><path d="M12 16v6"/>',
      snowy: '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M8 15h.01"/><path d="M8 19h.01"/><path d="M12 17h.01"/><path d="M12 21h.01"/><path d="M16 15h.01"/><path d="M16 19h.01"/>',
      snowy_rainy: '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M11 20v2"/><path d="M8 18h.01"/><path d="M16 18h.01"/>',
      fog: '<path d="M3 5h18"/><path d="M3 10h18"/><path d="M3 15h18"/><path d="M3 20h18"/>',
      windy: '<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>',
      windy_variant: '<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>',
      lightning: '<path d="M19 16.9A5 5 0 0 0 18 7h-1.26a8 8 0 1 0-11.62 9"/><path d="m13 12-3 5h4l-3 5"/>',
      lightning_rainy: '<path d="M16 14v6"/><path d="M8 14v6"/><path d="M19 16.9A5 5 0 0 0 18 7h-1.26a8 8 0 1 0-11.62 9"/><path d="m13 12-3 5h4l-3 5"/>',
      hail: '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 14v2"/><path d="M8 14v2"/><path d="M16 20h.01"/><path d="M8 20h.01"/><path d="M12 16v2"/><path d="M12 22h.01"/>',
      exceptional: '<path d="M12 9v4"/><path d="M12 17h.01"/><circle cx="12" cy="12" r="10"/>'
    };
    const key = String(state || "").replace(/-/g, "_");
    const p = paths[key] || paths.cloudy;
    return '<svg class="info-bar-icon" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="' + a + '">' + p + '</svg>';
  }

  // Lucide-style inline SVG icons for settings sections
  _lucideIcon(name, size = 16) {
    const a = 'none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round';
    const paths = {
      house: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
      gauge: '<path d="M12 16v-4"/><path d="M12 8h.01"/><circle cx="12" cy="12" r="10"/>',
      thermometer: '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
      wind: '<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>',
      cog: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
      archive: '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
      menu: '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
      info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
      app_window: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 4v4"/><path d="M2 8h20"/><path d="M6 4v4"/>',
      sliders: '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
      move_vertical: '<polyline points="8 18 12 22 16 18"/><polyline points="8 6 12 2 16 6"/><line x1="12" x2="12" y1="2" y2="22"/>',
      activity: '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.5.5 0 0 1-.96 0L9.24 2.18a.5.5 0 0 0-.96 0l-2.35 8.36A2 2 0 0 1 4 12H2"/>',
      copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
      shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
      thermometer_snowflake: '<path d="m10 20-1.25-2.5L6 18"/><path d="M10 4 8.75 6.5 6 6"/><path d="M10.585 15H10"/><path d="M2 12h6.5L10 9"/><path d="M20 14.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z"/><path d="m4 10 1.5 2L4 14"/><path d="m7 21 3-6-1.5-3"/><path d="m7 3 3 6h2"/>',
      thermometer_sun: '<path d="M12 2v2"/><path d="M12 8a4 4 0 0 0-1.645 7.647"/><path d="M2 12h2"/><path d="M20 14.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0z"/><path d="m4.93 4.93 1.41 1.41"/><path d="m6.34 17.66-1.41 1.41"/>',
      sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>'
    };
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="' + a + '">' + (paths[name] || '') + '</svg>';
  }

  _renderContent() {
    switch (this._activeTab) {
      case "covers": return this._renderCovers();
      case "facades": return this._renderFacades();
      case "rules": return this._renderRules();
      case "scenarios": return this._renderScenarios();
      case "settings": return this._renderSettings();
      case "log": return this._renderLog();
      default: return '';
    }
  }

  _renderConfirmDialog() {
    if (!this._confirmCallback) return '';
    return '<div class="confirm-overlay" data-action="confirm-cancel">'
      + '<div class="confirm-dialog" role="alertdialog" aria-modal="true" aria-label="' + this._esc(this._confirmMessage) + '">'
      + '<p>' + this._esc(this._confirmMessage) + '</p>'
      + '<div class="actions">'
      + '<button class="btn btn-secondary" data-action="confirm-cancel">' + this._t("cancel") + '</button>'
      + '<button class="btn btn-danger" data-action="confirm-ok">' + this._esc(this._confirmOkLabel || this._t("delete")) + '</button>'
      + '</div></div></div>';
  }

  // Items separated by a thin line (content without framed boxes)
  _sepList(items) {
    return `<div class="sep-list">${items.filter(Boolean).map(h => `<div class="sep-item">${h}</div>`).join("")}</div>`;
  }

  // Label with a shorter variant shown on narrow screens (key + "_short")
  _L(key) {
    const lang = (this._hass?.language) || "en";
    const dict = I18N[lang] || I18N.en;
    const sk = key + "_short";
    const long = this._esc(this._t(key));
    if (dict[sk] === undefined && I18N.en[sk] === undefined) return long;
    return `<span class="lbl-long">${long}</span><span class="lbl-short">${this._esc(this._t(sk))}</span>`;
  }

  _renderToggle(labelKey, checked, action, id, field, hintKey = null) {
    return `<div class="toggle-row">
      <span class="toggle-label">${this._L(labelKey)}${hintKey ? this._hint(hintKey) : ""}</span>
      <label class="toggle">
        <input type="checkbox" ${checked ? "checked" : ""} data-action="${action}" data-id="${this._esc(id)}" data-field="${field}">
        <span class="toggle-slider"></span>
      </label>
    </div>`;
  }

  _renderEntitySelect(field, currentValue, domain, deviceClass) {
    if (!this._hass || !this._hass.states) return `<input type="text" value="${this._esc(currentValue || "")}" data-settings-field="${field}">`;
    const entities = Object.values(this._hass.states)
      .filter(s => {
        if (!s.entity_id.startsWith(domain + ".")) return false;
        if (deviceClass && s.attributes.device_class !== deviceClass) return false;
        return true;
      })
      .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id));
    let html = `<select data-settings-field="${field}">`;
    html += `<option value="">-- ${this._t("none")} --</option>`;
    for (const e of entities) {
      const name = e.attributes.friendly_name || e.entity_id;
      const sel = e.entity_id === currentValue ? " selected" : "";
      html += `<option value="${this._esc(e.entity_id)}"${sel}>${this._esc(name)} (${this._esc(e.entity_id)})</option>`;
    }
    // A configured entity outside the filter (other device class, not loaded
    // yet) stays selected instead of being cleared by the next save.
    if (currentValue && !entities.some(e => e.entity_id === currentValue)) {
      html += `<option value="${this._esc(currentValue)}" selected>${this._esc(currentValue)}</option>`;
    }
    html += "</select>";
    return html;
  }

  // Display label for a multiselect option; the stored value stays raw.
  _optionLabel(paramKey, opt) {
    if (paramKey === "weather") {
      return this._i18nOr("weather_" + String(opt).replace(/-/g, "_"), String(opt));
    }
    return this._i18nOr("opt_" + opt, String(opt));
  }

  _i18nOr(key, fallback) {
    const t = this._t(key);
    return (t && t !== key) ? t : fallback;
  }

  _getCoverName(entityId) {
    const covers = this._config ? (this._config.covers || {}) : {};
    const cover = covers[entityId];
    return cover ? cover.name : entityId;
  }

  /* ============================================================
   * Helpers
   * ============================================================ */
  _getActiveScenario() {
    if (!this._config) return null;
    const id = (this._config.settings || {}).active_scenario || this._config.active_scenario;
    return id ? (this._config.scenarios || {})[id] || null : null;
  }

  _getFacadeName(facadeId) {
    if (!facadeId || !this._config) return "-";
    const f = (this._config.facades || {})[facadeId];
    return f ? f.name : "-";
  }

  _getFacadeCovers(facadeId) {
    if (!this._config) return [];
    const covers = this._config.covers || {};
    return Object.values(covers).filter(c => c.facade_id === facadeId);
  }

  _esc(str) {
    if (str == null) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Coerce a stored numeric field for safe HTML-attribute interpolation.
  // Returns a finite number, otherwise the fallback (empty string by default).
  // Defense-in-depth against hand-edited .storage files (WS schema already
  // enforces numerics on write).
  _num(v, fallback = "") {
    if (v === null || v === undefined || v === "") return fallback;
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  }
}

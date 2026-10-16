// CoverAutomatic panel -- Log tab.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).

export const LogMixin = (Base) => class extends Base {
  _renderLog() {
    // Filter on a cover that no longer exists: back to all covers
    if (this._logCover && this._config && !(this._config.covers || {})[this._logCover]) {
      this._logCover = null;
      this._logEntries = null;
    }
    if (this._logEntries === null) {
      this._loadLog();
      return '<div class="state-msg"><div class="spinner"></div><div>' + this._t("log_loading") + '</div></div>';
    }

    let html = '';

    // Filter buttons
    const filters = [null, "position", "status", "rule", "wind", "scenario"];
    html += '<div class="log-filter-bar">';
    for (const f of filters) {
      const active = this._logFilter === f ? " active" : "";
      const label = f ? this._t("log_type_" + f) : this._t("log_filter_all");
      html += '<button class="btn btn-sm' + active + '" data-action="log-filter" data-filter="' + (f || '') + '">' + label + '</button>';
    }
    html += '<button class="btn btn-sm btn-danger" data-action="log-clear">' + this._t("log_clear") + '</button>';
    html += '</div>';

    // Cover filter: all covers, or one (its entries + global events such as wind)
    const covers = Object.values(this._config?.covers || {})
      .sort((a, b) => String(a.name || a.entity_id).localeCompare(String(b.name || b.entity_id), this._hass?.language || undefined));
    html += '<div class="log-cover-filter"><label for="log-cover-select">' + this._esc(this._t("log_filter_cover")) + '</label>'
      + '<select id="log-cover-select" data-action="log-cover">'
      + '<option value=""' + (this._logCover ? '' : ' selected') + '>' + this._esc(this._t("log_filter_all_covers")) + '</option>'
      + covers.map(c => '<option value="' + this._esc(c.entity_id) + '"' + (this._logCover === c.entity_id ? ' selected' : '') + '>'
        + this._esc(c.name || c.entity_id) + '</option>').join('')
      + '</select>'
      + (this._logCover ? '<span class="log-cover-note">' + this._esc(this._t("log_filter_cover_note")) + '</span>' : '')
      + '</div>';

    let entries = this._logEntries;
    if (this._logFilter) {
      entries = entries.filter(e => e.type === this._logFilter);
    }

    if (entries.length === 0) {
      return html + '<div class="empty-state">' + this._t("log_empty") + '</div>';
    }

    html += '<div class="card"><div class="table-scroll"><table class="data-table">';
    html += '<thead><tr>';
    html += '<th>' + this._t("log_time") + '</th>';
    html += '<th>' + this._t("log_event") + '</th>';
    html += '<th>' + this._t("log_cover") + '</th>';
    html += '<th>' + this._t("log_message") + '</th>';
    html += '</tr></thead><tbody>';

    for (const e of entries) {
      const time = new Date(e.ts * 1000).toLocaleString(this._hass?.language || undefined);
      const typeLabel = this._t("log_type_" + e.type) || e.type;
      const coverName = e.entity_id ? this._getCoverName(e.entity_id) : "–";
      const typeClass = e.type === "wind" ? "status-wind_protected" : e.type === "status" ? "status-paused"
        : e.type === "scenario" ? "status-manual" : "";
      html += '<tr>';
      html += '<td class="nowrap">' + this._esc(time) + '</td>';
      html += '<td><span class="status-badge ' + typeClass + '">' + this._esc(typeLabel) + '</span></td>';
      html += '<td>' + this._esc(coverName) + '</td>';
      html += '<td>' + this._esc(this._formatLogMessage(e)) + '</td>';
      html += '</tr>';
    }
    html += '</tbody></table></div></div>';
    return html;
  }

  // Localize an activity log entry from its structured data. Entries written
  // by versions before 1.63.0 have no data.key and keep their English text.
  _formatLogMessage(e) {
    const d = e && e.data;
    const key = d && d.key;
    if (!key) return e.message || "";
    const template = this._t("log_msg_" + key);
    if (template === "log_msg_" + key) return e.message || "";
    const status = (v) => {
      const t = this._t("status_" + v);
      return t !== "status_" + v ? t : String(v);
    };
    const values = { ...d };
    if (key === "status_change") {
      values.from = status(d.from);
      values.to = status(d.to);
    }
    if (key === "safety_takeover" || key === "safety_release" || key === "sensor_unavailable") {
      if (d.status) values.status = status(d.status);
    }
    if (Array.isArray(d.sensor)) values.sensor = d.sensor.join(", ");
    if (key === "scenario_change") {
      // Current names when the scenarios still exist, else the logged ones
      const sc = this._config?.scenarios || {};
      if (sc[d.from_id]) values.from = sc[d.from_id].name || d.from_id;
      if (sc[d.to_id]) values.to = sc[d.to_id].name || d.to_id;
    }
    if (key === "rule" || key === "safety_takeover" || key === "safety_release") {
      const rule = this._config?.rules?.[d.rule_id];
      values.rule = rule ? rule.name : (d.rule_name || d.rule_id || "");
    }
    return template.replace(/\{(\w+)\}/g, (m, name) => (values[name] != null ? String(values[name]) : m));
  }

  async _loadLog() {
    const cover = this._logCover || null;
    // Same request already in flight: repeated renders don't refire it
    if (this._logLoading && this._logLoadingCover === cover) return;
    const seq = (this._logSeq = (this._logSeq || 0) + 1);
    this._logLoading = true;
    this._logLoadingCover = cover;
    let entries;
    try {
      const msg = cover
        ? { entity_id: cover, include_global: true, limit: 1000 }
        : {};
      const result = await this._ws("cover_automatic/log", msg);
      entries = result.entries || [];
    } catch (e) {
      entries = [];
    }
    // Stale response (filter changed, log cleared or newer request): drop it
    if (seq !== this._logSeq) return;
    this._logLoading = false;
    this._logLoadingCover = undefined;
    if ((this._logCover || null) !== cover) return;
    this._logEntries = entries;
    this._render();
  }
};

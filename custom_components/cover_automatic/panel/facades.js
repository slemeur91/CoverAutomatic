// CoverAutomatic panel -- Facades tab, compass and house orientation.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).
import * as sky from "./sky.js";
import { FACADE_BEARINGS, FACADE_SIDE_COLORS, DIRECTION_ARROWS } from "./constants.js";

export const FacadesMixin = (Base) => class extends Base {
  _renderFacadeDropdown(cover) {
    const facades = this._config.facades || {};
    let html = `<div class="form-group"><label>${this._t("cover_facade")}</label><select data-action="cover-select" data-id="${this._esc(cover.entity_id)}" data-field="facade_id">`;
    html += `<option value="">${this._t("none")}</option>`;
    for (const f of Object.values(facades)) {
      const sel = cover.facade_id === f.id ? " selected" : "";
      html += `<option value="${this._esc(f.id)}"${sel}>${this._esc(f.name)}</option>`;
    }
    html += '</select></div>';
    return html;
  }

  /* ============================================================
   * TAB: Facades
   * ============================================================ */
  _renderFacades() {
    const facades = this._config.facades || {};
    const entries = Object.values(facades).sort((a, b) => (a.azimuth_start ?? 0) - (b.azimuth_start ?? 0));

    let html = '<div class="card-grid">';

    for (const f of entries) {
      if (this._editingFacade === f.id) {
        html += this._renderFacadeEditForm(f);
      } else {
        html += this._renderFacadeCard(f);
      }
    }

    // Add button or form
    if (this._addingFacade) {
      html += this._renderFacadeAddForm();
    } else {
      html += `<button class="add-card" data-action="facade-add-start">+ ${this._t("facade_add")}</button>`;
    }

    html += '</div>';
    return html;
  }

  _renderFacadeCard(f) {
    const covers = this._getFacadeCovers(f.id);
    const arrow = DIRECTION_ARROWS[f.direction] || "";
    const dirLabel = this._t("facade_dir_" + f.direction) || f.direction;
    const liveFacade = (this._config.live_facades || {})[f.id] || {};
    const sunOn = liveFacade.sun_on_facade;
    const sunBadge = sunOn
      ? '<span class="live-icon-sun" title="' + this._esc(this._t("facade_sun_active")) + '">' + this._sunIconSvg(14) + '</span>'
      : '';
    // Today's sun entry/exit times next to the azimuths (sent by the backend)
    const hasTimes = !!(liveFacade.sun_entry || liveFacade.sun_exit);
    const sunTime = (time, tipKey) => time
      ? ` <span class="facade-sun-time" title="${this._esc(this._t(tipKey))}">· ${this._esc(time)}</span>` : "";
    let html = `<div class="card">
      <div class="card-header">
        <span>${this._esc(f.name)}${sunBadge}</span>
        <span class="facade-dir-label">${arrow} ${this._esc(dirLabel)}</span>
      </div>
      <div class="card-body">
        <div class="facade-meta-row">
          <span>${this._t("facade_azimuth_start")}${this._colon()}${f.azimuth_start}&#176;${sunTime(liveFacade.sun_entry, "facade_sun_entry_tip")}</span>
          <span>${this._t("facade_azimuth_end")}${this._colon()}${f.azimuth_end}&#176;${sunTime(liveFacade.sun_exit, "facade_sun_exit_tip")}</span>
          ${hasTimes || !("sun_entry" in liveFacade) ? "" : `<span class="facade-no-sun">${this._esc(this._t("facade_no_sun_today"))}</span>`}
        </div>
        <div class="facade-covers-intro">
          ${this._t("facade_min_elevation")}${this._colon()}${f.min_elevation}&#176;
        </div>
        <div class="facade-covers-list-wrap">
          <span class="facade-covers-label">${this._t("facade_covers")}</span>
          <div class="chip-group">`;
    if (covers.length === 0) {
      html += `<span class="facade-no-covers">${this._t("facade_no_covers")}</span>`;
    } else {
      for (const c of covers) {
        html += `<span class="chip">${this._esc(c.name)}</span>`;
      }
    }
    html += `</div>
        </div>
        <div class="facade-actions">
          <button class="btn btn-secondary btn-sm" data-action="facade-edit" data-id="${this._esc(f.id)}">${this._t("edit")}</button>
          <button class="btn btn-danger btn-sm" data-action="facade-delete" data-id="${this._esc(f.id)}">${this._t("delete")}</button>
        </div>
      </div>
    </div>`;
    return html;
  }

  _renderFacadeEditForm(f) {
    const covers = this._config.covers || {};
    let html = `<div class="inline-form">
      <div class="form-group">
        <label>${this._t("name")}</label>
        <input type="text" value="${this._esc(f.name)}" data-facade-field="name">
      </div>
      <div class="form-group">
        <label>${this._t("facade_direction")}</label>
        <select data-facade-field="direction">
          ${["north","east","south","west"].map(d => `<option value="${d}"${f.direction===d?" selected":""}>${this._t("facade_dir_"+d)}</option>`).join("")}
        </select>
        ${this._hint("facade_direction_hint")}
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>${this._t("facade_azimuth_start")}</label>
          <input type="number" step="any" value="${this._num(f.azimuth_start)}" data-facade-field="azimuth_start">
        </div>
        <div class="form-group">
          <label>${this._t("facade_azimuth_end")}</label>
          <input type="number" step="any" value="${this._num(f.azimuth_end)}" data-facade-field="azimuth_end">
        </div>
      </div>
      ${this._hint("facade_azimuth_hint")}
      <div class="form-group">
        <label>${this._t("facade_min_elevation")}</label>
        <input type="number" min="0" max="90" step="0.5" value="${this._num(f.min_elevation)}" data-facade-field="min_elevation">
        ${this._hint("facade_min_elevation_hint")}
      </div>
      <div class="form-group">
        <label>${this._t("facade_covers")}</label>
        <div class="multi-select">`;
    for (const c of Object.values(covers)) {
      const assignedHere = (f.cover_ids || []).includes(c.entity_id);
      const otherFacade = !assignedHere && c.facade_id && c.facade_id !== f.id ? this._getFacadeName(c.facade_id) : null;
      const sel = assignedHere ? " selected" : "";
      const label = otherFacade ? `${this._esc(c.name)} [${this._esc(otherFacade)}]` : this._esc(c.name);
      html += `<button class="ms-item${sel}" data-action="facade-cover-toggle" data-cover="${this._esc(c.entity_id)}">${label}</button>`;
    }
    html += `</div></div>
      <div class="form-actions">
        <button class="btn btn-secondary" data-action="facade-edit-cancel">${this._t("cancel")}</button>
        <button class="btn btn-primary" data-action="facade-edit-save" data-id="${this._esc(f.id)}">${this._t("save")}</button>
      </div>
    </div>`;
    return html;
  }

  // Widest sun window of a facade: 90° on each side of its bearing, with the
  // house rotation applied (real compass bearings, normalized to [0, 360)),
  // trimmed on its sides to the bearings the sun can actually reach.
  _facadeMaxSpan(direction) {
    const bearing = FACADE_BEARINGS[direction] ?? FACADE_BEARINGS.south;
    const rot = this._num(this._config?.settings?.house_rotation, 0);
    const start = this._facadeAz(bearing - 90 + rot, 90);
    const end = this._facadeAz(bearing + 90 + rot, 270);
    return this._trimToSunSector(start, end) || { start, end };
  }

  // Bearings the sun can reach over the year, as a clockwise sector
  // { from, sweep }: bounded by the sunrise and sunset bearings of the summer
  // solstice at the Home Assistant latitude. The whole circle between the
  // tropics, in polar regions and when the latitude is unknown.
  _sunSector() {
    const lat = Number(this._hass?.config?.latitude);
    const TILT = 23.44;
    if (!Number.isFinite(lat) || Math.abs(lat) <= TILT || Math.abs(lat) >= 90 - TILT) return { from: 0, sweep: 360 };
    const toRad = Math.PI / 180;
    // Half-width of the dark sector = sunrise bearing at the summer solstice
    const half = Math.acos(Math.sin(TILT * toRad) / Math.cos(lat * toRad)) / toRad;
    const dark = lat >= 0 ? 0 : 180;
    return { from: dark + half, sweep: 360 - 2 * half };
  }

  // Parts of the clockwise span (start, sweep) inside a sector, as
  // [from, sweep] pairs: none, one, or two when the span covers both ends.
  _clipToSector(start, sweep, sector) {
    if (sector.sweep >= 360) return [[start, Math.min(sweep, 360)]];
    const s = (((start - sector.from) % 360) + 360) % 360;
    const e = s + Math.min(sweep, 360);
    return [0, 360]
      .map(k => [Math.max(s, k), Math.min(e, k + sector.sweep)])
      .filter(([a, b]) => b - a > 0.01)
      .map(([a, b]) => [a + sector.from, b - a]);
  }

  // The sun never stands in a sector centred on north (northern hemisphere)
  // or south (southern): it is bounded by the sunrise and sunset bearings of
  // the summer solstice at the Home Assistant latitude. Returns the part of
  // [start, end] (clockwise) outside that sector, in whole degrees, or null
  // when nothing is trimmed, when the trim would split the window in two
  // (facade facing the dark sector) or when the sun can come from anywhere
  // (tropics, polar regions, unknown latitude).
  _trimToSunSector(start, end) {
    const sector = this._sunSector();
    if (sector.sweep >= 360) return null;
    const sweep = (((end - start) % 360) + 360) % 360 || 360;
    const parts = this._clipToSector(start, sweep, sector);
    if (parts.length !== 1) return null;
    const [from, width] = parts[0];
    // Offsets from the start of the sector: of the span, and of its lit part
    const s = (((start - sector.from) % 360) + 360) % 360;
    const a = from - sector.from;
    const cutStart = a - s > 0.001, cutEnd = (s + sweep) - (a + width) > 0.001;
    if (!cutStart && !cutEnd) return null;
    // Whole degrees, rounded towards the inside of the lit sector
    const lo = cutStart ? Math.ceil(from - 0.001) : from;
    const hi = cutEnd ? Math.floor(from + width + 0.001) : from + width;
    if (hi - lo <= 0) return null;
    return { start: this._facadeAz(lo, start), end: this._facadeAz(hi, end) };
  }

  _renderFacadeAddForm() {
    const covers = this._config.covers || {};
    const span = this._facadeMaxSpan("south");
    let html = `<div class="inline-form">
      <div class="form-group">
        <label>${this._t("name")}</label>
        <input type="text" value="" data-facade-field="name" placeholder="${this._t("name")}">
      </div>
      <div class="form-group">
        <label>${this._t("facade_direction")}</label>
        <select data-facade-field="direction">
          ${["north","east","south","west"].map(d => `<option value="${d}"${d==="south"?" selected":""}>${this._t("facade_dir_"+d)}</option>`).join("")}
        </select>
        ${this._hint("facade_direction_hint")}
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>${this._t("facade_azimuth_start")}</label>
          <input type="number" step="any" value="${span.start}" data-facade-field="azimuth_start">
        </div>
        <div class="form-group">
          <label>${this._t("facade_azimuth_end")}</label>
          <input type="number" step="any" value="${span.end}" data-facade-field="azimuth_end">
        </div>
      </div>
      ${this._hint("facade_azimuth_hint")}
      <div class="form-group">
        <label>${this._t("facade_min_elevation")}</label>
        <input type="number" min="0" max="90" step="0.5" value="0" data-facade-field="min_elevation">
        ${this._hint("facade_min_elevation_hint")}
      </div>
      <div class="form-group">
        <label>${this._t("facade_covers")}</label>
        <div class="multi-select">`;
    for (const c of Object.values(covers)) {
      const otherFacade = c.facade_id ? this._getFacadeName(c.facade_id) : null;
      const label = otherFacade ? `${this._esc(c.name)} [${this._esc(otherFacade)}]` : this._esc(c.name);
      html += `<button class="ms-item" data-action="facade-cover-toggle" data-cover="${this._esc(c.entity_id)}">${label}</button>`;
    }
    html += `</div></div>
      <div class="form-actions">
        <button class="btn btn-secondary" data-action="facade-add-cancel">${this._t("cancel")}</button>
        <button class="btn btn-primary" data-action="facade-add-save">${this._t("add")}</button>
      </div>
    </div>`;
    return html;
  }

  /* ---------- Sky: compass, sun and moon, today's sun (Settings > House) ---------- */
  // Home Assistant's home location and time zone; null without coordinates
  _skyLocation() {
    const c = (this._hass && this._hass.config) || {};
    const lat = Number(c.latitude), lon = Number(c.longitude);
    return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon, tz: c.time_zone || null } : null;
  }

  // Sun path of the day, current sun (from sun.sun when available) and moon
  _skyNow() {
    const loc = this._skyLocation();
    const now = new Date();
    const start = sky.dayStartIn(now, loc && loc.tz);
    const samples = loc ? sky.sunDay(start, loc.lat, loc.lon, 5) : [];
    const sunState = this._hass && this._hass.states ? this._hass.states["sun.sun"] : null;
    const az = sunState ? parseFloat(sunState.attributes.azimuth) : NaN;
    const el = sunState ? parseFloat(sunState.attributes.elevation) : NaN;
    let sunNow = null;
    if (Number.isFinite(az) && Number.isFinite(el)) sunNow = { azimuth: az, elevation: el };
    else if (loc) sunNow = sky.sunPosition(now, loc.lat, loc.lon);
    const moonNow = loc ? sky.moonPosition(now, loc.lat, loc.lon) : null;
    return { now, loc, samples, nowMin: (now - start) / 60000, sunNow, moonNow, moon: sky.moonIllumination(now) };
  }

  _skyNum(v) {
    const lang = (this._hass && this._hass.language) || "en";
    return Number(v).toLocaleString(lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  // Compass (north up, sky seen from above) with the house in the middle,
  // then the legend of the bearings. Re-rendered when the rotation changes.
  _renderCompassSVG(rotation) {
    const houseRot = Number.isFinite(Number(rotation)) ? Number(rotation) : 0;
    const d = this._skyNow();
    // Arcs around the horizon: the bearings the sun reaches over the year,
    // then one ring per side of the house, centred on the direction that side
    // faces (house rotation applied) and spanning the 180° from which the sun
    // can light it; the part the sun never reaches is drawn faint.
    const sector = this._sunSector();
    const arcs = [{ from: sector.from, sweep: sector.sweep, color: "var(--ca-sun)", ring: 0, width: 3 }];
    const ringOf = { north: 1, east: 2, south: 3, west: 4 };
    const letter = { north: "compass_n", east: "compass_e", south: "compass_s", west: "compass_w" };
    for (const [dir, bearing] of Object.entries(FACADE_BEARINGS)) {
      const ring = ringOf[dir], color = FACADE_SIDE_COLORS[dir];
      arcs.push({ from: bearing - 90 + houseRot, sweep: 180, color, ring, width: 4, opacity: 0.25 });
      for (const [from, sweep] of this._clipToSector(bearing - 90 + houseRot, 180, sector)) {
        arcs.push({ from, sweep, color, ring, width: 4 });
      }
      arcs.push({ from: bearing - 90 + houseRot, sweep: 180, color, ring, width: 0, opacity: 0, label: this._esc(this._t(letter[dir])) });
    }
    const svg = sky.renderSkyCompass({
      samples: d.samples, sunNow: d.sunNow, moonNow: d.moonNow, moonPhase: d.moon.phase, arcs,
      house: { rotation: houseRot },
      labels: { n: this._esc(this._t("compass_n")), e: this._esc(this._t("compass_e")), s: this._esc(this._t("compass_s")), w: this._esc(this._t("compass_w")) },
    });
    const deg = (v) => `${Math.round((((v % 360) + 360) % 360))}°`;
    const range = (from, sweep) => sweep >= 359.99 ? "0°–360°" : `${deg(from)}–${deg(from + sweep)}`;
    const row = (dot, name, text) => `<div class="compass-legend-row"><span class="compass-legend-dot" style="background:${dot}"></span><span class="compass-legend-name">${name}</span><span class="compass-legend-az">${text}</span></div>`;
    let legend = row("var(--ca-sun)", this._esc(this._t("compass_sun_range")), range(sector.from, sector.sweep));
    // One row per house side: the bearings from which the sun can light it
    // (90° on each side of its bearing), cut to the sunshine sector.
    for (const [dir, bearing] of Object.entries(FACADE_BEARINGS)) {
      const parts = this._clipToSector(bearing - 90 + houseRot, 180, sector);
      let text = parts.length ? parts.map(([from, sweep]) => range(from, sweep)).join(", ") : "\u2013";
      // Cut in two by the dark sector: whole span first, then its two lit parts
      if (parts.length === 2) text = `${deg(parts[0][0])}–${deg(parts[1][0] + parts[1][1])} (${text})`;
      legend += row(FACADE_SIDE_COLORS[dir], this._esc(this._t("facade_dir_" + dir)), text);
    }
    return `${svg}<div class="compass-legend">${legend}</div>`;
  }

  // Sun and moon information, next to the compass
  _renderSkyInfo() {
    const d = this._skyNow();
    const info = (label, value) => `<div class="sky-info-row"><span class="sky-info-lbl">${this._esc(label)}</span><span>${value}</span></div>`;
    const head = (color, label) => `<div class="sky-info-head"><span class="compass-legend-dot" style="background:${color}"></span>${this._esc(label)}</div>`;
    let html = "";
    if (d.sunNow) {
      const rise = d.samples.find((p, i) => i && d.samples[i - 1].elevation < 0 && p.elevation >= 0);
      const set = d.samples.find((p, i) => i && d.samples[i - 1].elevation >= 0 && p.elevation < 0);
      const hm = (p) => (p ? sky.hhmm(p.min) : "\u2013");
      html += head("var(--ca-sun)", this._t("sky_sun"));
      html += info(this._t("sky_azimuth"), `${this._skyNum(d.sunNow.azimuth)}°`);
      html += info(this._t("sky_elevation"), `${this._skyNum(d.sunNow.elevation)}°`);
      html += info(this._t("sky_sunrise"), `${hm(rise)} · ${this._esc(this._t("sky_sunset"))} ${hm(set)}`);
    }
    if (d.moonNow) {
      html += '<div class="compass-legend-sep"></div>';
      html += head("var(--ca-moon-dark)", this._t("sky_moon"));
      html += info(this._t("sky_phase"), `${this._esc(this._t("moon_" + sky.moonPhaseKey(d.moon.phase)))} · ${Math.round(d.moon.fraction * 100)} %`);
      const below = d.moonNow.elevation < 0 ? ` (${this._esc(this._t("sky_below_horizon"))})` : "";
      html += info(this._t("sky_position"), `${this._skyNum(d.moonNow.azimuth)}° / ${this._skyNum(d.moonNow.elevation)}°${below}`);
    }
    return html ? `<div class="sky-info">${html}</div>` : "";
  }

  // Today's sun curve with one strip per facade
  _renderSunToday() {
    const d = this._skyNow();
    if (!d.loc) return "";
    const facades = Object.values((this._config && this._config.facades) || {})
      .sort((a, b) => (a.azimuth_start ?? 0) - (b.azimuth_start ?? 0))
      .map((f, i) => ({ ...f, name: this._esc(f.name), color: sky.FACADE_PALETTE[i % sky.FACADE_PALETTE.length] }));
    for (const f of facades) f.windows = sky.facadeWindows(f, d.samples);
    let date = "";
    try {
      date = d.now.toLocaleDateString((this._hass && this._hass.language) || "en", { weekday: "long", day: "numeric", month: "long", timeZone: d.loc.tz || undefined });
    } catch (err) {
      date = d.now.toLocaleDateString();
    }
    return `<div class="sun-today-head"><span>${this._esc(this._t("sun_today_title"))}</span><span>${this._esc(date)}</span></div>
      ${sky.renderSunToday({ samples: d.samples, nowMin: d.nowMin, sunNow: d.sunNow, facades, labels: { noSun: this._esc(this._t("facade_no_sun_today")) } })}`;
  }

  // New sun or moon position (sun.sun changed): redraw the sky parts of the
  // house section in place, without touching its inputs.
  _refreshSky() {
    const root = this.shadowRoot;
    if (!root || this._houseDragState) return;
    const compass = root.querySelector(".settings-house-compass");
    if (!compass) return;
    const input = root.querySelector("#house-rotation-input");
    const parsed = input ? parseFloat(input.value) : NaN;
    compass.innerHTML = this._renderCompassSVG(Number.isFinite(parsed) ? parsed : this._num((this._config.settings || {}).house_rotation, 0));
    const info = root.querySelector(".settings-house-sky");
    if (info) info.innerHTML = this._renderSkyInfo();
    const today = root.querySelector(".sun-today");
    if (today) today.innerHTML = this._renderSunToday();
  }

  /* ---------- House compass drag-rotation ---------- */
  _handleHouseDragStart(e) {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    const target = e.target.closest('[data-action="house-drag-start"]');
    if (!target) return;
    e.preventDefault();
    const svg = this.shadowRoot.querySelector("#compass-svg");
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const vb = (svg.getAttribute("viewBox") || "0 0 280 288").split(" ").map(parseFloat);
    // Compass centre in SVG units (set by sky.renderSkyCompass)
    const compassCxLogical = parseFloat(svg.dataset.cx) || vb[2] / 2;
    const compassCyLogical = parseFloat(svg.dataset.cy) || vb[3] / 2;
    const cxPx = rect.left + (compassCxLogical / vb[2]) * rect.width;
    const cyPx = rect.top + (compassCyLogical / vb[3]) * rect.height;
    this._houseDragState = { cxPx, cyPx, cx: compassCxLogical, cy: compassCyLogical };
    target.style.cursor = "grabbing";
    this._houseDragMoveBound = (ev) => this._handleHouseDragMove(ev);
    this._houseDragEndBound = (ev) => this._handleHouseDragEnd(ev);
    window.addEventListener("pointermove", this._houseDragMoveBound);
    window.addEventListener("pointerup", this._houseDragEndBound);
    window.addEventListener("pointercancel", this._houseDragEndBound);
  }

  _handleHouseDragMove(e) {
    if (!this._houseDragState) return;
    e.preventDefault();
    const { cxPx, cyPx } = this._houseDragState;
    const dx = e.clientX - cxPx;
    const dy = e.clientY - cyPx;
    // SVG rotate(0) keeps the house upright: north up, its front (south
    // side) at the bottom. atan2(dy, dx) returns 0 for the +x screen axis, so
    // take 90° off to make the bottom of the compass the zero; clockwise on
    // screen stays clockwise (same rotation values as before).
    let angle = Math.atan2(dy, dx) * 180 / Math.PI - 90;
    while (angle > 180) angle -= 360;
    while (angle < -180) angle += 360;
    if (e.shiftKey) {
      angle = Math.round(angle / 45) * 45;
    } else {
      angle = Math.round(angle * 2) / 2; // 0.5° steps
    }
    // Update transform inline (avoid full SVG re-render during drag)
    const houseG = this.shadowRoot.querySelector("#compass-house");
    if (houseG) {
      houseG.setAttribute("transform", `rotate(${angle}, ${this._houseDragState.cx}, ${this._houseDragState.cy})`);
    }
    const degLabel = this.shadowRoot.querySelector("#compass-degree-label");
    if (degLabel) degLabel.textContent = `${angle}°`;
    const input = this.shadowRoot.querySelector("#house-rotation-input");
    if (input) input.value = angle;
  }

  _removeHouseDragListeners() {
    this._houseDragState = null;
    if (this._houseDragMoveBound) {
      window.removeEventListener("pointermove", this._houseDragMoveBound);
      window.removeEventListener("pointerup", this._houseDragEndBound);
      window.removeEventListener("pointercancel", this._houseDragEndBound);
      this._houseDragMoveBound = null;
      this._houseDragEndBound = null;
    }
  }

  _handleHouseDragEnd(e) {
    if (!this._houseDragState) return;
    this._removeHouseDragListeners();
    const houseG = this.shadowRoot.querySelector("#compass-house");
    if (houseG) houseG.style.cursor = "grab";
    // Trigger the existing live-update path so facade arcs etc. re-render.
    const input = this.shadowRoot.querySelector("#house-rotation-input");
    if (input) input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // Facade azimuth: any number, normalized to [0, 360) (-90 -> 270, 450 -> 90).
  _facadeAz(raw, def) {
    const v = raw === "" || raw == null ? NaN : parseFloat(raw);
    if (!Number.isFinite(v)) return def;
    return Math.round((((v % 360) + 360) % 360) * 1000) / 1000;
  }

  async _onFacadeAddSave(btn) {
    const form = btn.closest(".inline-form");
    if (!form) return;
    const name = form.querySelector('[data-facade-field="name"]')?.value || "";
    if (!name.trim()) return;
    const direction = form.querySelector('[data-facade-field="direction"]')?.value || "south";
    const span = this._facadeMaxSpan(direction);
    const azStart = this._facadeAz(form.querySelector('[data-facade-field="azimuth_start"]')?.value, span.start);
    const azEnd = this._facadeAz(form.querySelector('[data-facade-field="azimuth_end"]')?.value, span.end);
    const minElev = (() => { const v = parseFloat(form.querySelector('[data-facade-field="min_elevation"]')?.value); return Number.isFinite(v) ? Math.max(0, v) : 0; })();
    const coverIds = [];
    form.querySelectorAll('[data-action="facade-cover-toggle"].selected').forEach(b => coverIds.push(b.dataset.cover));
    try {
      const result = await this._ws("cover_automatic/facade/add", {
        name: name.trim(), direction, azimuth_start: azStart, azimuth_end: azEnd, min_elevation: minElev, cover_ids: coverIds
      });
      this._addingFacade = false;
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }

  async _onFacadeEditSave(btn) {
    const facadeId = btn.dataset.id;
    const form = btn.closest(".inline-form");
    if (!form) return;
    const name = form.querySelector('[data-facade-field="name"]')?.value || "";
    if (!name.trim()) return;
    const direction = form.querySelector('[data-facade-field="direction"]')?.value || "south";
    const azStart = this._facadeAz(form.querySelector('[data-facade-field="azimuth_start"]')?.value, 135);
    const azEnd = this._facadeAz(form.querySelector('[data-facade-field="azimuth_end"]')?.value, 225);
    const minElev = (() => { const v = parseFloat(form.querySelector('[data-facade-field="min_elevation"]')?.value); return Number.isFinite(v) ? Math.max(0, v) : 0; })();
    const coverIds = [];
    form.querySelectorAll('[data-action="facade-cover-toggle"].selected').forEach(b => coverIds.push(b.dataset.cover));
    try {
      const result = await this._ws("cover_automatic/facade/update", {
        facade_id: facadeId, name: name.trim(), direction, azimuth_start: azStart, azimuth_end: azEnd, min_elevation: minElev, cover_ids: coverIds
      });
      this._editingFacade = null;
      this._updateConfigFromResult(result);
    } catch (e) { console.error(e); this._showError(e); }
  }

  _onFacadeDelete(facadeId) {
    this._showConfirm(this._t("confirm_delete"), async () => {
      try {
        const result = await this._ws("cover_automatic/facade/delete", { facade_id: facadeId });
        this._updateConfigFromResult(result);
      } catch (e) { console.error(e); this._showError(e); }
    });
  }
};

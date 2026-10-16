// CoverAutomatic panel -- Facades tab, compass and house orientation.
// Mixin of CoverAutomaticPanel (see cover-automatic-panel.js).
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

  _renderCompassSVG(rotation) {
    const cx = 140, cy = 140, r = 88, hr = 28;
    // South at the top (the sun side in the northern hemisphere): north is
    // down, east left, west right. Screen angle of a compass bearing:
    const rad = (az) => (az + 90) * Math.PI / 180;
    const sunState = this._hass ? this._hass.states["sun.sun"] : null;
    const sunAz = sunState ? parseFloat(sunState.attributes.azimuth) : null;
    const sunEl = sunState ? parseFloat(sunState.attributes.elevation) : null;
    const belowHorizon = sunEl != null && sunEl < 0;

    // Sunshine arcs: only the bearings the sun can reach over the year, for
    // the whole house and for each of its sides (north / east / south / west,
    // house rotation applied). The legend below gives the same bearings: the
    // part the sun never reaches is not shown.
    const sector = this._sunSector();
    const arc = (from, sweep, col, arcR, width) => {
      if (sweep >= 359.99) return `<circle cx="${cx}" cy="${cy}" r="${arcR}" fill="none" stroke="${col}" stroke-width="${width}" opacity="0.9"/>`;
      const point = (az) => [cx + arcR * Math.cos(rad(az)), cy + arcR * Math.sin(rad(az))];
      const [x1, y1] = point(from), [x2, y2] = point(from + sweep);
      return `<path d="M${x1},${y1} A${arcR},${arcR} 0 ${sweep > 180 ? 1 : 0},1 ${x2},${y2}" fill="none" stroke="${col}" stroke-width="${width}" opacity="0.9"/>`;
    };
    const houseRot = Number.isFinite(Number(rotation)) ? Number(rotation) : 0;
    // Outer arc: the sunshine sector, in the sun colour. Then two rings for
    // the house sides, each over the bearings from which the sun can light it
    // (90° on each side): north + south on one ring, east + west on the
    // other, so that opposite sides never overlap.
    const sideRing = { north: r - 12, south: r - 12, east: r - 20, west: r - 20 };
    let sunArc = arc(sector.from, sector.sweep, "var(--ca-sun)", r - 5, 3);
    for (const [dir, bearing] of Object.entries(FACADE_BEARINGS)) {
      for (const [from, sweep] of this._clipToSector(bearing - 90 + houseRot, 180, sector)) {
        sunArc += arc(from, sweep, FACADE_SIDE_COLORS[dir], sideRing[dir], 5);
      }
    }
    const deg = (v) => `${Math.round((((v % 360) + 360) % 360))}°`;
    const range = (from, sweep) => sweep >= 359.99 ? "0°–360°" : `${deg(from)}–${deg(from + sweep)}`;
    const legendRow = (dot, name, text) => `<div class="compass-legend-row"><span class="compass-legend-dot" style="background:${dot}"></span><span class="compass-legend-name">${name}</span><span class="compass-legend-az">${text}</span></div>`;
    let legend = legendRow("var(--ca-sun)", this._esc(this._t("compass_sun_range")), range(sector.from, sector.sweep));
    // One row per house side: the bearings from which the sun can light it
    // (90° on each side of its bearing), cut to the sunshine sector.
    for (const [dir, bearing] of Object.entries(FACADE_BEARINGS)) {
      const parts = this._clipToSector(bearing - 90 + houseRot, 180, sector);
      let text = parts.length ? parts.map(([from, sweep]) => range(from, sweep)).join(", ") : "\u2013";
      // Cut in two by the dark sector: whole span first, then its two lit parts
      if (parts.length === 2) text = `${deg(parts[0][0])}–${deg(parts[1][0] + parts[1][1])} (${text})`;
      legend += legendRow(FACADE_SIDE_COLORS[dir], this._esc(this._t("facade_dir_" + dir)), text);
    }

    // Sun position -- soft radial glow behind the disc, fine rays, and a
    // light cone rendered as a directional gradient fading toward the house
    let sunMarker = "";
    let sunBeams = "";
    let beamGradient = "";
    if (sunAz != null && !isNaN(sunAz) && !belowHorizon) {
      const sunRad = rad(sunAz);
      const sr = r + 28;
      const sx = cx + sr * Math.cos(sunRad), sy = cy + sr * Math.sin(sunRad);
      // Sun symbol rays (radiating outward)
      const symbolRays = [0,45,90,135,180,225,270,315].map(d => {
        const rr = d * Math.PI / 180;
        const x1 = sx + 10.5 * Math.cos(rr), y1 = sy + 10.5 * Math.sin(rr);
        const x2 = sx + 14.5 * Math.cos(rr), y2 = sy + 14.5 * Math.sin(rr);
        return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="var(--ca-sun)" stroke-width="1.5" stroke-linecap="round" opacity="0.9"/>`;
      }).join("");
      // Light cone toward house facade (trapezoid: narrow at sun, wide at house)
      const dx = cx - sx, dy = cy - sy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const ndx = dx / dist, ndy = dy / dist;
      const perpX = -ndy, perpY = ndx;
      const sunW = 4;
      const facadeW = hr + 20;
      const facadeDist = dist + hr * 0.5 + 20;
      const fx = sx + ndx * facadeDist, fy = sy + ndy * facadeDist;
      beamGradient = `<linearGradient id="ca-beam" gradientUnits="userSpaceOnUse" x1="${sx}" y1="${sy}" x2="${fx}" y2="${fy}">
          <stop offset="0" stop-color="var(--ca-sun)" stop-opacity="0.22"/>
          <stop offset="1" stop-color="var(--ca-sun)" stop-opacity="0.02"/>
        </linearGradient>`;
      sunBeams = `<polygon points="${sx + perpX * sunW},${sy + perpY * sunW} ${sx - perpX * sunW},${sy - perpY * sunW} ${fx - perpX * facadeW},${fy - perpY * facadeW} ${fx + perpX * facadeW},${fy + perpY * facadeW}" fill="url(#ca-beam)"/>`;
      sunMarker = `<circle cx="${sx}" cy="${sy}" r="20" fill="url(#ca-sun-glow)" pointer-events="none"/>
        ${symbolRays}<circle cx="${sx}" cy="${sy}" r="7" fill="var(--ca-sun)" stroke="var(--ca-sun-outline)" stroke-width="1"/>
        <text x="${sx}" y="${sy + 27}" text-anchor="middle" font-size="9" fill="var(--ca-sun)" font-weight="600">\u2220${Math.round(sunEl)}\u00B0</text>`;
    }

    // Outdoor temperature info text at bottom of SVG
    let infoText = "";
    const settings = this._config ? this._config.settings || {} : {};
    const tempEntity = settings.outdoor_temp_sensor;
    if (tempEntity && this._hass?.states[tempEntity]) {
      const tempState = this._hass.states[tempEntity];
      const tempVal = parseFloat(tempState.state);
      if (!isNaN(tempVal)) {
        infoText = `${this._t("settings_outdoor_temp_short")} ${tempVal.toFixed(1)}\u00B0C`;
      }
    }

    const svgW = 280, svgH = infoText ? 302 : 288;
    const infoSvg = infoText ? `<text x="${cx}" y="${svgH - 4}" text-anchor="middle" font-size="11" fill="var(--ca-secondary-text)">${infoText}</text>` : "";
    return `<svg id="compass-svg" class="compass-svg-root" width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}">
      <defs>
        <filter id="ca-house-shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="1.5" stdDeviation="2.5" flood-color="#000" flood-opacity="0.3"/>
        </filter>
        <radialGradient id="ca-sun-glow">
          <stop offset="0" stop-color="var(--ca-sun)" stop-opacity="0.35"/>
          <stop offset="1" stop-color="var(--ca-sun)" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="ca-house-sheen" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#fff" stop-opacity="0.09"/>
          <stop offset="1" stop-color="#fff" stop-opacity="0"/>
        </linearGradient>
        ${beamGradient}
      </defs>
      <!-- Compass rings: quiet outer ring, fine dotted inner ring -->
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--divider-color)" stroke-width="1"/>
      <circle cx="${cx}" cy="${cy}" r="${r - 28}" fill="none" stroke="var(--divider-color)" stroke-width="1" stroke-dasharray="0.5 6" stroke-linecap="round" opacity="0.8"/>
      <!-- Cardinal directions (fixed); N carries the accent as rotation reference -->
      <text x="${cx}" y="${cy + r + 18}" text-anchor="middle" font-size="12" font-weight="700" letter-spacing="1" fill="var(--ca-primary)">${this._esc(this._t("compass_n"))}</text>
      <text x="${cx}" y="${cy - r - 8}" text-anchor="middle" font-size="12" font-weight="600" letter-spacing="1" fill="var(--ca-secondary-text)">${this._esc(this._t("compass_s"))}</text>
      <text x="${cx - r - 11}" y="${cy + 4}" text-anchor="middle" font-size="12" font-weight="600" letter-spacing="1" fill="var(--ca-secondary-text)">${this._esc(this._t("compass_e"))}</text>
      <text x="${cx + r + 11}" y="${cy + 4}" text-anchor="middle" font-size="12" font-weight="600" letter-spacing="1" fill="var(--ca-secondary-text)">${this._esc(this._t("compass_w"))}</text>
      <!-- North marker (bottom): filled triangle pointing inward from the ring -->
      <polygon points="${cx - 3.5},${cy + r} ${cx + 3.5},${cy + r} ${cx},${cy + r - 8}" fill="var(--ca-primary)"/>
      <!-- Tick marks (north replaced by the triangle marker) -->
      ${[45,90,135,180,225,270,315].map(d => { const rad=(d+90)*Math.PI/180; const i=d%90===0?5:3; return `<line x1="${cx+r*Math.cos(rad)}" y1="${cy+r*Math.sin(rad)}" x2="${cx+(r+i)*Math.cos(rad)}" y2="${cy+(r+i)*Math.sin(rad)}" stroke="var(--primary-text-color)" stroke-width="${d%90===0?1.5:1}" opacity="${d%90===0?0.5:0.25}"/>`; }).join("")}
      <!-- Sun beams (behind house) -->
      ${sunBeams}
      <!-- House (rotated, on top of beams) -->
      <g id="compass-house" transform="rotate(${rotation}, ${cx}, ${cy})" data-action="house-drag-start" filter="url(#ca-house-shadow)">
        <rect x="${cx - hr}" y="${cy - hr}" width="${hr * 2}" height="${hr * 2}" rx="4" fill="var(--primary-background-color, #1c1c1c)" stroke="var(--primary-color)" stroke-width="1.5"/>
        <rect x="${cx - hr + 1.5}" y="${cy - hr + 1.5}" width="${hr * 2 - 3}" height="${hr * 2 - 3}" rx="3" fill="url(#ca-house-sheen)" stroke="none" pointer-events="none"/>
        <!-- Roof indicator (front = south of house before rotation, at the top) -->
        <line x1="${cx - hr + 7}" y1="${cy - hr}" x2="${cx + hr - 7}" y2="${cy - hr}" stroke="var(--primary-color)" stroke-width="2.5" stroke-linecap="round" pointer-events="none"/>
        <text id="compass-degree-label" x="${cx}" y="${cy + 4}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--primary-text-color)" opacity="0.75" pointer-events="none">${rotation}°</text>
      </g>
      <!-- Sunshine sector: sun-coloured arc, north-south ring, east-west ring -->
      ${sunArc}
      <!-- Sun -->
      ${sunMarker}
      <!-- Info -->
      ${infoSvg}
    </svg><div class="compass-legend">${legend}</div>`;
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
    const compassCxLogical = 140; // matches _renderCompassSVG cx/cy
    const compassCyLogical = 140;
    const cxPx = rect.left + (compassCxLogical / vb[2]) * rect.width;
    const cyPx = rect.top + (compassCyLogical / vb[3]) * rect.height;
    this._houseDragState = { cxPx, cyPx };
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
    // SVG rotate(0) keeps the house upright (front at the top = south).
    // atan2(dy, dx) returns 0 for the +x screen axis, so add 90° to make the
    // top of the compass the zero; clockwise on screen stays clockwise.
    let angle = Math.atan2(dy, dx) * 180 / Math.PI + 90;
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
      houseG.setAttribute("transform", `rotate(${angle}, 140, 140)`);
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

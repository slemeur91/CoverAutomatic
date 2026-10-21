// CoverAutomatic panel -- sky compass and today's sun curve (Settings > House).
// Sun and moon positions from the usual low-precision formulas (accurate to a
// fraction of a degree, enough for a drawing).

const RAD = Math.PI / 180;
const DAY_MS = 86400000;
const J1970 = 2440588;
const J2000 = 2451545;
const OBLIQUITY = RAD * 23.4397;

const toDays = (date) => date.valueOf() / DAY_MS - 0.5 + J1970 - J2000;
const rightAscension = (l, b) => Math.atan2(Math.sin(l) * Math.cos(OBLIQUITY) - Math.tan(b) * Math.sin(OBLIQUITY), Math.cos(l));
const declination = (l, b) => Math.asin(Math.sin(b) * Math.cos(OBLIQUITY) + Math.cos(b) * Math.sin(OBLIQUITY) * Math.sin(l));
const siderealTime = (d, lw) => RAD * (280.16 + 360.9856235 * d) - lw;
const altitude = (H, phi, dec) => Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(H));
const azimuthSouth = (H, phi, dec) => Math.atan2(Math.sin(H), Math.cos(H) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi));

function sunCoords(d) {
  const M = RAD * (357.5291 + 0.98560028 * d);
  const C = RAD * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M));
  const L = M + C + RAD * 102.9372 + Math.PI;
  return { dec: declination(L, 0), ra: rightAscension(L, 0) };
}

function moonCoords(d) {
  const L = RAD * (218.316 + 13.176396 * d);
  const M = RAD * (134.963 + 13.064993 * d);
  const F = RAD * (93.272 + 13.22935 * d);
  const l = L + RAD * 6.289 * Math.sin(M);
  const b = RAD * 5.128 * Math.sin(F);
  return { ra: rightAscension(l, b), dec: declination(l, b), dist: 385001 - 20905 * Math.cos(M) };
}

// Compass bearings: azimuth from north, clockwise, in degrees
const toBearing = (azS) => ((azS / RAD + 180) % 360 + 360) % 360;

export function sunPosition(date, lat, lon) {
  const lw = RAD * -lon, phi = RAD * lat, d = toDays(date);
  const c = sunCoords(d);
  const H = siderealTime(d, lw) - c.ra;
  return { azimuth: toBearing(azimuthSouth(H, phi, c.dec)), elevation: altitude(H, phi, c.dec) / RAD };
}

export function moonPosition(date, lat, lon) {
  const lw = RAD * -lon, phi = RAD * lat, d = toDays(date);
  const c = moonCoords(d);
  const H = siderealTime(d, lw) - c.ra;
  let h = altitude(H, phi, c.dec);
  h += RAD * 0.017 / Math.tan(h + RAD * 10.26 / (h / RAD + 5.10)); // refraction
  return { azimuth: toBearing(azimuthSouth(H, phi, c.dec)), elevation: h / RAD };
}

// phase: 0 new, 0.25 first quarter, 0.5 full, 0.75 last quarter
export function moonIllumination(date) {
  const d = toDays(date);
  const s = sunCoords(d), m = moonCoords(d);
  const sdist = 149598000;
  const phi = Math.acos(Math.sin(s.dec) * Math.sin(m.dec) + Math.cos(s.dec) * Math.cos(m.dec) * Math.cos(s.ra - m.ra));
  const inc = Math.atan2(sdist * Math.sin(phi), m.dist - sdist * Math.cos(phi));
  const angle = Math.atan2(Math.cos(s.dec) * Math.sin(s.ra - m.ra),
    Math.sin(s.dec) * Math.cos(m.dec) - Math.cos(s.dec) * Math.sin(m.dec) * Math.cos(s.ra - m.ra));
  return { fraction: (1 + Math.cos(inc)) / 2, phase: 0.5 + 0.5 * inc * (angle < 0 ? -1 : 1) / Math.PI };
}

export function moonPhaseKey(phase) {
  const keys = ["new", "waxing_crescent", "first_quarter", "waxing_gibbous", "full", "waning_gibbous", "last_quarter", "waning_crescent"];
  return keys[Math.round(phase * 8) % 8];
}

// Same test as sun.py _sun_hits_facade
export function sunHitsFacade(f, azimuth, elevation) {
  if (elevation < Math.max(Number(f.min_elevation) || 0, 0)) return false;
  const start = Number(f.azimuth_start) || 0, end = Number(f.azimuth_end) || 0;
  if (start === end) return true;
  return start <= end ? azimuth >= start && azimuth <= end : azimuth >= start || azimuth <= end;
}

// Midnight of the day of `date` in a time zone (Home Assistant's), as a Date.
// Without a usable zone: the browser's local midnight.
export function dayStartIn(date, timeZone) {
  const local = () => { const d = new Date(date); d.setHours(0, 0, 0, 0); return d; };
  if (!timeZone) return local();
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
    }).formatToParts(date);
    const get = (type) => Number(parts.find((p) => p.type === type).value);
    const wall = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
    const offset = wall - Math.floor(date.valueOf() / 1000) * 1000;
    return new Date(Date.UTC(get("year"), get("month") - 1, get("day")) - offset);
  } catch (err) {
    return local();
  }
}

// The sun over a day, one sample every `stepMin` minutes from `start`
// (midnight, see dayStartIn); `min` is the minute of the day.
export function sunDay(start, lat, lon, stepMin = 5) {
  const out = [];
  for (let m = 0; m <= 1440; m += stepMin) {
    const t = new Date(start.valueOf() + m * 60000);
    out.push({ min: m, t, ...sunPosition(t, lat, lon) });
  }
  return out;
}

// Sunlit intervals of a facade over the samples: [[startMin, endMin], ...]
export function facadeWindows(f, samples) {
  const out = [];
  let open = null;
  for (const s of samples) {
    const hit = sunHitsFacade(f, s.azimuth, s.elevation);
    if (hit && open === null) open = s.min;
    if (!hit && open !== null) { out.push([open, s.min]); open = null; }
  }
  if (open !== null) out.push([open, 1440]);
  return out;
}

export const FACADE_PALETTE = ["#4e9af1", "#f2994a", "#27ae60", "#eb5757", "#9b51e0", "#2d9cdb", "#d4a017", "#8d6e63", "#16a085", "#e056a0"];

export const hhmm = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(Math.round(min % 60)).padStart(2, "0")}`;

function moonGlyph(x, y, r, phase) {
  const k = Math.cos(2 * Math.PI * phase);
  const waxing = phase < 0.5;
  const rx = Math.abs(k) * r;
  const a1 = waxing ? 1 : 0;
  const a2 = waxing ? (k > 0 ? 0 : 1) : (k > 0 ? 1 : 0);
  const lit = `M${x},${y - r} A${r},${r} 0 0 ${a1} ${x},${y + r} A${rx},${r} 0 0 ${a2} ${x},${y - r}Z`;
  return `<circle cx="${x}" cy="${y}" r="${r}" fill="var(--ca-moon-dark, #555)"/><path d="${lit}" fill="var(--ca-moon, #e8e8e8)"/>
    <circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="var(--ca-moon-edge, rgba(127,127,127,.6))" stroke-width="0.8"/>`;
}

/**
 * Sky compass: north at the top, the sky seen from above (horizon on the
 * outer ring, zenith at the centre), today's sun path, sun, moon, the house
 * in the middle and coloured arcs around the horizon.
 * opts: { samples, sunNow:{azimuth,elevation}, moonNow, moonPhase,
 *   labels:{n,e,s,w}, arcs:[{from, sweep, color, ring, width}], house:{rotation} }
 */
export function renderSkyCompass(opts) {
  const R = 112, ringStep = 9, rings = Math.max(0, ...opts.arcs.map((a) => a.ring + 1));
  const Rl = R + 6 + rings * ringStep + 10;
  const S = 2 * Rl + 24, cx = S / 2, cy = S / 2;
  const rOf = (el) => R * (90 - Math.max(el, 0)) / 90;
  const pt = (az, r) => [cx + r * Math.sin(az * RAD), cy - r * Math.cos(az * RAD)];
  const arcPath = (a0, sweep, r) => {
    if (sweep >= 359.99) return `M${cx - r},${cy} a${r},${r} 0 1,0 ${2 * r},0 a${r},${r} 0 1,0 ${-2 * r},0`;
    const [x0, y0] = pt(a0, r), [x1, y1] = pt(a0 + sweep, r);
    return `M${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 ${sweep > 180 ? 1 : 0},1 ${x1.toFixed(1)},${y1.toFixed(1)}`;
  };
  let svg = `<svg id="compass-svg" class="compass-svg-root sky-compass" viewBox="0 0 ${S} ${S}" width="${S}" height="${S}" data-cx="${cx}" data-cy="${cy}" role="img">`;
  for (const el of [0, 30, 60]) svg += `<circle cx="${cx}" cy="${cy}" r="${rOf(el)}" fill="none" stroke="var(--divider-color)" stroke-width="${el === 0 ? 1.2 : 0.8}"${el ? ' stroke-dasharray="2 4"' : ""}/>`;
  svg += `<line x1="${cx}" y1="${cy - R}" x2="${cx}" y2="${cy + R}" stroke="var(--divider-color)" stroke-width="0.6"/><line x1="${cx - R}" y1="${cy}" x2="${cx + R}" y2="${cy}" stroke="var(--divider-color)" stroke-width="0.6"/>`;
  svg += `<text x="${cx + 3}" y="${cy - rOf(30) + 10}" font-size="8" fill="var(--secondary-text-color)">30°</text><text x="${cx + 3}" y="${cy - rOf(60) + 10}" font-size="8" fill="var(--secondary-text-color)">60°</text>`;
  for (const a of opts.arcs) {
    const r = R + 6 + a.ring * ringStep;
    svg += `<path d="${arcPath(a.from, a.sweep, r)}" fill="none" stroke="${a.color}" stroke-width="${a.width || 4}" stroke-linecap="round" opacity="${a.opacity ?? 0.9}"${a.dash ? ` stroke-dasharray="${a.dash}"` : ""}/>`;
    if (a.label) {
      const [lx, ly] = pt(a.from + a.sweep / 2, r);
      svg += `<circle cx="${lx}" cy="${ly}" r="6.5" fill="${a.color}"/><text x="${lx}" y="${ly + 3}" text-anchor="middle" font-size="8" font-weight="700" fill="#fff">${a.label}</text>`;
    }
  }
  // House in the middle, rotated by the house rotation; its front (south
  // side before rotation) is at the bottom, towards the south.
  if (opts.house) {
    const hr = 19, rot = opts.house.rotation;
    svg += `<g id="compass-house" transform="rotate(${rot}, ${cx}, ${cy})" data-action="house-drag-start" style="cursor:grab">
      <rect x="${cx - hr}" y="${cy - hr}" width="${hr * 2}" height="${hr * 2}" rx="4" fill="var(--card-background-color, #fff)" stroke="var(--primary-color)" stroke-width="1.5"/>
      <line x1="${cx - hr + 6}" y1="${cy + hr}" x2="${cx + hr - 6}" y2="${cy + hr}" stroke="var(--primary-color)" stroke-width="3" stroke-linecap="round" pointer-events="none"/>
      <text id="compass-degree-label" x="${cx}" y="${cy + 4}" text-anchor="middle" font-size="11" font-weight="600" fill="var(--primary-text-color)" opacity="0.8" pointer-events="none">${rot}°</text>
    </g>`;
  }
  const up = opts.samples.filter((p) => p.elevation >= 0);
  if (up.length > 1) {
    const d = up.map((p, i) => { const [x, y] = pt(p.azimuth, rOf(p.elevation)); return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`; }).join("");
    svg += `<path d="${d}" fill="none" stroke="var(--ca-sun, #f5b400)" stroke-width="1.6" stroke-opacity="0.85"/>`;
    for (const p of up) {
      if (p.min % 60 !== 0) continue;
      const [x, y] = pt(p.azimuth, rOf(p.elevation));
      svg += `<circle cx="${x}" cy="${y}" r="1.8" fill="var(--ca-sun, #f5b400)"/>`;
      if (p.min % 180 === 0) svg += `<text x="${x}" y="${y + 11}" text-anchor="middle" font-size="8" fill="var(--secondary-text-color)">${hhmm(p.min).slice(0, 2)}h</text>`;
    }
  }
  if (opts.moonNow) {
    const below = opts.moonNow.elevation < 0;
    const [mx, my] = pt(opts.moonNow.azimuth, below ? R : rOf(opts.moonNow.elevation));
    svg += `<g opacity="${below ? 0.35 : 1}">${moonGlyph(mx, my, 8, opts.moonPhase)}</g>`;
  }
  if (opts.sunNow && opts.sunNow.elevation >= 0) {
    const [sx, sy] = pt(opts.sunNow.azimuth, rOf(opts.sunNow.elevation));
    svg += `<circle cx="${sx}" cy="${sy}" r="15" fill="var(--ca-sun, #f5b400)" opacity="0.2"/><circle cx="${sx}" cy="${sy}" r="8" fill="var(--ca-sun, #f5b400)" stroke="#fff" stroke-width="1.2"/>`;
  } else if (opts.sunNow) {
    const [sx, sy] = pt(opts.sunNow.azimuth, R);
    svg += `<circle cx="${sx}" cy="${sy}" r="6" fill="var(--ca-sun, #f5b400)" opacity="0.35"/>`;
  }
  const L = opts.labels;
  svg += `<text x="${cx}" y="${cy - Rl + 4}" text-anchor="middle" font-size="13" font-weight="700" fill="var(--primary-color)">${L.n}</text>`;
  svg += `<text x="${cx}" y="${cy + Rl + 6}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--secondary-text-color)">${L.s}</text>`;
  svg += `<text x="${cx + Rl}" y="${cy + 4}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--secondary-text-color)">${L.e}</text>`;
  svg += `<text x="${cx - Rl}" y="${cy + 4}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--secondary-text-color)">${L.w}</text>`;
  return svg + "</svg>";
}

/**
 * Today's sun: elevation curve over the day, current time, and one strip per
 * facade with the times the sun is on it. opts: { samples, nowMin, sunNow,
 * facades (with windows, color, name), labels:{now} }
 */
export function renderSunToday(opts) {
  const W = 720, padL = 130, padR = 110, top = 12, chartH = 150;
  const stripH = 20, stripGap = 4;
  const n = opts.facades.length;
  const H = top + chartH + 26 + n * (stripH + stripGap) + 4;
  const x = (min) => padL + (W - padL - padR) * min / 1440;
  const maxEl = Math.max(30, ...opts.samples.map((s) => s.elevation));
  const minEl = Math.min(-1, ...opts.samples.map((s) => s.elevation));
  const yMax = Math.ceil(maxEl / 30) * 30, yMin = minEl;
  // Below the horizon the curve is squeezed into a thin band under 0°,
  // smoothly (same slope at 0°, flattening towards the bottom of the band)
  const negH = chartH * 0.12, posH = chartH - negH;
  const k = (posH / yMax) / negH;
  const y = (el) => (el >= 0 ? top + posH * (yMax - el) / yMax : top + posH + negH * (1 - Math.exp(el * k)));
  let svg = `<svg class="sun-today" viewBox="0 0 ${W} ${H}" width="100%" role="img">`;
  // Grid
  for (let el = 0; el <= yMax; el += 30) {
    svg += `<line x1="${padL}" y1="${y(el)}" x2="${W - padR}" y2="${y(el)}" stroke="var(--divider-color)" stroke-width="${el === 0 ? 1 : 0.6}"${el === 0 ? ' stroke-dasharray="4 3"' : ""}/>`;
    svg += `<text x="${padL - 6}" y="${y(el) + 3}" text-anchor="end" font-size="10" fill="var(--secondary-text-color)">${el}°</text>`;
  }
  for (let h = 0; h <= 24; h += 3) {
    svg += `<line x1="${x(h * 60)}" y1="${top}" x2="${x(h * 60)}" y2="${top + chartH}" stroke="var(--divider-color)" stroke-width="0.5" opacity="0.6"/>`;
    svg += `<text x="${x(h * 60)}" y="${top + chartH + 14}" text-anchor="middle" font-size="10" fill="var(--secondary-text-color)">${String(h).padStart(2, "0")}:00</text>`;
  }
  // Night shading below the horizon line
  svg += `<rect x="${padL}" y="${y(0)}" width="${W - padL - padR}" height="${negH}" fill="var(--secondary-text-color)" opacity="0.06"/>`;
  // Elevation curve, cut at the bottom of the chart
  svg += `<clipPath id="sun-today-clip"><rect x="${padL}" y="${top}" width="${W - padL - padR}" height="${chartH}"/></clipPath>`;
  const d = opts.samples.map((s, i) => `${i ? "L" : "M"}${x(s.min).toFixed(1)},${y(s.elevation).toFixed(1)}`).join("");
  svg += `<path d="${d}" fill="none" stroke="var(--ca-curve, #2d9cdb)" stroke-width="2.4" clip-path="url(#sun-today-clip)"/>`;
  // Now: vertical line and sun on the curve
  if (opts.nowMin != null) {
    const nx = x(opts.nowMin);
    const ny = y(Math.max(opts.sunNow.elevation, yMin)); // below the chart: kept on its bottom edge
    svg += `<line x1="${nx}" y1="${top}" x2="${nx}" y2="${top + chartH + 26 + n * (stripH + stripGap) - stripGap}" stroke="var(--ca-sun, #f5b400)" stroke-width="1.4"/>`;
    svg += `<circle cx="${nx}" cy="${ny}" r="6" fill="var(--ca-sun, #f5b400)" stroke="#fff" stroke-width="1.2"/>`;
    svg += `<text x="${nx + 9}" y="${ny - 8}" font-size="10" font-weight="600" fill="var(--ca-sun, #f5b400)">${Math.round(opts.sunNow.elevation)}°</text>`;
  }
  // One strip per facade
  let sy = top + chartH + 26;
  for (const f of opts.facades) {
    svg += `<rect x="${padL}" y="${sy}" width="${W - padL - padR}" height="${stripH}" rx="4" fill="var(--secondary-text-color)" opacity="0.07"/>`;
    svg += `<circle cx="10" cy="${sy + stripH / 2}" r="5" fill="${f.color}"/>`;
    svg += `<text x="20" y="${sy + stripH / 2 + 4}" font-size="11" fill="var(--primary-text-color)">${f.name}</text>`;
    for (const [a, b] of f.windows) {
      svg += `<rect x="${x(a)}" y="${sy + 2}" width="${Math.max(2, x(b) - x(a))}" height="${stripH - 4}" rx="3" fill="${f.color}" opacity="0.85"/>`;
    }
    const times = f.windows.length ? f.windows.map(([a, b]) => `${hhmm(a)}–${hhmm(b)}`).join(", ") : opts.labels.noSun;
    svg += `<text x="${W - padR + 8}" y="${sy + stripH / 2 + 4}" font-size="10.5" fill="var(--${f.windows.length ? "primary" : "secondary"}-text-color)" style="font-variant-numeric: tabular-nums">${times}</text>`;
    sy += stripH + stripGap;
  }
  return svg + "</svg>";
}

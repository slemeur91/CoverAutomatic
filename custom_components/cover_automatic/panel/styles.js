// CoverAutomatic panel -- styles of the shadow root.

/* ============================================================
 * Styles
 * ============================================================ */
export const PANEL_STYLES = `
  :host {
    display: block;
    font-family: var(--paper-font-body1_-_font-family, Roboto, Noto, sans-serif);
    color: var(--primary-text-color, #212121);
    background: var(--primary-background-color, #fafafa);
    --ca-primary: var(--primary-color, #03a9f4);
    /* Semantic role aliases (do not change values, just clarify intent at call site):
       --ca-action  = interactive UI (buttons, tabs, toggles, links) -> follows HA theme primary
       --ca-active  = "this is running right now" status (active rule, active scenario) -> green
       --ca-warning = transient warning (paused, threshold exceeded) -> orange
       --ca-danger  = blocked/protective state (locked, wind protection) -> red
       --ca-info    = neutral info / cool indicator (manual, venting, cooling) -> blue */
    --ca-action: var(--ca-primary);
    --ca-active: var(--ca-success-strong, #4caf50);
    --ca-card-bg: var(--ha-card-background, var(--card-background-color, #fff));
    --ca-border: var(--divider-color, #e0e0e0);
    --ca-box-border: color-mix(in srgb, var(--primary-text-color, #212121) 25%, transparent);
    --ca-sep: color-mix(in srgb, var(--primary-text-color, #212121) 45%, transparent);
    --ca-secondary-text: var(--secondary-text-color, #727272);
    --ca-error: var(--error-color, #db4437);
    --ca-success: var(--success-color, #43a047);
    --ca-success-strong: #4caf50;
    --ca-warning: var(--warning-color, #e67e22);
    --ca-info: var(--info-color, #2196f3);
    --ca-danger: var(--state-icon-error-color, #c62828);
    --ca-danger-bg: #fce4ec;
    --ca-sun: var(--ca-sun-color, #f9a825);
    --ca-sun-outline: var(--ca-sun-outline-color, #F57F17);
    --ca-radius: 12px;
    --ca-shadow: 0 2px 8px rgba(0,0,0,0.08);
    --ca-transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }
  *, *::before, *::after { box-sizing: border-box; }

  /* Layout */
  .panel-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 16px;
  }

  /* Header */
  .menu-btn {
    display: none;
    background: none;
    border: none;
    color: var(--primary-text-color);
    cursor: pointer;
    padding: 8px;
    margin: -8px 4px -8px -8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .menu-btn:hover { background: rgba(128,128,128,0.2); }
  .menu-btn svg { display: block; }
  @media (max-width: 870px) {
    .menu-btn { display: flex; align-items: center; justify-content: center; }
  }
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0 8px;
    margin-bottom: 8px;
    gap: 12px;
  }
  .panel-header h1 {
    font-size: 24px;
    font-weight: 500;
    margin: 0;
    letter-spacing: -0.5px;
  }
  .header-left {
    display: flex;
    align-items: center;
    flex: 0 0 auto;
  }
  .info-bar-slot { display: contents; }
  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .info-bar {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--ca-secondary-text);
    flex-wrap: wrap;
  }
  .info-widget {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
    border: 1px solid color-mix(in srgb, var(--primary-text-color) 8%, transparent);
    white-space: nowrap;
    line-height: 1.3;
    transition: background var(--ca-transition), border-color var(--ca-transition), color var(--ca-transition);
  }
  .info-widget:hover {
    background: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
  }
  .info-widget-value {
    color: var(--primary-text-color);
    font-weight: 500;
  }
  .info-widget.info-widget-highlight {
    background: color-mix(in srgb, var(--ca-warning) 18%, transparent);
    border-color: color-mix(in srgb, var(--ca-warning) 40%, transparent);
    color: var(--ca-warning);
  }
  .info-widget.info-widget-highlight .info-widget-value {
    color: var(--ca-warning);
    font-weight: 600;
  }
  .info-bar-icon {
    flex-shrink: 0;
  }
  .sun-icon-svg {
    color: var(--ca-sun);
    vertical-align: -2px;
  }
  .scenario-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--ca-primary);
    color: #fff;
    padding: 4px 14px;
    border-radius: 16px;
    font-size: 13px;
    font-weight: 500;
  }
  .scenario-badge-icon {
    --mdc-icon-size: 16px;
    margin-right: 4px;
  }
  .version-info {
    font-size: 12px;
    color: var(--ca-secondary-text);
    opacity: 0.7;
    margin-left: 8px;
    text-decoration: none;
  }
  a.version-info:hover {
    opacity: 1;
    text-decoration: underline;
  }
  .uptodate-badge {
    display: inline-flex;
    align-items: center;
    margin-left: 8px;
    padding: 2px 9px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    color: var(--ca-success);
    background: color-mix(in srgb, var(--ca-success) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--ca-success) 40%, transparent);
  }
  .update-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: #4CAF50;
    color: #fff;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    margin-left: 8px;
  }
  .update-badge:hover { opacity: 0.85; }

  /* Tabs */
  .tab-bar {
    display: flex;
    gap: 2px;
    border-bottom: 2px solid var(--ca-border);
    margin-bottom: 20px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scroll-snap-type: x proximity;
  }
  .tab-bar button {
    scroll-snap-align: start;
    flex: 0 0 auto;
    background: none;
    border: none;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    color: var(--ca-secondary-text);
    cursor: pointer;
    position: relative;
    transition: color var(--ca-transition);
    white-space: nowrap;
    font-family: inherit;
  }
  .tab-bar button:hover { color: var(--primary-text-color); }
  .tab-bar button.active {
    color: var(--ca-primary);
  }
  .tab-bar button.active::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--ca-primary);
    border-radius: 2px 2px 0 0;
  }

  /* Cards */
  .card {
    background: var(--ca-card-bg);
    border-radius: var(--ca-radius);
    box-shadow: var(--ca-shadow);
    border: 1px solid var(--ca-border);
    overflow: hidden;
    /* clip (where supported) keeps the rounded corners without becoming a
       scroll container, so the rule editor's sticky save bar can stick. */
    overflow: clip;
    transition: box-shadow var(--ca-transition);
  }
  .card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
  .card-header {
    padding: 16px 20px;
    font-weight: 500;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .card-body { padding: 0 20px 20px; }

  /* Card grid */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  /* Table */
  .table-scroll {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .data-table {
    width: 100%;
    border-collapse: collapse;
  }
  .data-table td.last-change {
    font-size: 12px;
    color: var(--ca-secondary-text);
    white-space: nowrap;
  }
  /* Inline rule link inside cover table -- jumps to Rules tab and highlights the rule */
  .data-table .rule-link {
    color: var(--ca-action);
    text-decoration: none;
    border-bottom: 1px dashed color-mix(in srgb, var(--ca-action) 40%, transparent);
    cursor: pointer;
    transition: color var(--ca-transition), border-bottom-color var(--ca-transition);
  }
  .data-table .rule-link:hover,
  .data-table .rule-link:focus-visible {
    color: var(--ca-action);
    border-bottom-color: var(--ca-action);
    outline: none;
  }
  .data-table th.row-chevron-head {
    width: 24px;
    padding-left: 0;
    padding-right: 12px;
  }
  .data-table th, .data-table td {
    text-align: left;
    padding: 12px 16px;
    border-bottom: 1px solid var(--ca-border);
  }
  .data-table th {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--ca-secondary-text);
    background: var(--ca-card-bg);
    position: sticky;
    top: 0;
    z-index: 1;
    white-space: nowrap;
  }
  .data-table th.sortable {
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  .data-table th.sortable:hover {
    color: var(--primary-text-color);
  }
  /* Keyboard focus for row/header activation (tabindex targets) */
  .data-table th.sortable:focus-visible,
  .data-table tr[data-action]:focus-visible {
    outline: 2px solid var(--ca-primary);
    outline-offset: -2px;
  }
  .data-table th .sort-arrow {
    display: inline-block;
    margin-left: 4px;
    font-size: 10px;
    opacity: 0;
    color: var(--ca-primary);
    transition: opacity var(--ca-transition);
  }
  .data-table th.sortable:hover .sort-arrow {
    opacity: 0.35;
    color: var(--ca-secondary-text);
  }
  .data-table th.sorted .sort-arrow {
    opacity: 1;
    color: var(--ca-primary);
  }
  .data-table tr {
    cursor: pointer;
    transition: background var(--ca-transition);
  }
  .data-table tbody tr:hover {
    background: color-mix(in srgb, var(--ca-primary) 10%, transparent);
  }
  .data-table tbody tr.selected {
    background: color-mix(in srgb, var(--ca-primary) 16%, transparent);
  }
  .data-table td.row-chevron {
    width: 24px;
    padding-left: 8px;
    padding-right: 12px;
    text-align: right;
    color: var(--ca-secondary-text);
    opacity: 0.35;
    transition: opacity var(--ca-transition), transform var(--ca-transition), color var(--ca-transition);
  }
  .data-table tbody tr:hover td.row-chevron {
    opacity: 1;
    transform: translateX(2px);
    color: var(--ca-primary);
  }
  .data-table td.row-chevron svg {
    display: block;
    margin-left: auto;
  }

  /* Status badge */
  .status-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 500;
    text-transform: capitalize;
  }
  .status-auto {
    background: color-mix(in srgb, var(--ca-active) 14%, transparent);
    color: var(--ca-active);
  }
  .status-paused {
    background: color-mix(in srgb, var(--ca-warning) 16%, transparent);
    color: var(--ca-warning);
  }
  .status-manual {
    background: color-mix(in srgb, var(--ca-info) 14%, transparent);
    color: var(--ca-info);
  }
  .status-locked {
    background: color-mix(in srgb, var(--ca-danger) 14%, transparent);
    color: var(--ca-danger);
  }
  .status-venting {
    background: color-mix(in srgb, var(--ca-info) 12%, transparent);
    color: var(--ca-info);
  }
  .status-wind_protected {
    background: color-mix(in srgb, var(--ca-danger) 14%, transparent);
    color: var(--ca-danger);
  }

  /* Slide-out panel */
  .slide-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.3);
    z-index: 100;
    opacity: 0;
    visibility: hidden;
    transition: opacity var(--ca-transition), visibility var(--ca-transition);
  }
  .slide-overlay.open { opacity: 1; visibility: visible; }
  .slide-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 420px;
    max-width: 100vw;
    height: 100%;
    background: var(--primary-background-color, #1c1c1c);
    z-index: 101;
    transform: translateX(100%);
    transition: transform var(--ca-transition);
    display: flex;
    flex-direction: column;
    box-shadow: -4px 0 24px rgba(0,0,0,0.15);
  }
  .slide-panel.open { transform: translateX(0); }
  .slide-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--ca-border);
    flex-shrink: 0;
  }
  .slide-header .slide-back { display: none; }
  /* Cover sheet: the help icon sits on the label line instead of its own line */
  .slide-body .form-group { position: relative; }
  .slide-body .form-group > .field-hint > summary { position: absolute; top: 0; right: 0; }
  .slide-body .form-group:has(> .field-hint) > label { padding-right: 24px; }
  .slide-body .sep-item, .slide-body .threshold-entity, .slide-body .opt-box { position: relative; }
  .slide-body .sep-item > .field-hint > summary,
  .slide-body .threshold-entity > .field-hint > summary { position: absolute; top: 0; right: 0; }
  .slide-body .opt-box-body > .field-hint > summary { position: absolute; top: 12px; right: 14px; }
  .toggle-row .toggle-label { display: block; flex: 1; min-width: 0; }
  .toggle-row .toggle-label .field-hint { display: inline; margin: 0 0 0 2px; }
  .toggle-row .toggle-label .field-hint > summary { display: inline-flex; vertical-align: middle; padding: 0 4px; }
  .toggle-row .toggle-label .field-hint[open] .hint-body { display: block; }
  .lbl-short { display: none; }
  @media (max-width: 600px) {
    .lbl-long { display: none; }
    .lbl-short { display: inline; }
  }
  .slide-expand-bar { display: flex; justify-content: flex-end; margin: -8px 0 4px; }
  .slide-header .btn-icon:focus:not(:focus-visible) { outline: none; }
  .slide-close-bottom { display: none; }
  .slide-header h2 {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin: 0;
    font-size: 18px;
    font-weight: 500;
  }
  .slide-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
  }

  /* Form elements */
  .form-group {
    margin-bottom: 16px;
  }
  .form-group label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--ca-secondary-text);
    margin-bottom: 4px;
  }
  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group input[type="time"],
  .form-group select,
  .form-group textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color);
    font-size: 14px;
    font-family: inherit;
    outline: none;
    transition: border-color var(--ca-transition);
  }
  .form-group input:focus,
  .form-group select:focus,
  .form-group textarea:focus {
    border-color: var(--ca-primary);
  }
  .form-group input.input-invalid,
  input.input-invalid {
    border-color: var(--ca-danger);
    box-shadow: 0 0 0 1px var(--ca-danger);
  }
  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    align-items: start;
  }

  /* Settings shell: sidebar + content */
  .settings-shell {
    display: flex;
    gap: 24px;
    align-items: flex-start;
  }
  .settings-nav {
    flex: 0 0 220px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    position: sticky;
    top: 16px;
    padding: 8px;
    background: var(--ca-card-bg);
    border: 1px solid var(--ca-border);
    border-radius: var(--ca-radius);
  }
  .settings-nav-btn {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ca-secondary-text);
    font-size: 14px;
    font-family: inherit;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: background var(--ca-transition), color var(--ca-transition);
  }
  .settings-nav-btn:hover {
    background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
    color: var(--primary-text-color);
  }
  .settings-nav-btn.active {
    background: color-mix(in srgb, var(--ca-primary) 14%, transparent);
    color: var(--ca-primary);
  }
  .settings-nav-btn .settings-nav-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    flex-shrink: 0;
  }
  .settings-nav-btn .settings-nav-icon svg {
    width: 18px;
    height: 18px;
  }
  .settings-nav-btn .settings-nav-label {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .settings-content {
    flex: 1;
    min-width: 0;
  }

  /* Settings card stack */
  .settings-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .settings-stack .card-header {
    font-size: 13px;
    font-weight: 600;
    color: var(--ca-secondary-text);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 12px 20px 8px;
    border-bottom: 1px solid var(--ca-border);
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 8px;
  }
  .settings-stack .card-header svg {
    flex-shrink: 0;
    opacity: 0.7;
  }
  /* Hint text below a field (legacy, still used in a few places) */
  .settings-hint {
    font-size: 12px;
    color: var(--ca-secondary-text);
    margin-top: 4px;
    line-height: 1.4;
  }
  /* Intro hint at top of a card section */
  .settings-hint-intro {
    font-size: 12px;
    color: var(--ca-secondary-text);
    margin-bottom: 12px;
    line-height: 1.4;
  }
  /* Field-level collapsible hint */
  .field-hint {
    margin-top: 4px;
  }
  .field-hint summary {
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 6px;
    border-radius: 6px;
    color: var(--ca-secondary-text);
    list-style: none;
    user-select: none;
    transition: background var(--ca-transition), color var(--ca-transition);
  }
  .field-hint summary::-webkit-details-marker { display: none; }
  .field-hint summary::marker { content: ""; }
  .field-hint summary:hover {
    background: color-mix(in srgb, var(--primary-text-color) 8%, transparent);
    color: var(--ca-primary);
  }
  .field-hint[open] summary {
    color: var(--ca-primary);
  }
  .field-hint .hint-body {
    padding: 8px 10px;
    margin-top: 4px;
    background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
    border-left: 2px solid color-mix(in srgb, var(--ca-primary) 50%, transparent);
    border-radius: 4px;
    font-size: 12px;
    color: var(--ca-secondary-text);
    line-height: 1.5;
  }
  /* Sensor live value */
  .sensor-current-value {
    font-size: 12px;
    color: var(--ca-primary);
    margin-top: 3px;
  }
  /* Optional entity providing a threshold (number = fallback) */
  input.entity-driven { display: none; }
  .entity-shadow-value {
    padding: 10px 12px; border-radius: 8px; font-size: 14px;
    border: 1px solid var(--ca-border);
    background: color-mix(in srgb, var(--primary-text-color, #212121) 6%, transparent);
    color: var(--ca-secondary-text);
    max-width: 200px;
  }
  .entity-shadow-note { font-size: 12px; color: var(--ca-secondary-text); margin-top: 4px; }
  .threshold-entity {
    margin-top: 10px;
    padding-left: 10px;
    border-left: 2px solid var(--ca-border);
  }
  .threshold-entity-label {
    font-size: 12px;
    color: var(--ca-secondary-text);
    margin-bottom: 4px;
  }
  .threshold-entity-value {
    font-size: 12px;
    color: var(--ca-primary);
    margin-top: 4px;
    min-height: 0;
  }
  .threshold-entity-value:empty { display: none; }
  .threshold-entity-unavail { color: var(--ca-warning, var(--ca-secondary-text)); }

  /* Settings page: roomier layout (settings tab only) */
  .settings-stack { gap: 20px; }
  .settings-stack .card-header {
    font-size: 15px;
    font-weight: 600;
    color: var(--primary-text-color);
    text-transform: none;
    letter-spacing: 0;
    padding: 16px 24px 14px;
    margin-bottom: 0;
  }
  .settings-stack .card-header svg { color: var(--ca-primary); opacity: 1; }
  .settings-stack .card-body { padding: 20px 24px 24px; }
  .settings-stack .form-group { margin-bottom: 24px; }
  .settings-stack .card-body > .form-group:last-child,
  .settings-stack .card-body > .form-row:last-child { margin-bottom: 0; }
  .settings-stack .form-row > .form-group { margin-bottom: 0; }
  .settings-stack .form-group > label:not(.checkbox-row) { margin-bottom: 6px; }
  .settings-stack .form-row {
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 24px 28px;
    margin-bottom: 24px;
  }
  .settings-stack .form-group input[type="number"] { max-width: 220px; }
  .settings-stack .form-group select,
  .settings-stack .form-group input[type="text"] { max-width: 480px; }
  .settings-stack .settings-hint { margin-top: 6px; line-height: 1.5; }
  .settings-stack .field-hint { margin-top: 6px; }
  .settings-stack .settings-hint-intro {
    font-size: 13px;
    line-height: 1.55;
    margin-bottom: 24px;
    padding: 10px 14px;
    border-radius: 8px;
    border-left: 3px solid color-mix(in srgb, var(--ca-primary) 55%, transparent);
    background: color-mix(in srgb, var(--ca-primary) 6%, transparent);
  }
  .settings-stack .sensor-current-value { margin-top: 6px; }
  .settings-stack .checkbox-row {
    font-size: 14px;
    text-transform: none;
    letter-spacing: 0;
    color: var(--primary-text-color);
    margin-bottom: 0;
  }
  .settings-stack .checkbox-row input { width: 18px; height: 18px; margin: 0; }
  .settings-save-bar { padding-top: 4px; }
  .pos-inverted { display: inline-flex; align-items: center; gap: 4px; }
  .pos-inverted-mark { font-size: 12px; color: var(--secondary-text-color, #727272); cursor: help; }
  .radio-group { display: flex; flex-direction: column; gap: 10px; margin-top: 6px; }
  .form-group .radio-row, .form-group .radio-row * { text-transform: none; letter-spacing: normal; }
  .form-group .radio-row { display: flex; align-items: flex-start; gap: 10px; cursor: pointer; font-weight: normal; font-size: 14px; color: var(--primary-text-color); margin: 0; }
  .form-group .radio-row b { font-weight: 500; }
  .radio-row input { margin-top: 3px; width: 16px; height: 16px; flex: none; }
  .sun-explain { margin-top: 12px; border: 1px solid var(--ca-box-border); border-radius: 8px; }
  .sun-explain summary { cursor: pointer; padding: 8px 12px; font-size: 13px; font-weight: 500; color: var(--primary-color); }
  .sun-explain-body { padding: 0 12px 12px; }
  .sun-explain-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
  .sun-explain-table th { text-align: left; font-weight: 500; font-size: 12px; color: var(--secondary-text-color, #727272); padding: 6px 8px; border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  .sun-explain-table td { padding: 6px 8px; vertical-align: top; border-bottom: 1px solid var(--divider-color, #e0e0e0); color: var(--primary-text-color); }
  .sun-explain-table tr.current td { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
  .sun-explain-table tr.current td:first-child { box-shadow: inset 3px 0 0 var(--primary-color); font-weight: 500; }
  .sun-explain-so { margin-top: 10px; font-size: 13px; color: var(--primary-text-color); }
  .sun-explain-so ul { margin: 4px 0 0; padding-left: 20px; }
  .sun-explain-so li { margin: 3px 0; line-height: 1.45; }
  .radio-hint { font-size: 12px; color: var(--secondary-text-color, #727272); font-weight: normal; text-transform: none; letter-spacing: normal; }
  .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 8px 0 4px; }
  @media (max-width: 900px) { .profile-grid { grid-template-columns: 1fr; } }
  .profile-col { border: 1px solid var(--ca-box-border); border-radius: 10px; padding: 12px 14px; min-width: 0; }
  .profile-col-title { font-weight: 600; margin-bottom: 8px; }
  .profile-col .profile-chips { margin-bottom: 8px; }
  .profile-chips[data-editable="0"] .ms-item, .profile-chips[data-editable="0"] .ms-item:hover { cursor: default; }
  .profile-free { margin-top: 6px; }
  .rich-hint p { margin: 0 0 6px; }
  .rich-hint p:last-child { margin-bottom: 0; }
  .rich-hint ul { margin: 0 0 10px; padding-left: 20px; }
  .rich-hint li { margin: 2px 0; }
  .profile-col .profile-off-note { display: none; font-size: 12px; color: var(--ca-secondary-text); font-style: italic; margin: 4px 0 8px; }
  .profile-col.profile-off .profile-off-note { display: block; }
  .profile-col.profile-off .profile-fields { opacity: 0.45; }
  .profile-col.profile-off .profile-fields * { cursor: not-allowed; }
  .profile-col .sun-explain-table { font-size: 12px; }
  .cover-profile { border-top: 1px solid var(--ca-border); padding-top: 10px; margin-top: 10px; }
  .cover-profile-title { font-weight: 600; margin-bottom: 6px; }
  .cover-profile-title .radio-hint { font-weight: 400; margin-left: 6px; }
  .cover-profile.profile-unused { opacity: 0.7; }
  .cover-profile-warn { display: flex; gap: 6px; align-items: flex-start; font-size: 12px; margin: 0 0 8px; padding: 6px 8px;
    border-radius: 6px; color: var(--ca-warning); background: color-mix(in srgb, var(--ca-warning) 12%, transparent); }
  .opt-box { border: 1px solid var(--ca-box-border); border-radius: 10px; padding: 12px 14px; margin: 0 0 14px;
    background: color-mix(in srgb, var(--primary-text-color, #212121) 2%, transparent); }
  .opt-box > .opt-box-title { padding-bottom: 8px; border-bottom: 1px solid var(--ca-box-border); }
  .sep-list > * + * { border-top: 1px solid var(--ca-sep); margin-top: 12px; padding-top: 12px; }
  .opt-box > .form-group:last-child, .opt-box > .form-row:last-child .form-group { margin-bottom: 0; }
  .sep-list > .form-group:last-child, .sep-list > .sep-item > .form-group:last-child { margin-bottom: 0; }
  .opt-box .opt-box { margin: 10px 0 0; }
  .opt-box.opt-box-flat { border: 0; padding: 0; margin: 0; background: none; }
  .opt-box.opt-box-nested { margin: 8px 0 4px 26px; background: var(--ca-card-bg); }
  .opt-box-body > .form-group:last-child, .opt-box-body > .form-row:last-child .form-group { margin-bottom: 0; }
  .opt-box-title { font-weight: 600; margin-bottom: 10px; }
  .opt-box-offnote { display: none; font-size: 12px; color: var(--secondary-text-color, #727272); margin: 2px 0 8px; font-style: italic; }
  .opt-box.opt-off > .opt-box-offnote { display: block; }
  .opt-box.opt-off > .opt-box-body { opacity: 0.45; }
  /* Only the outermost disabled box fades and explains why */
  .opt-box.opt-off .opt-box.opt-off > .opt-box-body { opacity: 1; }
  .opt-box.opt-off .opt-box .opt-box-offnote { display: none; }
  .opt-box.opt-off > .opt-box-body * { cursor: not-allowed; }
  .settings-unsaved-warning { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; padding: 8px 12px; border-radius: 8px; background: rgba(255, 152, 0, 0.12); color: var(--warning-color, #ff9800); }
  .settings-unsaved-warning .btn { margin-left: auto; }

  /* House card: rotation input + compass side by side */
  .settings-house-layout {
    display: flex;
    gap: 24px;
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .settings-house-input {
    flex: 1;
    min-width: 160px;
  }
  .settings-house-compass {
    flex: 0 0 auto;
  }
  .compass-legend { margin-top: 8px; font-size: 12px; color: var(--primary-text-color); display: grid; gap: 3px; }
  .compass-legend-row { display: flex; align-items: center; gap: 6px; }
  .compass-legend-dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .compass-legend-name { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .compass-legend-az { color: var(--ca-secondary-text); font-variant-numeric: tabular-nums; white-space: nowrap; }
  /* Quick rotate buttons next to the rotation input */
  .rotation-quick {
    display: flex;
    gap: 6px;
    margin-top: 8px;
    flex-wrap: wrap;
  }
  .rotation-quick-btn {
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
    border: 1px solid color-mix(in srgb, var(--primary-text-color) 10%, transparent);
    color: var(--primary-text-color);
    padding: 6px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    cursor: pointer;
    font-family: inherit;
    transition: background var(--ca-transition), border-color var(--ca-transition), color var(--ca-transition);
  }
  .rotation-quick-btn:hover {
    background: color-mix(in srgb, var(--ca-action) 12%, transparent);
    border-color: color-mix(in srgb, var(--ca-action) 35%, transparent);
    color: var(--ca-action);
  }
  .rotation-quick-btn.rotation-quick-reset {
    color: var(--ca-secondary-text);
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.6px;
  }
  /* House SVG: ensure the house group has a proper drag affordance */
  #compass-house { transition: filter var(--ca-transition); cursor: grab; touch-action: none; }
  #compass-house:hover rect { stroke-width: 2; }
  /* Save action bar below all config cards */
  .settings-save-bar {
    display: flex;
    justify-content: flex-end;
  }
  /* Backup button row */
  .settings-backup-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  /* Inline checkbox label (icon + text on one row) */
  .checkbox-row {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  /* Position bar */
  .pos-bar {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 90px;
  }
  .pos-bar-track {
    width: 60px;
    height: 6px;
    background: rgba(255,255,255,0.06);
    border-radius: 3px;
    overflow: hidden;
    flex-shrink: 0;
    outline: 1px solid rgba(255,255,255,0.15);
    position: relative;
  }
  .pos-bar-fill {
    display: block;
    height: 100%;
    border-radius: 3px;
    background: #5bb8f5;
    transition: width 0.3s ease;
  }
  .pos-bar-label {
    font-size: 12px;
    min-width: 32px;
  }
  .pos-bar.pos-bar-diverges {
    min-width: 110px;
  }
  .pos-bar.pos-bar-diverges .pos-bar-track {
    width: 70px;
  }
  .pos-bar-range {
    position: absolute;
    top: 0;
    bottom: 0;
    background: repeating-linear-gradient(
      135deg,
      var(--ca-primary) 0,
      var(--ca-primary) 3px,
      transparent 3px,
      transparent 6px
    );
    opacity: 0.7;
    pointer-events: none;
    transition: left var(--ca-transition), width var(--ca-transition);
  }
  .pos-bar-diverges .pos-bar-label {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 11px;
    min-width: 0;
  }
  .pos-bar-diverges .pos-bar-current-val {
    color: var(--primary-text-color);
    font-weight: 500;
  }
  .pos-bar-diverges .pos-bar-arrow,
  .pos-bar-diverges .pos-bar-target-val {
    color: var(--ca-primary);
    font-weight: 600;
  }
  .data-table .pos-cell {
    white-space: nowrap;
  }
  .pos-bar.pos-bar-compact {
    min-width: 0;
    gap: 6px;
    vertical-align: middle;
  }
  .pos-bar.pos-bar-compact .pos-bar-track {
    width: 44px;
    height: 4px;
  }
  .pos-bar.pos-bar-compact .pos-bar-label {
    font-size: 11px;
    min-width: 0;
    color: var(--ca-secondary-text);
  }
  .rule-meta .rule-target {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .resume-x {
    display: inline;
    font-size: 13px;
    padding: 2px 4px;
    margin-left: 2px;
    vertical-align: middle;
    color: var(--ca-secondary-text);
    background: none;
    border: none;
    cursor: pointer;
    line-height: 1;
  }
  .resume-x:hover {
    color: #e65100;
  }

  /* Inline live-update elements in covers table */
  .pause-remaining {
    font-size: 11px;
    color: var(--ca-secondary-text);
    margin-left: 4px;
  }
  .hysteresis-badge {
    font-size: 11px;
    margin-left: 4px;
    vertical-align: middle;
  }
  .live-icon {
    font-size: 12px;
    margin-left: 2px;
  }
  .live-icon-sun {
    font-size: 14px;
    margin-left: 4px;
    color: var(--ca-sun);
  }

  /* Toggle switch */
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
  }
  .toggle-row span { font-size: 14px; }
  .toggle {
    position: relative;
    width: 44px;
    height: 24px;
    flex-shrink: 0;
  }
  .toggle input {
    opacity: 0;
    width: 0;
    height: 0;
    position: absolute;
  }
  .toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background: var(--ca-border);
    border-radius: 12px;
    transition: background var(--ca-transition);
  }
  .toggle-slider::before {
    content: '';
    position: absolute;
    width: 18px;
    height: 18px;
    left: 3px;
    bottom: 3px;
    background: #fff;
    border-radius: 50%;
    transition: transform var(--ca-transition);
  }
  .toggle input:checked + .toggle-slider {
    background: var(--ca-primary);
  }
  .toggle input:checked + .toggle-slider::before {
    transform: translateX(20px);
  }

  /* Master switch in header */
  .master-switch {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: default;
  }
  .master-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--ca-secondary-text);
    user-select: none;
  }
  .master-toggle {
    position: relative;
    width: 44px;
    height: 24px;
    flex-shrink: 0;
    cursor: pointer;
  }
  .master-toggle input {
    opacity: 0;
    width: 0;
    height: 0;
    position: absolute;
  }
  .master-toggle .toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background: var(--ca-border);
    border-radius: 12px;
    transition: background var(--ca-transition);
  }
  .master-toggle .toggle-slider::before {
    content: '';
    position: absolute;
    width: 18px;
    height: 18px;
    left: 3px;
    bottom: 3px;
    background: #fff;
    border-radius: 50%;
    transition: transform var(--ca-transition);
  }
  .master-toggle input:checked + .toggle-slider {
    background: var(--ca-primary);
  }
  .master-toggle input:checked + .toggle-slider::before {
    transform: translateX(20px);
  }

  /* Section */
  .section {
    margin-bottom: 8px;
    border-top: 1px solid var(--ca-sep);
  }
  .section:first-child {
    border-top: none;
  }
  .section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 0 10px;
    cursor: pointer;
    user-select: none;
    font-size: 14px;
    font-weight: 600;
    color: var(--primary-text-color);
    letter-spacing: 0.2px;
  }
  .section-header:hover {
    color: var(--ca-primary);
  }
  .section-header .section-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--ca-primary) 12%, transparent);
    color: var(--ca-primary);
    flex-shrink: 0;
  }
  .section-header .section-title {
    flex: 1;
    min-width: 0;
  }
  .section-header .section-summary {
    display: block;
    margin-top: 2px;
    font-size: 12px;
    font-weight: normal;
    letter-spacing: normal;
    color: var(--ca-secondary-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .section-header .arrow {
    font-size: 10px;
    color: var(--ca-secondary-text);
    transition: transform var(--ca-transition);
    display: inline-block;
  }
  .section-header .arrow.expanded { transform: rotate(90deg); }
  .section-body {
    overflow: hidden;
    max-height: 0;
    transition: max-height 0.35s ease;
  }
  .section-body.expanded { max-height: 6000px; padding-bottom: 8px; }
  /* Cover sheet: the slide background is the page grey, so framed boxes
     take the card colour and a stronger border to stand out */
  .slide-body .opt-box:not(.opt-box-flat) {
    background: var(--ca-card-bg);
    border-color: color-mix(in srgb, var(--primary-text-color, #212121) 35%, transparent);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  }
  .slide-body .opt-box .opt-box:not(.opt-box-flat) { box-shadow: none; }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--ca-transition);
    font-family: inherit;
  }
  .btn-primary {
    background: var(--ca-primary);
    color: #fff;
  }
  .btn-primary:hover { filter: brightness(1.1); }
  .btn-secondary {
    background: transparent;
    color: var(--ca-primary);
    border: 1px solid var(--ca-primary);
  }
  .btn-secondary:hover { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.08); }
  .btn-danger {
    background: transparent;
    color: var(--ca-error);
    border: 1px solid var(--ca-error);
  }
  .btn-danger:hover { background: rgba(219, 68, 55, 0.08); }
  .btn-icon {
    background: none;
    border: none;
    padding: 6px;
    cursor: pointer;
    color: var(--ca-secondary-text);
    font-size: 18px;
    border-radius: 50%;
    transition: all var(--ca-transition);
    line-height: 1;
    font-family: inherit;
  }
  .btn-icon:hover {
    background: rgba(0,0,0,0.06);
    color: var(--primary-text-color);
  }
  .btn-sm { padding: 4px 10px; font-size: 12px; }
  .btn-sm.active { background: var(--ca-primary); color: #fff; }

  /* Chips */
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.1);
    color: var(--ca-primary);
    font-weight: 500;
  }
  .chip-group { display: flex; flex-wrap: wrap; gap: 6px; }

  /* Drag & drop */
  .drag-handle {
    cursor: grab;
    color: var(--ca-secondary-text);
    font-size: 16px;
    padding: 4px;
    user-select: none;
    line-height: 1;
  }
  .drag-handle:active { cursor: grabbing; }
  .rule-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border: 1px solid var(--ca-border);
    border-left: 3px solid transparent;
    border-radius: var(--ca-radius);
    margin-bottom: 8px;
    background: var(--ca-card-bg);
    transition: all var(--ca-transition);
  }
  .rule-row.rule-active {
    border-left-color: var(--ca-active);
    background: color-mix(in srgb, var(--ca-active) 6%, var(--ca-card-bg));
  }
  .rule-row:hover { box-shadow: var(--ca-shadow); }
  /* Pulsing highlight when a rule is opened from the cover table */
  .rule-row.rule-highlight {
    animation: ca-rule-pulse 1.6s ease-out;
  }
  @keyframes ca-rule-pulse {
    0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ca-action) 60%, transparent); }
    40%  { box-shadow: 0 0 0 6px color-mix(in srgb, var(--ca-action) 30%, transparent); }
    100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ca-action) 0%, transparent); }
  }
  .rule-row.drag-over {
    border-color: var(--ca-primary);
    box-shadow: 0 0 0 2px rgba(var(--rgb-primary-color, 3, 169, 244), 0.3);
  }
  .rule-row.dragging { opacity: 0.4; }
  .rule-info { flex: 1; min-width: 0; }
  .rule-name { font-weight: 500; font-size: 15px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .rule-scen { font-size: 11px; font-weight: 400; padding: 1px 7px; border-radius: 999px; color: var(--ca-secondary-text);
    border: 1px solid var(--ca-border); white-space: nowrap; }
  .rule-scen-off { text-decoration: line-through; opacity: 0.7; }
  .rule-scen-none { color: var(--ca-warning); border-color: currentColor; }
  .rule-active-dot {
    width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
    background: var(--ca-divider, #e0e0e0);
    transition: background 0.2s, box-shadow 0.2s;
  }
  .rule-active-dot.active { background: var(--ca-active); box-shadow: 0 0 6px color-mix(in srgb, var(--ca-active) 50%, transparent); }
  .rule-meta {
    font-size: 12px;
    color: var(--ca-secondary-text);
    margin-top: 2px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
  .rule-safety-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 1px 7px 1px 5px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.2px;
    color: var(--ca-danger);
    background: color-mix(in srgb, var(--ca-danger) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--ca-danger) 30%, transparent);
    white-space: nowrap;
  }
  .rule-safety-badge svg { flex-shrink: 0; }
  .rule-safety-icon { display: inline-flex; vertical-align: middle; margin-left: 5px; color: var(--ca-danger); }
  .rule-top-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; margin-bottom: 22px; }
  .rule-top-row > .rule-inline-label { margin-right: -6px; }
  .form-group.rule-top-row > .rule-name-input { flex: 1 1 220px; min-width: 0; width: auto; }
  .rule-top-field { display: flex; align-items: center; gap: 8px; }
  .rule-top-field[hidden] { display: none; }
  .form-group.rule-top-row .rule-top-field input { width: 90px; }
  .rule-top-label { font-size: 13px; font-weight: 500; color: var(--ca-secondary-text); display: inline-flex;
    align-items: center; white-space: nowrap; }
  .rule-top-row > .hint-panel { flex: 0 0 100%; margin: 0; }
  .rule-inline-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-bottom: 12px; }
  .rule-inline-label { flex: 0 0 110px; font-size: 13px; font-weight: 500; color: var(--ca-secondary-text);
    display: inline-flex; align-items: center; }
  .rule-inline-row > .multi-select { flex: 1 1 280px; margin-top: 0; }
  .rule-inline-label-auto { flex-basis: auto; }
  .rule-inline-select { flex: 0 1 280px; min-width: 180px; }
  .rule-inline-select select { width: 100%; padding: 8px 12px; border: 1px solid var(--ca-border); border-radius: 8px;
    background: var(--primary-background-color, #fafafa); color: var(--primary-text-color); font-size: 14px;
    font-family: inherit; outline: none; }
  .rule-inline-select select:focus { border-color: var(--ca-primary); }
  .cond-group-add-row { gap: 4px; margin-top: 8px; }
  .cond-group-add-row .cond-group-add { margin: 0; }
  .rule-safety-inline { display: flex; align-items: center; gap: 8px; margin-left: auto; font-size: 13px; }
  .rule-safety-inline > span { display: inline-flex; align-items: center; }
  .rule-inline-row > .hint-panel { flex: 0 0 100%; margin: 0; }
  .hint-btn { background: none; border: none; padding: 2px 4px; margin-left: 2px; border-radius: 6px; cursor: pointer;
    color: var(--ca-secondary-text); display: inline-flex; vertical-align: middle; }
  .hint-btn:hover, .hint-btn.open { color: var(--ca-primary); }
  .hint-panel { padding: 8px 10px; background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
    border-left: 2px solid color-mix(in srgb, var(--ca-primary) 50%, transparent); border-radius: 4px;
    font-size: 12px; color: var(--ca-secondary-text); line-height: 1.5; }
  .hint-panel[hidden] { display: none; }
  @media (max-width: 700px) {
    .form-group.rule-top-row > .rule-name-input { flex-basis: 100%; }
    .rule-top-field { flex: 1 1 40%; flex-direction: column; align-items: stretch; gap: 4px; }
    .form-group.rule-top-row .rule-top-field input { width: 100%; }
    .rule-inline-label { flex-basis: 100%; }
    .rule-safety-inline { margin-left: 0; }
  }
  .priority-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 28px;
    padding: 2px 6px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12);
    color: var(--ca-primary);
  }

  /* Inline editor for rules */
  .rule-editor {
    overflow: hidden;
    max-height: 0;
    transition: max-height 0.4s ease, padding 0.3s ease;
    padding: 0 16px;
  }
  .rule-editor.expanded {
    /* No height cap: a long rule must never clip its save button. */
    max-height: none;
    overflow: visible;
    padding: 16px;
    border-top: 1px solid var(--ca-border);
  }

  /* Condition card */
  .condition-card {
    background: var(--primary-background-color, #fafafa);
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    position: relative;
  }
  .condition-card .cond-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .condition-card .cond-type {
    font-weight: 500;
    font-size: 13px;
    color: var(--ca-primary);
  }
  .condition-card .cond-params {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .condition-card .cond-params .form-group { margin-bottom: 0; }
  .cond-head-left { display: flex; align-items: center; gap: 8px; min-width: 0; flex-wrap: wrap; }
  .cond-preview {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 12px; color: var(--ca-secondary-text); white-space: nowrap;
  }
  .cond-preview-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--ca-border); flex-shrink: 0;
  }
  .cond-preview-on { color: var(--ca-text); }
  .cond-preview-on .cond-preview-dot { background: var(--ca-active, var(--ca-success-strong)); }
  .cond-preview-context { font-style: italic; opacity: 0.65; }
  .day-select { display: flex; gap: 4px; flex-wrap: wrap; }
  /* Native Home Assistant condition card */
  .ha-seg { display: inline-flex; border: 1px solid var(--ca-border); border-radius: 8px; overflow: hidden; margin: 8px 0 4px; }
  .ha-seg button { border: 0; background: var(--ca-card-bg); color: var(--ca-secondary-text); padding: 6px 14px; font: inherit; font-size: 13px; cursor: pointer; }
  .ha-seg button + button { border-left: 1px solid var(--ca-border); }
  .ha-seg button.on { background: var(--ca-primary); color: #fff; }
  .condition-card .cond-params.ha-params { grid-template-columns: 1fr; }
  .ha-params .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  textarea.ha-yaml { width: 100%; box-sizing: border-box; font: 13px/1.5 ui-monospace, Menlo, Consolas, monospace; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--ca-border); background: var(--code-editor-background-color, #1e1e1e); color: var(--code-editor-color, #d4d4d4); resize: vertical; tab-size: 2; }
  .btn-link { background: none; border: 0; padding: 0 0 0 6px; color: var(--ca-primary); font: inherit; cursor: pointer; text-decoration: underline; }
  .ha-help { font-size: 12px; color: var(--ca-secondary-text); margin-top: 4px; }
  .ha-current { font-size: 12px; color: var(--ca-secondary-text); margin-top: 4px; }
  .ha-add-state { display: flex; gap: 8px; margin-top: 8px; max-width: 420px; }
  .ha-add-state input { flex: 1; }
  .ha-status { display: grid; gap: 6px; margin-top: 10px; }
  .ha-status:empty { display: none; }
  .ha-msg { font-size: 13px; padding: 6px 10px; border-radius: 6px; overflow-wrap: anywhere; }
  .ha-msg-ok { color: var(--ca-success); background: color-mix(in srgb, var(--ca-success) 12%, transparent); }
  .ha-msg-err { color: var(--ca-error); background: color-mix(in srgb, var(--ca-error) 12%, transparent); }
  .ha-msg-warn { color: var(--ca-warning); background: color-mix(in srgb, var(--ca-warning) 12%, transparent); }
  .ha-msg-info { color: var(--ca-secondary-text); background: color-mix(in srgb, var(--ca-secondary-text) 10%, transparent); }
  .ha-convert { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 8px 0 10px; }
  .chip.chip-error { color: var(--ca-error); background: color-mix(in srgb, var(--ca-error) 12%, transparent); }
  @media (max-width: 600px) { .ha-params .form-row { grid-template-columns: 1fr; } }
  .day-btn {
    padding: 4px 8px; border: 1px solid var(--ca-border); border-radius: 4px;
    background: var(--ca-card-bg); color: var(--ca-text); cursor: pointer;
    font-size: 13px; min-width: 36px; text-align: center;
    transition: background 0.15s, border-color 0.15s;
  }
  .day-btn:hover { border-color: var(--ca-primary); }
  .day-btn.selected { background: var(--ca-primary); color: #fff; border-color: var(--ca-primary); }

  /* Scenario card */
  .scenario-card {
    background: var(--ca-card-bg);
    border: 2px solid var(--ca-border);
    border-radius: var(--ca-radius);
    padding: 20px;
    transition: all var(--ca-transition);
  }
  .scenario-card.active-scenario {
    border-color: var(--ca-active);
    background: color-mix(in srgb, var(--ca-active) 6%, var(--ca-card-bg));
    box-shadow:
      0 0 0 2px color-mix(in srgb, var(--ca-active) 35%, transparent),
      0 4px 16px color-mix(in srgb, var(--ca-active) 18%, transparent);
  }
  .scenario-card.active-scenario .sc-name {
    color: var(--ca-active);
  }
  .scenario-card .sc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .scenario-card .sc-name {
    font-weight: 500;
    font-size: 18px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .scenario-card .sc-rules { margin-top: 12px; }
  .scenario-card .sc-rule-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid var(--ca-border);
    font-size: 14px;
  }
  .scenario-card .sc-rule-row:last-child { border-bottom: none; }
  .scenario-card .sc-rule-label { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
  .scenario-card .sc-rule-off .sc-rule-label > span:not(.sc-rule-off-badge),
  .scenario-card .sc-rule-off .priority-badge { opacity: 0.45; }
  .scenario-card .sc-rule-off .toggle { opacity: 0.55; }
  .sc-rule-off-badge { font-size: 11px; padding: 1px 8px; border-radius: 10px; color: var(--ca-secondary-text); border: 1px dashed var(--ca-border); white-space: nowrap; }

  /* Toast */
  .toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: var(--ca-success);
    color: #fff;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    z-index: 200;
    opacity: 0;
    transition: all 0.3s ease;
    pointer-events: none;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    overflow: hidden;
  }
  .toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
  .toast-progress {
    position: absolute;
    left: 0;
    bottom: 0;
    height: 3px;
    width: 100%;
    background: rgba(255,255,255,0.55);
    transform: scaleX(0);
    transform-origin: left;
  }
  /* duration must match the timeout in _showToast() */
  .toast.show .toast-progress {
    animation: ca-toast-countdown 2s linear forwards;
  }
  .toast.toast-error {
    background: var(--error-color, #db4437);
  }
  .toast.toast-error.show .toast-progress {
    animation-duration: 5s;
  }
  @keyframes ca-toast-countdown {
    from { transform: scaleX(1); }
    to { transform: scaleX(0); }
  }

  /* Loading / Error */
  .state-msg {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 20px;
    text-align: center;
    color: var(--ca-secondary-text);
  }
  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid var(--ca-border);
    border-top-color: var(--ca-primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 16px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Add card */
  .add-card {
    border: 2px dashed var(--ca-border);
    border-radius: var(--ca-radius);
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 120px;
    cursor: pointer;
    transition: all var(--ca-transition);
    color: var(--ca-secondary-text);
    font-size: 15px;
    font-weight: 500;
    gap: 8px;
    background: transparent;
    width: 100%;
    font-family: inherit;
  }
  .add-card:hover {
    border-color: var(--ca-primary);
    color: var(--ca-primary);
    background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.04);
  }

  /* Inline form */
  .inline-form {
    background: var(--ca-card-bg);
    border: 2px solid var(--ca-primary);
    border-radius: var(--ca-radius);
    padding: 20px;
  }
  .inline-form .form-actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;
    justify-content: flex-end;
  }

  /* Confirm dialog */
  .confirm-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.6);
    z-index: 300;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .confirm-dialog {
    background: var(--primary-background-color, #1c1c1c);
    border-radius: var(--ca-radius);
    padding: 24px;
    min-width: 300px;
    max-width: 90vw;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }
  .confirm-dialog p {
    margin: 0 0 20px;
    font-size: 16px;
  }
  .confirm-dialog .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  /* Multi-select */
  .multi-select {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
  }
  .multi-select .ms-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    border: 1px solid var(--ca-border);
    border-radius: 16px;
    font-size: 13px;
    cursor: pointer;
    transition: all var(--ca-transition);
    background: transparent;
    color: var(--primary-text-color);
    font-family: inherit;
  }
  .multi-select .ms-item.selected {
    background: var(--ca-primary);
    color: #fff;
    border-color: var(--ca-primary);
  }
  .multi-select .ms-item:hover { border-color: var(--ca-primary); }

  /* Empty state */
  .empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--ca-secondary-text);
    font-size: 14px;
  }

  /* Utilities */
  .nowrap { white-space: nowrap; }
  .mt-6 { margin-top: 6px; }
  .mt-8 { margin-top: 8px; }
  .mt-16 { margin-top: 16px; }
  .mb-12 { margin-bottom: 12px; }
  .mb-16 { margin-bottom: 16px; }

  /* State/error message icon */
  .state-msg-icon {
    font-size: 32px;
    margin-bottom: 12px;
  }

  /* Add-cover form */
  .add-cover-select {
    width: 100%;
    min-height: 80px;
    padding: 8px;
    border: 1px solid var(--divider-color);
    border-radius: 6px;
    background: var(--ha-card-background, var(--card-background-color));
    color: var(--primary-text-color);
  }

  /* Slide-out delete block */
  .slide-delete-wrap {
    padding: 16px 0;
    border-top: 1px solid var(--ca-border);
    margin-top: 16px;
  }

  /* Facade card */
  .facade-dir-label {
    font-size: 12px;
    color: var(--ca-secondary-text);
  }
  .facade-meta-row {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
    font-size: 13px;
    color: var(--ca-secondary-text);
  }
  .facade-covers-intro {
    font-size: 13px;
    color: var(--ca-secondary-text);
    margin-bottom: 8px;
  }
  .facade-covers-list-wrap {
    margin-bottom: 12px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 8px;
  }
  .facade-covers-label {
    font-size: 12px;
    color: var(--ca-secondary-text);
  }
  .facade-covers-list-wrap > .chip-group { margin: 0; }
  .facade-sun-time { color: var(--primary-text-color); }
  .facade-no-sun { font-style: italic; }
  .facade-no-covers {
    font-size: 12px;
    color: var(--ca-secondary-text);
  }
  .facade-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  /* Rules */
  .rule-reorder-hint {
    margin-bottom: 12px;
    font-size: 12px;
    color: var(--ca-secondary-text);
  }
  .slide-out input:disabled, .form-group input:disabled { opacity: .5; cursor: not-allowed; }
  .cond-group { border: 1px solid var(--ca-border); border-left: 3px solid var(--ca-primary, #03a9f4); border-radius: 8px; padding: 10px 10px 2px; margin-bottom: 4px; }
  .cond-group-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
  .cond-group-title { font-weight: 600; font-size: 13px; }
  .cond-group-op { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ca-secondary-text); }
  .cond-group-op select { width: auto; padding: 4px 8px; font-size: 12px; }
  .cond-group-head > .btn-icon { margin-left: auto; }
  .cond-group-head > .move-btns { margin-left: auto; }
  .cond-group-head > .move-btns + .btn-icon { margin-left: 0; }
  .move-btns { display: inline-flex; align-items: center; flex: none; }
  .move-btns.move-btns-v { flex-direction: column; gap: 2px; margin: -4px 0; }
  .move-btns.move-btns-v .btn-move { padding: 3px 6px; }
  /* Touch screens cannot drag rows: the arrows replace the handle */
  @media (max-width: 600px) {
    .rule-row > .drag-handle { display: none; }
    .rule-row { gap: 8px; padding-left: 8px; }
  }
  .btn-icon.btn-move { font-size: 11px; padding: 5px 6px; border-radius: 6px; }
  .btn-icon.btn-move:disabled { opacity: .3; cursor: default; background: none; color: var(--ca-secondary-text); }
  .cond-group-sep { text-align: center; font-weight: 700; font-size: 12px; letter-spacing: .05em; color: var(--ca-primary, #03a9f4); margin: 6px 0; }
  .cond-group-add { margin: 6px 0 4px; }
  .cond-head-right { display: inline-flex; align-items: center; gap: 6px; }
  .cond-chevron { border: none; background: transparent; color: var(--ca-secondary-text); cursor: pointer; font-size: 12px; padding: 0 6px 0 0; transition: transform .15s; }
  .condition-card.collapsed .cond-chevron { transform: rotate(-90deg); }
  .condition-card .cond-type[data-action] { cursor: pointer; }
  .condition-card.collapsed > :not(.cond-header) { display: none; }
  .condition-card.collapsed .cond-header { margin-bottom: 0; }
  .cond-summary { display: none; font-size: 12px; color: var(--primary-text-color); margin-left: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 45ch; }
  .condition-card.collapsed .cond-summary:not(:empty) { display: inline; }
  .rule-conditions-label { display: flex; align-items: center; justify-content: space-between; }
  .cond-collapse-all { border: none; background: transparent; color: var(--ca-primary); cursor: pointer; font-size: 12px; text-transform: none; font-weight: 500; letter-spacing: normal; padding: 0; }
  .cond-group-move { width: auto; padding: 2px 6px; font-size: 12px; }
  .cond-not { border: 1px solid var(--ca-border); background: transparent; color: var(--ca-secondary-text); border-radius: 10px; padding: 1px 8px; font-size: 11px; font-weight: 600; cursor: pointer; margin-right: 6px; }
  .cond-not.active { background: var(--error-color, #db4437); border-color: var(--error-color, #db4437); color: #fff; }
  .condition-card.negated { border-left: 3px solid var(--error-color, #db4437); }
  .chip-block { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 4px; padding: 2px 6px; border: 1px dashed var(--ca-border); border-radius: 12px; }
  .chip-op { font-size: 11px; color: var(--ca-secondary-text); }
  .chip-op-between { font-weight: 700; color: var(--ca-primary, #03a9f4); margin: 0 4px; }
  .chip-not { color: var(--error-color, #db4437); font-size: 11px; }
  .rule-conditions-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--ca-secondary-text);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 16px 0 8px;
  }
  .rule-no-conditions {
    font-size: 13px;
    color: var(--ca-secondary-text);
    margin-bottom: 8px;
  }
  .rule-condition-add {
    margin-top: 8px;
  }
  .rule-condition-type-select {
    padding: 8px;
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color);
    font-size: 13px;
    font-family: inherit;
  }
  .rule-editor-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
    /* Stays in view while scrolling a long rule */
    position: sticky;
    bottom: 0;
    z-index: 2;
    padding: 10px 0;
    background: var(--ca-card-bg);
    border-top: 1px solid var(--ca-border);
  }

  /* Scenario card extras */
  .scenario-card-icon {
    --mdc-icon-size: 20px;
    margin-right: 6px;
  }
  .sc-actions {
    display: flex;
    gap: 6px;
  }
  .scenario-no-rules {
    font-size: 13px;
    color: var(--ca-secondary-text);
  }
  .sc-rule-disabled {
    text-decoration: line-through;
    opacity: 0.5;
  }

  /* Scenario icon picker */
  .icon-picker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(44px, 1fr));
    gap: 6px;
    padding: 8px;
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    background: var(--primary-background-color, #fafafa);
    max-height: 220px;
    overflow-y: auto;
  }
  .icon-picker-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    aspect-ratio: 1 / 1;
    padding: 0;
    border: 1px solid transparent;
    border-radius: 6px;
    background: transparent;
    color: var(--primary-text-color);
    cursor: pointer;
    transition: background 0.12s ease, border-color 0.12s ease;
    --mdc-icon-size: 22px;
  }
  .icon-picker-btn:hover {
    background: color-mix(in srgb, var(--ca-primary) 10%, transparent);
    border-color: color-mix(in srgb, var(--ca-primary) 30%, transparent);
  }
  .icon-picker-btn.selected {
    background: color-mix(in srgb, var(--ca-primary) 18%, transparent);
    border-color: var(--ca-primary);
    color: var(--ca-primary);
  }
  .icon-picker-custom {
    margin-top: 8px;
  }
  .icon-picker-custom > summary {
    cursor: pointer;
    font-size: 12px;
    color: var(--ca-secondary-text);
    padding: 4px 0;
    list-style: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .icon-picker-custom > summary::-webkit-details-marker { display: none; }
  .icon-picker-custom[open] > summary { color: var(--ca-primary); }
  .icon-picker-custom-body {
    margin-top: 6px;
  }
  .icon-picker-custom-body input {
    width: 100%;
    padding: 8px;
    border: 1px solid var(--ca-border);
    border-radius: 6px;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color);
    font-size: 13px;
    font-family: inherit;
  }
  .icon-picker-custom-hint {
    font-size: 11px;
    color: var(--ca-secondary-text);
    margin-top: 4px;
    line-height: 1.4;
  }

  /* Log filter bar */
  .log-filter-bar {
    margin-bottom: 12px;
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .log-cover-filter {
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .log-cover-filter label { font-size: 13px; color: var(--ca-secondary-text); }
  .log-cover-filter select {
    min-width: 220px; max-width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color);
    font-size: 14px;
    font-family: inherit;
  }
  .rule-filter-bar select { min-width: 150px; flex: 1 1 150px; max-width: 260px; }
  .rule-filter-count { font-size: 13px; color: var(--ca-secondary-text); white-space: nowrap; }
  .drag-handle.drag-handle-off { opacity: 0.25; cursor: default; }
  .log-cover-filter select:focus { border-color: var(--ca-primary); outline: none; }
  .log-cover-note { font-size: 12px; color: var(--ca-secondary-text); }
  .slide-log-link { margin: 16px 0 4px; }

  /* Compass */
  .compass-svg-root {
    display: block;
  }

  /* Temperature cell -- mode color is still inline because it's dynamic, but weight is consistent */
  .data-table td.temp-mode {
    font-weight: 600;
  }
  .temp-icon { display: inline-flex; vertical-align: -2px; margin-right: 3px; }

  /* Responsive */
  @media (max-width: 768px) {
    .panel-container { padding: 8px; }
    .card-grid { grid-template-columns: 1fr; }
    .slide-panel { width: 100vw; }
    /* Full-screen sheet on phones: room for the status bar / notch, big
       close targets on both sides and a close button at the bottom */
    .slide-header {
      padding-top: calc(12px + env(safe-area-inset-top, 0px));
      gap: 8px;
    }
    .slide-header .slide-back { display: inline-flex; }
    .slide-header .btn-icon { min-width: 44px; min-height: 44px; font-size: 22px; align-items: center; justify-content: center; }
    .slide-body { padding-bottom: calc(20px + env(safe-area-inset-bottom, 0px)); }
    .slide-close-bottom { display: flex; justify-content: center; margin: 16px 0 8px; }
    .slide-close-bottom .btn { min-width: 160px; justify-content: center; }
    .form-row { grid-template-columns: 1fr; }
    .tab-bar button { padding: 10px 14px; font-size: 13px; }
    .data-table th, .data-table td { padding: 10px 12px; font-size: 13px; }
    .data-table td.row-chevron { display: none; }
    .data-table th.row-chevron-head { display: none; }
    /* Settings: sidebar collapses to horizontal scrollable pill strip */
    .settings-shell {
      flex-direction: column;
      align-items: stretch;
      gap: 12px;
    }
    .settings-nav {
      flex: 0 0 auto;
      flex-direction: row;
      position: static;
      padding: 6px;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      gap: 4px;
      /* Edge fade so users see there is more content to the side */
      -webkit-mask-image: linear-gradient(
        to right,
        transparent 0,
        black 18px,
        black calc(100% - 28px),
        transparent 100%
      );
      mask-image: linear-gradient(
        to right,
        transparent 0,
        black 18px,
        black calc(100% - 28px),
        transparent 100%
      );
      scrollbar-width: none;
      scroll-snap-type: x proximity;
    }
    .settings-nav::-webkit-scrollbar { display: none; }
    .settings-stack { gap: 16px; }
    .settings-stack .card-header { padding: 14px 16px 12px; }
    .settings-stack .card-body { padding: 16px 16px 20px; }
    .settings-stack .form-group { margin-bottom: 20px; }
    .settings-stack .form-row { grid-template-columns: 1fr; gap: 20px; margin-bottom: 20px; }
    .settings-stack .form-group input[type="number"],
    .settings-stack .form-group select,
    .settings-stack .form-group input[type="text"] { max-width: none; }
    .settings-nav-btn {
      flex: 0 0 auto;
      padding: 8px 12px;
      font-size: 13px;
      scroll-snap-align: start;
    }
    .settings-nav-btn .settings-nav-label {
      overflow: visible;
      text-overflow: unset;
    }
    /* Sticky first column so the cover name stays visible when scrolling horizontally */
    .data-table th:first-child,
    .data-table td:first-child {
      position: sticky;
      left: 0;
      z-index: 1;
      background: var(--ca-card-bg);
      box-shadow: 2px 0 4px rgba(0, 0, 0, 0.15);
    }
    .data-table thead th:first-child {
      z-index: 2;
    }
    .data-table tbody tr:hover td:first-child,
    .data-table tbody tr.selected td:first-child {
      background: color-mix(in srgb, var(--ca-primary) 12%, var(--ca-card-bg));
    }
    .condition-card .cond-params { grid-template-columns: 1fr; }
    .panel-header {
      flex-direction: column;
      align-items: stretch;
      gap: 6px;
      padding: 12px 0 6px;
    }
    .header-left {
      justify-content: flex-start;
    }
    .header-right {
      justify-content: space-between;
      row-gap: 8px;
      padding-top: 6px;
      border-top: 1px solid var(--ca-border);
    }
    .info-bar {
      flex-basis: 100%;
      order: -1;
      font-size: 11px;
    }
  }
`;

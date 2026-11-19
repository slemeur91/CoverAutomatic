"""Panel smoke tests: every tab renders, main edits send the right WebSocket messages."""
from __future__ import annotations

import pytest

TABS = ["covers", "facades", "rules", "scenarios", "settings", "log"]
SETTINGS_SECTIONS = ["house", "sensors", "comfort", "wind", "automation", "backup"]
SALON = "cover.volet_du_salon_nodeid_32_position"


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_tab_renders(mount, lang) -> None:
    m = mount(lang)
    for tab in TABS:
        m.tab(tab)
        active = m.js("window.__el.shadowRoot.querySelector('[data-tab].active').dataset.tab")
        assert active == tab
        text = m.js("window.__el.shadowRoot.querySelector('.panel-container').innerText")
        assert len(text) > 50, tab
    assert m.errors() == []


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_settings_section_renders(mount, lang) -> None:
    m = mount(lang)
    m.tab("settings")
    for section in SETTINGS_SECTIONS:
        m.click(f'.settings-nav-btn[data-section="{section}"]')
        active = m.js("window.__el.shadowRoot.querySelector('.settings-nav-btn.active').dataset.section")
        assert active == section
        assert m.js("window.__el.shadowRoot.querySelector('.settings-content').innerText.length") > 20, section
    assert m.errors() == []


def test_rule_name_saved(mount) -> None:
    m = mount()
    m.tab("rules")
    m.click('.rule-info[data-id="fermer_tout"]')
    assert m.root('.rule-editor.expanded').count() == 1
    m.root('.rule-name-input[data-id="fermer_tout"]').fill("Tout fermer")
    m.click('[data-action="rule-save"][data-id="fermer_tout"]')
    m.page.wait_for_timeout(300)
    saved = m.ws("cover_automatic/rule/update")
    assert saved and saved[-1]["rule_id"] == "fermer_tout" and saved[-1]["name"] == "Tout fermer"
    assert m.errors() == []


def test_rule_filter_closes_rule_out_of_filter(mount) -> None:
    m = mount()
    m.tab("rules")
    m.click('.rule-info[data-id="fermer_en_ete_bas"]')  # summer only
    assert m.root('.rule-editor.expanded').count() == 1
    m.root('[data-action="rule-filter"][data-filter-key="scenario"]').select_option("winter")
    m.page.wait_for_timeout(200)
    assert m.root('.rule-editor.expanded').count() == 0
    assert m.root('.rule-row[data-rule-id="fermer_en_ete_bas"]').count() == 0
    assert m.root('.rule-row[data-rule-id="ouvrir_en_hiver_si_soleil"]').count() == 1
    assert m.errors() == []


def test_cover_sheet_profiles_and_autosave(mount) -> None:
    m = mount()
    m.tab("covers")
    m.page.locator("tr", has_text="Volet du Salon").first.click()
    m.page.wait_for_timeout(300)
    assert m.root(".slide-panel.open").count() == 1
    m.click('.slide-panel.open .section-header[data-section="room"]')
    assert m.root(".slide-panel.open .cover-profile").count() == 2
    field = m.root(f'.slide-panel.open [data-action="cover-input"][data-id="{SALON}"][data-field="comfort_temp_min_b"]')
    field.fill("20.5")
    field.dispatch_event("change")
    m.page.wait_for_timeout(1500)
    saved = m.ws("cover_automatic/cover/update")
    assert saved and saved[-1]["entity_id"] == SALON and saved[-1]["comfort_temp_min_b"] == 20.5
    assert m.errors() == []


def test_profile_assignment_saved(mount) -> None:
    m = mount()
    m.tab("settings")
    m.click('.settings-nav-btn[data-section="sensors"]')
    m.click('[data-action="profile-scenario"][data-profile="b"][data-scenario="everyday"]')
    m.click('[data-action="settings-save"]')
    m.page.wait_for_timeout(300)
    saved = m.ws("cover_automatic/settings/update")
    assert saved
    assert "everyday" in saved[-1]["profile_b_scenarios"]
    assert "everyday" not in saved[-1].get("profile_a_scenarios", [])
    assert m.errors() == []


def test_log_filter(mount) -> None:
    m = mount()
    m.tab("log")
    m.page.wait_for_timeout(300)
    total = m.root(".data-table tbody tr").count()
    m.click('[data-action="log-filter"][data-filter="scenario"]')
    m.page.wait_for_timeout(200)
    shown = m.root(".data-table tbody tr").count()
    assert 0 < shown < total
    assert m.errors() == []


def test_facade_sun_times(mount) -> None:
    m = mount()
    m.tab("facades")
    assert m.root(".facade-sun-time").count() > 0
    assert m.errors() == []


XSS = '<img src=x onerror="window.__xss=1">'
XSS_SCRIPT = f"""
window.__patchConfig = (cfg) => {{
  const x = {XSS!r};
  for (const c of Object.values(cfg.covers)) c.name = x + c.name;
  for (const f of Object.values(cfg.facades)) f.name = x + f.name;
  for (const r of Object.values(cfg.rules)) r.name = x + r.name;
  for (const s of Object.values(cfg.scenarios)) s.name = x + s.name;
  return cfg;
}};
"""


def test_names_are_escaped(mount) -> None:
    m = mount(init_script=XSS_SCRIPT)
    for tab in TABS:
        m.tab(tab)
        assert m.js("window.__el.shadowRoot.querySelectorAll('img[src=x]').length") == 0, tab
    m.tab("rules")
    m.click('.rule-info[data-id="fermer_tout"]')
    m.tab("covers")
    m.page.locator("tr", has_text="Volet du Salon").first.click()
    m.page.wait_for_timeout(300)
    assert m.js("window.__el.shadowRoot.querySelectorAll('img[src=x]').length") == 0
    assert m.js("window.__xss") is None
    assert m.errors() == []


def test_cover_commands(mount) -> None:
    """Open / stop / close in the covers table call the cover services only."""
    m = mount()
    m.tab("covers")
    btn = f'[data-action="cover-command"][data-id="{SALON}"]'
    # Living room cover is closed (0 %): open and stop enabled, close disabled
    assert m.root(f'{btn}[data-cmd="open_cover"]').is_enabled()
    assert m.root(f'{btn}[data-cmd="stop_cover"]').is_enabled()
    assert m.root(f'{btn}[data-cmd="close_cover"]').is_disabled()
    m.click(f'{btn}[data-cmd="open_cover"]')
    m.page.wait_for_timeout(200)
    assert m.js("window.__services") == [
        {"domain": "cover", "service": "open_cover", "data": {"entity_id": SALON}}
    ]
    # The click does not open the cover sheet
    assert m.root(".slide-panel.open").count() == 0
    assert m.errors() == []


def test_cover_commands_follow_live_state(mount) -> None:
    m = mount()
    m.tab("covers")
    m.js(f"""(() => {{
      // Home Assistant hands a new hass object on every state change
      const hass = window.__hass;
      const st = hass.states["{SALON}"];
      const states = {{ ...hass.states, "{SALON}": {{ ...st, state: "opening", attributes: {{ ...st.attributes, current_position: 40 }} }} }};
      window.__el.hass = {{ ...hass, states }};
    }})()""")
    m.page.wait_for_timeout(300)
    btn = f'[data-action="cover-command"][data-id="{SALON}"]'
    assert m.root(f'{btn}[data-cmd="open_cover"]').is_disabled()
    assert m.root(f'{btn}[data-cmd="close_cover"]').is_enabled()
    assert m.errors() == []


def test_log_pause_details(mount) -> None:
    """A manual pause shows the expected and read positions and the first report."""
    entry = ("{ data: { key: 'status_change', from: 'auto', to: 'paused', expected: 100, actual: 0, "
             "first_position: 100, first_after: 2.5 } }")
    m = mount("fr")
    assert m.js(f"window.__el._formatLogMessage({entry})") == (
        "Auto → En pause : attendu 100 %, lu 0 % ; première position annoncée 100 % 2,5 s après le dernier ordre"
    )
    m_en = mount("en")
    assert m_en.js(f"window.__el._formatLogMessage({entry})") == (
        "Auto → Paused: expected 100 %, read 0 %; first report 100 % 2.5 s after the last command"
    )
    # Older entries and other status changes are unchanged
    assert m_en.js("window.__el._formatLogMessage({ data: { key: 'status_change', from: 'auto', to: 'paused' } })") == "Auto → Paused"
    assert m.errors() == [] and m_en.errors() == []


def _open_room_field(m):
    m.tab("covers")
    m.page.locator("tr", has_text="Volet du Salon").first.click()
    m.page.wait_for_timeout(300)
    m.click('.slide-panel.open .section-header[data-section="room"]')
    return m.root(f'.slide-panel.open [data-action="cover-input"][data-id="{SALON}"][data-field="comfort_temp_min_b"]')


def _saved(m) -> list:
    return [c["comfort_temp_min_b"] for c in m.ws("cover_automatic/cover/update") if "comfort_temp_min_b" in c]


def test_cover_number_saved_on_commit_only(mount) -> None:
    """Upstream v1.63.9: a pause while typing stores no partial value."""
    m = mount()
    field = _open_room_field(m)
    field.click()
    field.press("Control+a")
    field.press_sequentially("2")
    m.page.wait_for_timeout(900)
    assert _saved(m) == []
    field.press_sequentially("4")
    field.press("Enter")
    m.page.wait_for_timeout(300)
    assert _saved(m) == [24]
    # Focus and value kept after the save
    assert m.js("window.__el.shadowRoot.activeElement?.dataset.field") == "comfort_temp_min_b"
    assert field.input_value() == "24"
    assert m.errors() == []


def test_cover_number_committed_when_sheet_closes(mount) -> None:
    m = mount()
    field = _open_room_field(m)
    field.click()
    field.press("Control+a")
    field.press_sequentially("23")
    m.page.keyboard.press("Escape")
    m.page.wait_for_timeout(300)
    assert m.root(".slide-panel.open").count() == 0
    assert _saved(m) == [23]
    assert m.errors() == []


def test_touch_tap_outside_leaves_field(mount) -> None:
    """Upstream v1.63.10: on touch screens a tap elsewhere ends the entry."""
    m = mount()
    field = _open_room_field(m)
    field.click()
    field.press("Control+a")
    field.press_sequentially("22")
    tap = """(type) => {
      const root = window.__el.shadowRoot;
      const header = root.querySelector('.slide-panel.open .slide-header');
      header.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, composed: true, pointerType: type }));
      return root.activeElement?.dataset.field || null;
    }"""
    # A mouse pointerup does not blur (the click itself moves the focus)
    assert m.js(tap, "mouse") == "comfort_temp_min_b"
    assert m.js(tap, "touch") is None
    m.page.wait_for_timeout(300)
    assert _saved(m) == [22]
    assert m.errors() == []


def test_reload_option_and_log(mount) -> None:
    """Cover option "reload the integration if the cover does not react" and its log entries."""
    m = mount("fr")
    m.tab("covers")
    m.page.locator("tr", has_text="Volet du Salon").first.click()
    m.page.wait_for_timeout(300)
    m.click('.slide-panel.open .section-header[data-section="automation"]')
    toggle = m.root(f'.slide-panel.open [data-action="cover-toggle"][data-id="{SALON}"][data-field="reload_on_no_move"]')
    assert "Recharger l'intégration si le volet ne réagit pas" in m.js(
        "window.__el.shadowRoot.querySelector('.slide-panel.open').textContent")
    assert not toggle.is_checked()
    toggle.dispatch_event("click")
    m.page.wait_for_timeout(900)
    saved = [c for c in m.ws("cover_automatic/cover/update") if "reload_on_no_move" in c]
    assert saved and saved[-1]["entity_id"] == SALON and saved[-1]["reload_on_no_move"] is True
    fmt = "window.__el._formatLogMessage({ data: %s })"
    assert m.js(fmt % "{ key: 'reload_requested', integration: 'Velux' }") == (
        "Aucun mouvement après la commande : rechargement de l'intégration Velux demandé")
    assert m.js(fmt % "{ key: 'reload_done', integration: 'Velux', count: 2, covers: 'Cuisine, Salon' }") == (
        "Intégration Velux rechargée (2 volets : commandes renvoyées) — demandé par Cuisine, Salon")
    assert m.errors() == []


def test_cover_positions_clamped(mount) -> None:
    """Upstream v1.63.12: lock/vent positions outside 0-100 are brought back to the limit."""
    m = mount()
    m.tab("covers")
    m.page.locator("tr", has_text="Volet du Salon").first.click()
    m.page.wait_for_timeout(300)
    # Slat and vent fields only exist for covers with tilt and a tilt sensor
    m.js(f"Object.assign(window.__el._config.covers['{SALON}'], "
         "{ supports_tilt: true, vent_sensor: 'binary_sensor.do_salon' }); window.__el._render()")
    m.click('.slide-panel.open [data-action="sections-toggle-all"]')
    commit = """([field, value]) => {
      const el = window.__el.shadowRoot.querySelector(
        `.slide-panel.open [data-action="cover-input"][data-field="${field}"]`);
      el.value = value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      const marked = el.classList.contains("input-invalid");
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return [marked, el.value, el.classList.contains("input-invalid")];
    }"""
    assert m.js(commit, ["lock_position", "150"]) == [False, "100", False]
    assert m.js(commit, ["vent_tilt_position", "-5"]) == [False, "0", False]
    assert m.js(commit, ["vent_position", "42.6"]) == [False, "43", False]
    assert m.js(commit, ["lock_tilt_position", ""]) == [False, "", False]
    m.page.wait_for_timeout(300)
    saved = {k: v for c in m.ws("cover_automatic/cover/update") for k, v in c.items() if k not in ("entity_id", "type", "id")}
    assert saved == {"lock_position": 100, "vent_tilt_position": 0, "vent_position": 43, "lock_tilt_position": None}
    assert m.errors() == []


def test_settings_positions_clamped(mount) -> None:
    m = mount()
    m.tab("settings")
    m.click('[data-action="settings-section"][data-section="automation"]')
    m.js("""(() => {
      const root = window.__el.shadowRoot;
      const set = (f, v) => { root.querySelector(`[data-settings-field="${f}"]`).value = v; };
      set("lock_position", "150"); set("vent_position", ""); set("lock_tilt_position", "-3"); set("vent_tilt_position", "");
      set("pause_duration", "25");
    })()""")
    m.click('[data-action="settings-save"]')
    m.page.wait_for_timeout(300)
    sent = m.ws("cover_automatic/settings/update")[-1]
    # Whole section saved; empty lock/vent position keeps the stored value
    assert sent["lock_position"] == 100 and sent["lock_tilt_position"] == 0 and sent["pause_duration"] == 25
    assert "vent_position" not in sent
    assert m.errors() == []


def test_rule_do_nothing(mount) -> None:
    """Rule action "do nothing": targets greyed and kept, safety hidden, single summary."""
    m = mount("fr")
    m.tab("rules")
    m.click('.rule-info[data-id="fermer_tout"]')
    sel = lambda f: f'[data-action="rule-field"][data-id="fermer_tout"][data-field="{f}"]'  # noqa: E731
    pos = m.root(sel("target_position"))
    before = pos.input_value()
    assert "Action" in m.js("window.__el.shadowRoot.querySelector('[data-rule-top=\"fermer_tout\"]').textContent")
    m.root(sel("no_action")).check()
    m.page.wait_for_timeout(100)
    assert pos.is_disabled() and pos.input_value() == ""
    assert m.root('[data-rule-safety="fermer_tout"]').is_hidden()
    assert m.root('[data-rule-safety-off="fermer_tout"]').is_visible()
    assert m.root('[data-rule-noaction-help="fermer_tout"]').is_visible()
    # Unchecking puts the previous position back
    m.root(sel("no_action")).uncheck()
    m.page.wait_for_timeout(100)
    assert not pos.is_disabled() and pos.input_value() == before
    m.root(sel("no_action")).check()
    m.click('[data-action="rule-save"][data-id="fermer_tout"]')
    m.page.wait_for_timeout(300)
    saved = m.ws("cover_automatic/rule/update")[-1]
    assert saved["no_action"] is True and saved["safety"] is False
    assert saved["target_position"] == int(before)
    # Collapsed row: one "do nothing" instead of the position bars
    m.js("window.__el._config.rules.fermer_tout.no_action = true; window.__el._expandedRule = null; window.__el._ruleDraft = null; window.__el._render()")
    row = m.root('.rule-row[data-rule-id="fermer_tout"]')
    assert row.locator(".rule-no-action").count() == 1
    assert "Position cible" not in row.inner_text()
    assert m.errors() == []


def test_pending_rule_cell(mount) -> None:
    """Manual cover: rule it would follow in Auto, greyed, pause icon, target on the right."""
    m = mount("fr")
    m.tab("covers")
    m.js(f"""(() => {{
      const el = window.__el;
      el._config.covers['{SALON}'].status = 'manual';
      Object.assign(el._config.live_covers['{SALON}'], {{
        rule_id: null, rule_name: null, target_position: null,
        pending_rule_id: 'fermer_tout', pending_rule_name: 'Fermer tout', pending_target_position: 0 }});
      el._render();
    }})()""")
    cell = m.root(f'[data-live-rule="{SALON}"]')
    pending = cell.locator(".rule-pending")
    assert pending.count() == 1
    assert pending.locator(".rule-pending-icon svg").count() == 1
    assert pending.locator(".rule-pending-pos").inner_text().strip() == "0 %"
    assert cell.locator(".rule-link").count() == 0
    tip = pending.get_attribute("title")
    assert tip == "Ne s'applique pas (statut : Manuel). En Auto : Fermer tout → 0 %"
    # One line: the name is shortened, never wrapped
    assert m.js("getComputedStyle(window.__el.shadowRoot.querySelector('.rule-pending')).whiteSpace") == "nowrap"
    # Live refresh keeps it
    m.js("window.__el._updateLiveCells()")
    assert cell.locator(".rule-pending").count() == 1
    # Global automation off: the cover stays Auto, the tooltip says why
    m.js(f"window.__el._config.covers['{SALON}'].status = 'auto'; window.__el._render()")
    assert m.root(f'[data-live-rule="{SALON}"] .rule-pending').get_attribute("title").startswith(
        "Ne s'applique pas (statut : Automatisation désactivée)")
    assert m.errors() == []


def test_cover_wind_protection_option(mount) -> None:
    m = mount("fr")
    m.tab("covers")
    m.page.locator("tr", has_text="Volet du Salon").first.click()
    m.page.wait_for_timeout(300)
    m.click('.slide-panel.open .section-header[data-section="automation"]')
    toggle = m.root(f'.slide-panel.open [data-action="cover-toggle"][data-id="{SALON}"][data-field="wind_protection"]')
    assert toggle.is_checked()
    toggle.dispatch_event("click")
    m.page.wait_for_timeout(900)
    saved = [c for c in m.ws("cover_automatic/cover/update") if "wind_protection" in c]
    assert saved and saved[-1]["wind_protection"] is False
    m.js(f"window.__el._config.covers['{SALON}'].wind_protection = false")
    assert "Sans protection vent" in m.js(f"window.__el._coverSectionSummaries(window.__el._config.covers['{SALON}']).automation")
    m.page.keyboard.press("Escape")
    m.page.wait_for_timeout(300)
    m.tab("settings")
    m.click('.settings-nav-btn[data-section="wind"]')
    total = m.js("Object.keys(window.__el._config.covers).length")
    assert m.root("[data-wind-covers]").inner_text() == (
        f"Volets protégés du vent : {total - 1} sur {total} (option de la fiche de chaque volet, section Automatisation).")
    assert m.errors() == []

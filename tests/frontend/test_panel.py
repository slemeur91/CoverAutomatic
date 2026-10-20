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

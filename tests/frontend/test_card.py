"""Dashboard card smoke tests."""
from __future__ import annotations

import pytest

SALON = "cover.volet_du_salon_nodeid_32_position"
STATUS = "sensor.volet_du_salon_statut"

WITH_STATUS = f"""
window.__entities = {{ "{STATUS}": {{ entity_id: "{STATUS}", platform: "cover_automatic" }} }};
window.__patchStates = (states) => {{
  states["{STATUS}"] = {{
    entity_id: "{STATUS}", state: "auto",
    attributes: {{ cover_entity_id: "{SALON}", cover_name: "Volet du Salon", auto_enabled: true,
                  rule: "Fermer la Nuit", rule_name: "Fermer la Nuit", target_position: 0, position: 0 }},
  }};
  return states;
}};
"""


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_card_shows_managed_cover(mount, lang) -> None:
    m = mount(lang, mode="card", init_script=WITH_STATUS)
    text = m.js("window.__el.shadowRoot.textContent")
    assert "Fermer la Nuit" in text
    assert m.errors() == []


def test_card_without_covers(mount) -> None:
    m = mount("en", mode="card", init_script="window.__entities = {};")
    assert "No CoverAutomatic cover found" in m.js("window.__el.shadowRoot.textContent")
    assert m.errors() == []


def test_card_commands_call_cover_services(mount) -> None:
    m = mount("fr", mode="card", init_script=WITH_STATUS)
    # Living room cover is closed: close is disabled
    assert m.root('.cmd[data-cmd="close_cover"]').is_disabled()
    m.root('.cmd[data-cmd="open_cover"]').click()
    m.page.wait_for_timeout(100)
    assert m.js("window.__services") == [
        {"domain": "cover", "service": "open_cover", "data": {"entity_id": SALON}}
    ]
    assert m.errors() == []


def test_card_commands_can_be_hidden(mount) -> None:
    m = mount("fr", mode="card", init_script=WITH_STATUS + "window.__cardConfig = { show_commands: false };")
    assert m.root(".cmd").count() == 0
    assert m.errors() == []


PAUSED = WITH_STATUS.replace('state: "auto"', 'state: "paused"').replace(
    "position: 0 }}", "position: 0, pause_until: new Date(Date.now() + 42 * 60000).toISOString() }}"
)


def test_card_resume_next_to_pause_time(mount) -> None:
    m = mount("fr", mode="card", init_script=PAUSED)
    assert m.root(".status .pause .resume").count() == 1
    assert m.root(".controls .resume").count() == 0
    m.js("window.__el.shadowRoot.querySelector('.pause .resume').click()")
    m.page.wait_for_timeout(100)
    assert m.js("window.__services")[-1] == {
        "domain": "cover_automatic", "service": "resume", "data": {"entity_id": SALON}
    }
    assert m.errors() == []


@pytest.mark.parametrize("width", [475, 620])
def test_card_commands_leave_room_for_name_and_rule(mount, width) -> None:
    """With the buttons, a medium card uses two lines: name and rule are not cut."""
    long_rule = WITH_STATUS.replace('rule: "Fermer la Nuit"', 'rule: "Ouvrir en Hiver bas si Présent"')
    m = mount("fr", mode="card", init_script=long_rule)
    m.js(f"window.__el.style.display = 'block'; window.__el.style.width = '{width}px'")
    m.page.wait_for_timeout(200)
    cut = m.js("""(() => {
      const r = window.__el.shadowRoot;
      return [".name", ".rule-text"].filter((css) => { const el = r.querySelector(css); return el.scrollWidth > el.clientWidth; });
    })()""")
    assert cut == []
    assert m.errors() == []

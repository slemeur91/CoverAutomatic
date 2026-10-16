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

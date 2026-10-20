"""Characterization of the panel's event routing (data-action -> behaviour).

Prepares the replacement of the big _handleActionClick / _handleChange
switches by per-module action tables: for every data-action reachable in the
fixture configuration, the methods called by the dispatchers and the panel
properties changed must stay exactly the same (fixtures/action_map.json).

After an intended behaviour change, regenerate the reference with
    UPDATE_ACTION_MAP=1 pytest tests/frontend/test_actions.py --confcutdir=tests/frontend
and review the diff of action_map.json.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

HERE = Path(__file__).parent
PANEL_DIR = HERE.parents[1] / "custom_components" / "cover_automatic" / "panel"
ACTION_MAP = HERE / "fixtures" / "action_map.json"
TRACER = (HERE / "action_tracer.js").read_text(encoding="utf-8")

# Screens of the panel; each starts from a freshly mounted panel.
STATES = {
    "covers": "await tab('covers');",
    "cover-add": "await tab('covers'); await click('[data-action=\"cover-add-start\"]');",
    # Living room cover: occupancy sensor and a measured travel time
    "cover-sheet": (
        "await tab('covers');"
        "await click('[data-action=\"select-cover\"][data-id=\"cover.volet_du_salon_nodeid_32_position\"]');"
        "await click('.slide-panel.open [data-action=\"sections-toggle-all\"]');"
        "R().querySelector('[data-occ-other]').value = 'Absent';"
    ),
    "facades": "await tab('facades');",
    "facade-edit": "await tab('facades'); await click('[data-action=\"facade-edit\"]');",
    "facade-add": "await tab('facades'); await click('[data-action=\"facade-add-start\"]');",
    "rules": "await tab('rules');",
    "rule-editor": "await tab('rules'); await click('.rule-info[data-id=\"ouvrir_le_jour_en_ete\"]');",
    "rule-editor-sun": "await tab('rules'); await click('.rule-info[data-id=\"velux_aeration_ete\"]');",
    # Weather, days, entity state and YAML conditions (test rule of the fixtures)
    "rule-editor-various": "await tab('rules'); await click('.rule-info[data-id=\"test_conditions_diverses\"]');",
    "rules-filtered": (
        "await tab('rules');"
        "const f = R().querySelector('[data-action=\"rule-filter\"][data-filter-key=\"scenario\"]');"
        "f.value = 'winter'; f.dispatchEvent(new Event('change', { bubbles: true })); await wait(60);"
    ),
    "rule-add": "await tab('rules'); await click('[data-action=\"rule-add-start\"]');",
    "rule-confirm": "await tab('rules'); await click('[data-action=\"rule-delete\"]');",
    "scenarios": "await tab('scenarios');",
    "scenario-edit": "await tab('scenarios'); await click('[data-action=\"scenario-edit\"]');",
    "scenario-add": "await tab('scenarios'); await click('[data-action=\"scenario-add-start\"]');",
    **{
        f"settings-{section}": f"await tab('settings'); await click('[data-action=\"settings-section\"][data-section=\"{section}\"]');"
        for section in ("house", "sensors", "comfort", "wind", "automation", "backup")
    },
    "log": "await tab('log'); await wait(200);",
}

# Actions not shown with the fixture configuration (reason given)
UNREACHED = {
    "retry": "only shown when the configuration fails to load",
    "sun-explain-toggle": "case of _handleActionClick that no element renders any more (dead code)",
}

PAGE_HELPERS = """
window.wait = (ms) => new Promise((r) => setTimeout(r, ms));
window.R = () => window.__el.shadowRoot;
window.tab = async (name) => { R().querySelector(`[data-tab="${name}"]`).click(); await wait(60); };
window.click = async (css) => {
  const el = R().querySelector(css);
  if (!el) throw new Error("not found: " + css);
  el.click();
  await wait(60);
};
true;
"""

RUN_STATE = """
async ([steps]) => {
  const go = new Function("return (async () => {" + steps + "})();");
  await window.__mount(); await go();
  const list = window.__listActions();
  const out = {};
  for (const { action, events } of list) {
    for (const ev of events) {
      await window.__mount(); await go();
      out[action + "|" + ev] = window.__traceAction(action, ev);
    }
  }
  return out;
}
"""


def _source_actions() -> set[str]:
    """Every action name the panel can render or route."""
    names: set[str] = set()
    for path in PANEL_DIR.glob("*.js"):
        if path.name == "cover-automatic-card.js":
            continue
        text = path.read_text(encoding="utf-8")
        names |= set(re.findall(r'data-action=\\?["\']?([a-z0-9-]+)', text))
        names |= set(re.findall(r'\[data-action="([a-z0-9-]+)"\]', text))
        if path.name == "events.js":
            names |= set(re.findall(r'case "([a-z0-9-]+)"', text))
    return names


@pytest.fixture(scope="module")
def action_map(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.route(lambda url: not url.startswith(base_url), lambda route: route.abort())
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base_url}/tests/frontend/harness.html?lang=en&mode=panel")
    page.wait_for_function("window.__ready === true")
    page.evaluate(TRACER + "\ntrue;")
    page.evaluate(PAGE_HELPERS)
    page.evaluate("window.__installTracer()")
    result: dict[str, dict] = {}
    for state, steps in STATES.items():
        for key, value in page.evaluate(RUN_STATE, [steps]).items():
            result[f"{state}|{key}"] = value
    ctx.close()
    assert errors == [], errors
    return result


def test_action_map_unchanged(action_map) -> None:
    if os.environ.get("UPDATE_ACTION_MAP") == "1":
        ACTION_MAP.write_text(json.dumps(action_map, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("action_map.json regenerated")
    expected = json.loads(ACTION_MAP.read_text(encoding="utf-8"))
    missing = sorted(set(expected) - set(action_map))
    added = sorted(set(action_map) - set(expected))
    changed = sorted(k for k in set(expected) & set(action_map) if expected[k] != action_map[k])
    assert not missing and not added and not changed, {
        "missing": missing, "added": added,
        "changed": {k: {"expected": expected[k], "now": action_map[k]} for k in changed},
    }


def test_every_action_is_reached(action_map) -> None:
    reached = {key.split("|")[1] for key in action_map}
    not_reached = _source_actions() - reached - set(UNREACHED)
    assert not not_reached, sorted(not_reached)
    # The list of exceptions must not hide an action that is now reached
    assert not (set(UNREACHED) & reached), sorted(set(UNREACHED) & reached)


def _active(value) -> bool:
    return bool(value and (value["calls"] or value["state"] or value["events"] or value["dom"]))


def test_every_action_does_something(action_map) -> None:
    """A data-action that calls nothing and changes nothing has lost its handler.

    Inputs get both an input and a change event: one of them is enough.
    """
    by_action: dict[str, bool] = {}
    for key, value in action_map.items():
        state, action, _event = key.split("|")
        by_action[f"{state}|{action}"] = by_action.get(f"{state}|{action}", False) or _active(value)
    idle = sorted(k for k, active in by_action.items() if not active)
    assert idle == [], idle

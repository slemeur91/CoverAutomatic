"""Settings > House: sky compass (north up, house, sun, moon) and today's sun."""
from __future__ import annotations

SKY = "/custom_components/cover_automatic/panel/sky.js"


def _house(m) -> None:
    m.tab("settings")
    m.click('.settings-nav-btn[data-section="house"]')
    m.page.wait_for_timeout(200)


def test_astronomy(mount) -> None:
    """Sun, moon and day boundaries computed in the panel."""
    m = mount()
    r = m.js(f"""(async () => {{
      const sky = await import("{SKY}");
      // Home Assistant's sun.sun at this location and time: 303.19° / -38.53°
      const sun = sky.sunPosition(new Date("2026-10-20T22:52:48+02:00"), 48.548, 2.276);
      const start = sky.dayStartIn(new Date("2026-10-21T15:00:00+02:00"), "Europe/Paris");
      const ill = sky.moonIllumination(new Date("2026-10-21T15:00:00+02:00"));
      const samples = sky.sunDay(start, 48.548, 2.276, 5);
      const all = sky.facadeWindows({{ azimuth_start: 0, azimuth_end: 0, min_elevation: 0 }}, samples);
      const up = samples.filter((s) => s.elevation >= 0);
      return {{ sun, start: start.toISOString(), fraction: ill.fraction,
        phases: [0, 0.25, 0.5, 0.75, 0.99].map(sky.moonPhaseKey),
        all, firstUp: up[0].min, lastUp: up[up.length - 1].min, n: samples.length }};
    }})()""")
    assert abs(r["sun"]["azimuth"] - 303.19) < 1.5
    assert abs(r["sun"]["elevation"] + 38.53) < 1.5
    assert r["start"] == "2026-10-20T22:00:00.000Z"  # midnight in Paris (UTC+2)
    assert 0 <= r["fraction"] <= 1
    assert r["phases"] == ["new", "first_quarter", "full", "last_quarter", "new"]
    assert r["n"] == 289  # every 5 min, 00:00 to 24:00
    # A facade facing every direction is lit from sunrise to sunset
    assert r["all"] == [[r["firstUp"], r["lastUp"] + 5]]
    assert m.errors() == []


def test_house_section(mount) -> None:
    m = mount("fr")
    _house(m)
    r = m.js("""(() => {
      const root = window.__el.shadowRoot;
      const svg = root.querySelector(".settings-house-compass svg");
      const texts = [...svg.querySelectorAll(":scope > text")];
      const y = (t) => parseFloat(texts.find((e) => e.textContent === t).getAttribute("y"));
      return {
        northUp: y("N") < y("S"),
        house: root.querySelector("#compass-house").getAttribute("transform"),
        badges: [...svg.querySelectorAll("text[fill='#fff']")].map((e) => e.textContent),
        info: root.querySelector(".settings-house-sky").textContent,
        strips: root.querySelectorAll(".sun-today svg circle[r='5']").length,
        title: root.querySelector(".sun-today-head").textContent,
      };
    })()""")
    assert r["northUp"]
    assert r["house"].startswith("rotate(35,")
    assert sorted(r["badges"]) == sorted(["N", "E", "S", "O"])
    assert "Soleil" in r["info"] and "Lune" in r["info"] and "Gibbeuse croissante" in r["info"]
    assert r["strips"] == 10  # one per facade
    assert "Ensoleillement des façades aujourd'hui" in r["title"]
    assert m.errors() == []


def test_house_drag_north_up(mount) -> None:
    """Dragging towards the bottom gives 0°, towards the east (right) -90°."""
    m = mount()
    _house(m)
    house = m.root("#compass-house").bounding_box()
    svg = m.root(".settings-house-compass svg").bounding_box()
    cx, cy = house["x"] + house["width"] / 2, house["y"] + house["height"] / 2
    m.page.mouse.move(cx, cy)
    m.page.mouse.down()
    m.page.mouse.move(cx, svg["y"] + svg["height"] - 4, steps=4)
    assert m.root("#house-rotation-input").input_value() == "0"
    m.page.mouse.move(svg["x"] + svg["width"] - 4, cy, steps=4)
    assert m.root("#house-rotation-input").input_value() == "-90"
    m.page.mouse.up()
    assert m.errors() == []


def test_sky_follows_sun_updates(mount) -> None:
    m = mount("fr")
    _house(m)
    m.js("""(() => {
      const hass = window.__hass;
      const st = hass.states["sun.sun"];
      const states = { ...hass.states, "sun.sun": { ...st, attributes: { ...st.attributes, azimuth: 250.4, elevation: 12.3 } } };
      window.__el.hass = { ...hass, states };
    })()""")
    m.page.wait_for_timeout(200)
    info = m.js("window.__el.shadowRoot.querySelector('.settings-house-sky').textContent")
    assert "250,4°" in info and "12,3°" in info
    # The rotation input is not rebuilt
    assert m.root("#house-rotation-input").input_value() == "35"
    assert m.errors() == []

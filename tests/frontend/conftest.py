"""Fixtures of the frontend tests: local HTTP server, headless Chromium, mounted panel.

Skipped when Playwright is not installed (the Python test job does not need it).
Run alone with:  pytest tests/frontend --confcutdir=tests/frontend
"""
from __future__ import annotations

import functools
import os
import threading
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[2]
HARNESS = "/tests/frontend/harness.html"
# Fixed browser clock: the sky drawings (sun path, moon, current time) are the
# same on every run. Timers keep running.
FIXED_TIME = "2026-10-21T15:00:00+02:00"
# Answer of the GitHub API for the panel's update check (no network in tests)
LATEST_RELEASE = '{"tag_name": "v0.0.0", "html_url": "https://example.invalid"}'


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 -- stdlib signature
        pass

    def end_headers(self) -> None:
        # Always fetch the current files (the panel modules change between runs)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


@pytest.fixture(scope="session")
def base_url() -> Iterator[str]:
    handler = functools.partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser() -> Iterator[Any]:
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except sync_api.Error as err:
            # Python package without its browser: skip locally, fail in the
            # CI frontend job (REQUIRE_BROWSER=1) so the tests cannot vanish.
            if os.environ.get("REQUIRE_BROWSER") == "1":
                raise
            pytest.skip(f"Chromium not available (playwright install chromium): {err}")
        yield browser
        browser.close()


class Mounted:
    """A page with the panel or the card mounted, and helpers for the tests."""

    def __init__(self, page: Any) -> None:
        self.page = page
        self.console_errors: list[str] = []
        page.on("console", lambda m: m.type == "error" and self.console_errors.append(m.text))

    def js(self, expression: str, arg: Any = None) -> Any:
        return self.page.evaluate(expression, arg)

    def root(self, css: str) -> Any:
        """Locator inside the mounted element's shadow root (Playwright pierces it)."""
        return self.page.locator(css)

    def click(self, css: str) -> None:
        self.page.locator(css).first.click()
        self.page.wait_for_timeout(150)

    def tab(self, name: str) -> None:
        self.click(f'.tabs [data-tab="{name}"], [data-tab="{name}"]')
        self.page.wait_for_timeout(200)

    def ws(self, msg_type: str | None = None) -> list[dict]:
        calls = self.js("window.__ws")
        return [c for c in calls if msg_type is None or c["type"] == msg_type]

    def errors(self) -> list[str]:
        return self.js("window.__errors") + self.console_errors


@pytest.fixture
def mount(browser: Any, base_url: str) -> Iterator[Callable[..., Mounted]]:
    contexts: list[Any] = []
    mounted: list[Mounted] = []

    def _mount(lang: str = "fr", mode: str = "panel", init_script: str | None = None,
               width: int = 1280, height: int = 900) -> Mounted:
        ctx = browser.new_context(viewport={"width": width, "height": height})
        contexts.append(ctx)
        # Only the local server is reachable; the update check gets a canned answer
        ctx.route("https://api.github.com/**", lambda route: route.fulfill(
            status=200, content_type="application/json", body=LATEST_RELEASE))
        ctx.route(lambda url: not url.startswith(base_url) and "api.github.com" not in url,
                  lambda route: route.abort())
        page = ctx.new_page()
        page.clock.set_fixed_time(FIXED_TIME)
        m = Mounted(page)
        if init_script:
            page.add_init_script(init_script)
        page.goto(f"{base_url}{HARNESS}?lang={lang}&mode={mode}")
        page.wait_for_function("window.__ready === true")
        page.wait_for_timeout(300)
        mounted.append(m)
        return m

    yield _mount
    for m in mounted:
        assert m.errors() == [], m.errors()
    for ctx in contexts:
        ctx.close()

"""Playwright isolated browser workflow runner with SSRF protection and behaviour observation capture."""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

from playwright.sync_api import sync_playwright

from services.api.atlas.fingerprint import compute_fingerprint, normalize_observation
from services.api.core.config import get_settings
from services.api.core.security import validate_exploration_url

MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024  # 2 MB cap per artifact


def _attach_config_query(url: str, config_assignments: dict[str, Any], preview_token: str | None = None) -> str:
    parsed = urlparse(url)
    params = {}
    if preview_token:
        params["mv_preview"] = preview_token
    elif config_assignments:
        encoded = base64.urlsafe_b64encode(json.dumps(config_assignments).encode("utf-8")).decode("ascii")
        params["mv_sandbox_cfg"] = encoded
    query = urlencode(params)
    if parsed.query:
        query = f"{parsed.query}&{query}" if query else parsed.query
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))


def execute_workflow_observation(
    base_url: str,
    workflow_def: dict[str, Any],
    config_assignments: dict[str, Any],
    run_id: str,
    candidate_index: int,
    preview_token: str | None = None,
) -> dict[str, Any]:
    """Execute a structured workflow in an isolated Playwright Chromium context and return normalized evidence."""
    settings = get_settings()
    validate_exploration_url(base_url, registered_base_url=base_url)

    t0 = time.perf_counter()
    routes_visited: list[str] = []
    api_operations: list[str] = []
    http_status_classes: list[str] = []
    visible_components: set[str] = set()
    business_events: list[str] = []
    screenshot_path: str | None = None
    outcome = "success"
    error_message: str | None = None

    artifact_dir = Path(settings.artifact_storage_path) / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            def _on_response(resp):
                try:
                    u = urlparse(resp.url)
                    if "/api/" in u.path or "/demo/" in u.path:
                        api_operations.append(f"{resp.request.method} {u.path}")
                    http_status_classes.append(f"{resp.status // 100}xx")
                except Exception:
                    pass

            page.on("response", _on_response)

            # Intercept redirects to block SSRF
            def _handle_route(route):
                req_url = route.request.url
                try:
                    if req_url.startswith("http://") or req_url.startswith("https://"):
                        validate_exploration_url(req_url, registered_base_url=base_url)
                    route.continue_()
                except ValueError:
                    route.abort()

            page.route("**/*", _handle_route)

            start_path = workflow_def.get("start_path", "")
            initial_url = _attach_config_query(f"{base_url.rstrip('/')}{start_path}", config_assignments, preview_token)
            page.goto(initial_url, wait_until="networkidle", timeout=settings.exploration_timeout_seconds * 1000)
            routes_visited.append(urlparse(page.url).path or "/")

            for step in workflow_def.get("steps", []):
                action = step.get("action")
                timeout_ms = int(step.get("timeout_ms", 10000))
                selector = step.get("selector")
                value = step.get("value", "")

                if action == "navigate":
                    path = step.get("path", "/")
                    target = _attach_config_query(f"{base_url.rstrip('/')}{path}", config_assignments, preview_token)
                    # The initial page load already opens start_path. Avoid loading the same URL twice
                    # when a generated workflow begins with a matching navigate step.
                    if target.rstrip("/") != page.url.rstrip("/"):
                        page.goto(target, wait_until="networkidle", timeout=timeout_ms)
                        routes_visited.append(urlparse(page.url).path or "/")
                elif action == "click" and selector:
                    page.locator(selector).first.click(timeout=timeout_ms)
                    page.wait_for_timeout(150)
                elif action == "fill" and selector:
                    page.locator(selector).first.fill(str(value), timeout=timeout_ms)
                elif action == "search" and selector:
                    loc = page.locator(selector).first
                    loc.fill(str(value), timeout=timeout_ms)
                    loc.press("Enter")
                    page.wait_for_timeout(200)
                elif action == "wait":
                    if selector:
                        page.locator(selector).first.wait_for(state="visible", timeout=timeout_ms)
                    else:
                        page.wait_for_timeout(min(timeout_ms, 2000))
                elif action == "read":
                    comps = page.eval_on_selector_all(
                        "[data-mv-component]",
                        "els => els.map(e => e.getAttribute('data-mv-component')).filter(Boolean)",
                    )
                    visible_components.update(comps)
                elif action == "assert":
                    expected = step.get("expected_text", "")
                    if selector:
                        txt = page.locator(selector).first.inner_text(timeout=timeout_ms)
                        if expected and expected not in txt:
                            raise AssertionError(f"Expected '{expected}' in {selector}, got '{txt[:80]}'")
                elif action == "screenshot":
                    out_file = artifact_dir / f"cand_{candidate_index}.png"
                    raw_png = page.screenshot(full_page=False)
                    if len(raw_png) <= MAX_SCREENSHOT_BYTES:
                        out_file.write_bytes(raw_png)
                        screenshot_path = str(out_file)

                # Collect visible components & app telemetry after step
                comps = page.eval_on_selector_all(
                    "[data-mv-component]",
                    "els => els.map(e => e.getAttribute('data-mv-component')).filter(Boolean)",
                )
                visible_components.update(comps)

            # Collect business events recorded by @multiverse/sdk on window.__mvEvents
            events = page.evaluate("() => Array.isArray(window.__mvEvents) ? window.__mvEvents : []")
            for ev in events:
                if isinstance(ev, dict) and ev.get("name"):
                    business_events.append(str(ev["name"]))

            if not screenshot_path:
                out_file = artifact_dir / f"cand_{candidate_index}.png"
                raw_png = page.screenshot(full_page=False)
                if len(raw_png) <= MAX_SCREENSHOT_BYTES:
                    out_file.write_bytes(raw_png)
                    screenshot_path = str(out_file)

            context.close()
            browser.close()
    except Exception as exc:
        outcome = "failed"
        error_message = str(exc)

    duration_ms = int((time.perf_counter() - t0) * 1000)
    raw_obs = {
        "routes_visited": routes_visited,
        "visible_components": sorted(visible_components),
        "api_operations": api_operations,
        "http_status_classes": http_status_classes,
        "business_events": business_events,
        "outcome": outcome,
    }
    normalized = normalize_observation(raw_obs)
    fingerprint = compute_fingerprint(normalized)

    return {
        "status": "success" if outcome == "success" else "failed",
        "fingerprint": fingerprint,
        "normalized": normalized,
        "duration_ms": duration_ms,
        "artifact_path": screenshot_path,
        "error": error_message,
    }

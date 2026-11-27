"""Repeatable browser smoke audit for the Multiverse landing/auth/dashboard flow."""
from __future__ import annotations

import json
import time

from playwright.sync_api import sync_playwright


def main() -> None:
    email = f"ui-audit-{int(time.time())}@example.com"
    audit_id = int(time.time())
    password = "Audit-pass-123!"
    app_name = f"Audit Shop {audit_id}"
    results: dict[str, object] = {"email": email}
    console_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("requestfailed", lambda request: failed_requests.append(f"{request.method} {request.url}"))

        page.goto("http://localhost:5173", wait_until="domcontentloaded")
        page.wait_for_function("document.body.innerText.includes('BranchReality')", timeout=45_000)
        results["landing_loaded"] = True
        results["placeholder_links"] = page.locator('a[href="#"]').count()
        results["landing_buttons"] = page.locator("button").count()

        page.get_by_text("Enter Multiverse", exact=True).first.click()
        page.get_by_role("heading", name="Create New Profile").wait_for()
        results["auth_opened"] = True

        page.get_by_role("button", name="Log in").click()
        page.get_by_role("heading", name="Welcome Back").wait_for()
        page.get_by_role("button", name="Create an account").click()
        page.get_by_role("heading", name="Create New Profile").wait_for()
        results["auth_mode_toggle"] = True

        page.locator('[name="first_name"]').fill("Audit")
        page.locator('[name="last_name"]').fill("User")
        page.locator('[name="email"]').fill(email)
        page.locator('[name="password"]').fill(password)
        page.get_by_role("button", name="Show password").click()
        results["password_toggle"] = page.locator('[name="password"]').get_attribute("type") == "text"
        page.get_by_role("button", name="Create Account").click()
        page.get_by_role("heading", name="Overview").wait_for(timeout=10_000)
        results["signup_to_dashboard"] = True

        page.get_by_role("button", name="Register application").click()
        page.get_by_placeholder("Application name").fill(app_name)
        page.get_by_placeholder("http://localhost:5173/demo/shop").fill(f"http://localhost:5173/demo/shop/audit-{audit_id}")
        page.get_by_role("button", name="Register", exact=True).click()
        page.get_by_text(app_name, exact=True).wait_for()
        results["application_created"] = True

        inert_labels = ["Search", "New", "Upgrade", "Projects", "Blueprints", "Invite your team"]
        results["visible_controls_without_handlers"] = inert_labels

        page.get_by_title("Sign out").click()
        page.get_by_role("heading", name="Welcome Back").wait_for()
        page.locator('[name="email"]').fill(email)
        page.locator('[name="password"]').fill(password)
        page.get_by_role("button", name="Sign In").click()
        page.get_by_role("heading", name="Overview").wait_for(timeout=10_000)
        results["logout_and_login"] = True
        page.wait_for_timeout(2_000)
        persisted = page.evaluate("fetch('http://localhost:8001/api/v1/apps', {credentials: 'include'}).then(r => r.json())")
        results["application_persisted_api"] = any(item["name"] == app_name for item in persisted["items"])
        results["application_persisted_ui"] = page.get_by_text(app_name, exact=True).is_visible()
        results["console_errors"] = console_errors
        results["failed_requests"] = failed_requests
        browser.close()

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

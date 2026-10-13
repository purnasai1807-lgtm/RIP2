"""Authenticated Playwright acceptance test for a dedicated staging/CI environment.

For a disposable CI database, set BROWSER_TEST_REGISTER=true to create a one-off
synthetic @aceec.ac.in account through the real registration form. Never enable that
flag against production. For staging, provide an already-provisioned test account.
"""
from __future__ import annotations
import os
import sys
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BROWSER_BASE_URL", "").rstrip("/")
EMAIL = os.environ.get("BROWSER_TEST_EMAIL", "")
PASSWORD = os.environ.get("BROWSER_TEST_PASSWORD", "")
REGISTER = os.environ.get("BROWSER_TEST_REGISTER", "false").lower() == "true"
ALLOW_HTTP = os.environ.get("BROWSER_ALLOW_HTTP", "false").lower() == "true"


def csrf(page) -> str:
    field = page.locator('input[name="_csrf_token"]')
    if field.count() == 0:
        raise RuntimeError("CSRF field was not found on the form")
    return field.first.input_value()


def main() -> int:
    allowed_scheme = BASE_URL.startswith("https://") or (ALLOW_HTTP and BASE_URL.startswith("http://127.0.0.1"))
    if not allowed_scheme or not EMAIL or not PASSWORD:
        print("ERROR: set BROWSER_BASE_URL, BROWSER_TEST_EMAIL and BROWSER_TEST_PASSWORD; HTTPS is required except explicit 127.0.0.1 CI.", file=sys.stderr)
        return 2
    if REGISTER and not EMAIL.lower().endswith("@aceec.ac.in"):
        print("ERROR: registration test account must use @aceec.ac.in.", file=sys.stderr)
        return 2
    browser_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        try:
            response = page.goto(BASE_URL + ("/register" if REGISTER else "/login"), wait_until="networkidle", timeout=30000)
            if response is None or response.status >= 400:
                raise RuntimeError(f"Authentication page returned HTTP {response.status if response else 'no response'}")
            page.locator('input[name="email"]').fill(EMAIL)
            page.locator('input[name="password"]').fill(PASSWORD)
            if REGISTER:
                page.locator('input[name="name"]').fill("CampusRipple Automated Test")
            page.locator('input[name="_csrf_token"]').fill(csrf(page))
            page.locator('button[type="submit"], input[type="submit"]').first.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            if REGISTER and "/dashboard" not in page.url:
                raise RuntimeError("Synthetic registration did not reach dashboard; inspect validation or app logs.")
            if not REGISTER and "/login" in page.url:
                raise RuntimeError("Test account did not authenticate; verify account status and credentials.")
            for path in ("/dashboard", "/college-workspace", "/scenarios/new", "/reports"):
                result = page.goto(BASE_URL + path, wait_until="networkidle", timeout=30000)
                if result is None or result.status >= 400:
                    raise RuntimeError(f"{path} returned HTTP {result.status if result else 'no response'}")
                if "/login" in page.url:
                    raise RuntimeError(f"Session was not retained while opening {path}")
            # Verify authorization boundary: a student must not reach admin user management.
            denied = page.goto(BASE_URL + "/admin/users", wait_until="networkidle", timeout=30000)
            if denied is None or denied.status not in (302, 403):
                raise RuntimeError(f"Student authorization boundary unexpected status: {denied.status if denied else 'no response'}")
            if browser_errors:
                raise RuntimeError(f"Browser JavaScript errors detected ({len(browser_errors)}): " + "; ".join(browser_errors[:3]))
            print("PASS: authenticated browser routes, session persistence, and student/admin authorization boundary.")
            return 0
        except Exception as exc:
            print(f"FAIL: authenticated browser acceptance test: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            browser.close()

if __name__ == "__main__":
    raise SystemExit(main())

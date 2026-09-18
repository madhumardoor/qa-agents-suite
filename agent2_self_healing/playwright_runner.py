"""
playwright_runner.py
=====================
Live-mode integration: runs a real Playwright browser session, attempts to
find an element by its stored locator, and if that fails, grabs the live
DOM + a screenshot, hands them to the healer, updates the locator store,
and retries.

This file is only imported/executed when MODE=live and Playwright is
installed with browsers (`playwright install chromium`). In mock mode, the
agent works entirely off the bundled dom_before.html / dom_after.html files
via mock_runner.py, so you can see the full healing flow with zero setup.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from dom_analyzer import find_best_match
from locator_store import get as get_locator, update as update_locator


def run_step_with_healing(page, step_key: str, css_fallback: str, url: str):
    """
    Attempts to locate & click/fill an element using the stored locator.
    On failure, captures the live DOM, finds the best match, updates the
    store, and retries once.
    """
    stored = get_locator(step_key)
    selector = _locator_to_css(stored["current"]) if stored else css_fallback

    try:
        page.wait_for_selector(selector, timeout=3000)
        return selector
    except Exception:
        print(f"[playwright_runner] Locator '{selector}' failed for step '{step_key}'. Attempting self-heal...")
        live_dom = page.content()
        broken_locator = stored["current"] if stored else {"tag": "input"}
        best_match, confidence = find_best_match(broken_locator, live_dom)

        if not best_match:
            raise RuntimeError(f"Self-healing failed for step '{step_key}': no confident match found.")

        new_locator = best_match.as_locator_dict()
        update_locator(step_key, new_locator, confidence, healed_from=broken_locator)
        new_selector = _locator_to_css(new_locator)
        print(f"[playwright_runner] Healed '{step_key}' -> {new_selector} (confidence={confidence})")
        page.wait_for_selector(new_selector, timeout=3000)
        return new_selector


def _locator_to_css(locator: dict) -> str:
    if locator.get("id"):
        return f"#{locator['id']}"
    if locator.get("data_testid"):
        return f"[data-testid='{locator['data_testid']}']"
    if locator.get("name"):
        return f"{locator.get('tag', '*')}[name='{locator['name']}']"
    return locator.get("xpath", locator.get("tag", "*"))

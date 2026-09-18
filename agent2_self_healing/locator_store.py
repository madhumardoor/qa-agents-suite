"""
locator_store.py
=================
A simple JSON-backed store of "known-good" locators per test step. This is
what real self-healing frameworks (Healenium, etc.) do under the hood:
persist the last-working locator, and when a step fails, look it up here
first before trying to re-discover it from the DOM.

In a real Selenium/Playwright suite, your page objects would read from this
store instead of hardcoding locators, e.g.:

    email_field = driver.find_element(By.CSS_SELECTOR, locator_store.get("login.email"))
"""

import json
from pathlib import Path
from typing import Optional

STORE_PATH = Path(__file__).resolve().parent / "output" / "locator_store.json"
STORE_PATH.parent.mkdir(exist_ok=True)


def _load() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text())
    return {}


def _save(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, indent=2))


def get(step_key: str) -> Optional[dict]:
    return _load().get(step_key)


def update(step_key: str, new_locator: dict, confidence: float, healed_from: dict) -> None:
    data = _load()
    entry = data.get(step_key, {"history": []})
    entry["current"] = new_locator
    entry["history"].append({
        "healed_from": healed_from,
        "healed_to": new_locator,
        "confidence": confidence,
    })
    data[step_key] = entry
    _save(data)


def seed(step_key: str, locator: dict) -> None:
    data = _load()
    data[step_key] = {"current": locator, "history": []}
    _save(data)

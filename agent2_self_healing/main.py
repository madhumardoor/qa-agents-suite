"""
Agent 2: Self-Healing Automation Agent
========================================
Detects when a locator that used to work no longer matches anything in the
DOM (because the UI changed), finds the most likely replacement element
using attribute + text similarity scoring, updates a persistent locator
store, and reports what it healed.

USAGE (mock mode — no browser or API keys needed)
--------------------------------------------------
  python main.py --demo
      Simulates 3 locators breaking after a UI redesign (dom_before.html ->
      dom_after.html) and heals them.

USAGE (live mode — requires `playwright install chromium`)
------------------------------------------------------------
  MODE=live python main.py --live-url https://your-app.com/login
      Opens a real browser, attempts known locators, self-heals on failure.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from dom_analyzer import find_best_match
from locator_store import seed, get as get_locator, update as update_locator

MOCK_DIR = Path(__file__).resolve().parent / "mock_data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def run_mock_demo():
    print("[main] Running MOCK self-healing demo (no browser required).\n")

    before_html = (MOCK_DIR / "dom_before.html").read_text()
    after_html = (MOCK_DIR / "dom_after.html").read_text()

    from dom_analyzer import parse_dom

    before_elements = parse_dom(before_html)
    print(f"[main] Captured {len(before_elements)} known-good locators from the OLD DOM.\n")

    # Seed the locator store with the "before" locators, keyed by logical step name
    step_keys = ["login.email_field", "login.password_field", "login.submit_button"]
    for key, el in zip(step_keys, before_elements):
        seed(key, el.as_locator_dict())
        print(f"  Seeded '{key}' -> {el.as_locator_dict()['id'] or el.as_locator_dict()['xpath']}")

    print("\n[main] Simulating UI redesign deploy... locators from the old DOM no longer exist.\n")
    print("[main] Attempting to heal each broken locator against the NEW DOM:\n")

    healed_report = []
    for key in step_keys:
        stored = get_locator(key)
        broken_locator = stored["current"]
        best_match, confidence = find_best_match(broken_locator, after_html)

        if best_match:
            new_locator = best_match.as_locator_dict()
            update_locator(key, new_locator, confidence, healed_from=broken_locator)
            status = "HEALED"
            new_id = new_locator.get("id") or new_locator.get("data_testid") or new_locator.get("xpath")
        else:
            status = "FAILED - manual fix required"
            new_id = None

        old_id = broken_locator.get("id") or broken_locator.get("xpath")
        print(f"  [{status}] '{key}': '{old_id}'  ->  '{new_id}'  (confidence={confidence})")
        healed_report.append({
            "step": key, "status": status, "old_locator": old_id,
            "new_locator": new_id, "confidence": confidence,
        })

    report_path = OUTPUT_DIR / "healing_report.json"
    report_path.write_text(json.dumps(healed_report, indent=2))
    print(f"\n[main] Healing report saved to: {report_path}")
    print(f"[main] Locator store saved to: {OUTPUT_DIR / 'locator_store.json'}")

    healed_count = sum(1 for r in healed_report if r["status"] == "HEALED")
    print(f"\n[main] Result: {healed_count}/{len(step_keys)} locators self-healed without human intervention.")


def run_live(live_url: str):
    from playwright.sync_api import sync_playwright
    from playwright_runner import run_step_with_healing

    print(f"[main] LIVE mode: launching browser against {live_url}\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(live_url)

        # Example: heal the email field, password field, submit button.
        # In a real suite these calls live inside your page object methods.
        run_step_with_healing(page, "login.email_field", "#email-input", live_url)
        run_step_with_healing(page, "login.password_field", "#password-input", live_url)
        run_step_with_healing(page, "login.submit_button", "#login-btn", live_url)

        browser.close()
    print("[main] Live run complete. See output/locator_store.json for healed locators.")


def main():
    parser = argparse.ArgumentParser(description="Self-Healing Automation Agent")
    parser.add_argument("--demo", action="store_true", help="Run the offline mock healing demo")
    parser.add_argument("--live-url", help="Run against a real URL in live mode (requires Playwright browsers installed)")
    args = parser.parse_args()

    print(f"[main] Running in {config.mode.upper()} mode.\n")

    if args.live_url and config.is_live:
        run_live(args.live_url)
    else:
        run_mock_demo()


if __name__ == "__main__":
    main()

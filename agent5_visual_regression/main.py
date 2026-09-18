"""
Agent 5: Visual Regression & Accessibility Agent
====================================================
On every build: takes a screenshot, compares it pixel-by-pixel against a
stored baseline to detect layout shift, and runs accessibility checks
(missing alt text, unlabeled inputs, low color contrast, non-keyboard
controls) using real WCAG 2.1 contrast math. Posts a combined report as a
PR comment.

USAGE (mock mode — no browser needed)
---------------------------------------
  python main.py --demo
      Uses bundled baseline/candidate screenshots + a sample HTML page.

USAGE (live mode — requires `playwright install chromium`)
------------------------------------------------------------
  MODE=live python main.py --url https://your-app.com/checkout --pr 42
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from visual_diff import compare_images
from a11y_checker import check_html
from github_client import post_pr_comment

MOCK_DIR = Path(__file__).resolve().parent / "mock_data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def run_mock_demo(pr_number: str):
    print("[main] Running MOCK visual regression + a11y demo.\n")

    baseline = MOCK_DIR / "screenshot_baseline.png"
    candidate = MOCK_DIR / "screenshot_candidate.png"

    print("[main] Comparing baseline vs candidate screenshot (real pixel diff)...")
    visual_result = compare_images(str(baseline), str(candidate))
    print(f"  -> {visual_result['pct_pixels_changed']}% of pixels changed. {visual_result['verdict']}")
    print(f"  -> Heatmap saved to: {visual_result['heatmap_path']}\n")

    print("[main] Running accessibility checks on candidate page HTML...")
    html = (MOCK_DIR / "candidate_page.html").read_text()
    violations = check_html(html)
    print(f"  -> {len(violations)} accessibility violation(s) found.\n")
    for v in violations:
        print(f"    [{v['impact'].upper()}] {v['rule']}: {v['description']}")

    report = build_report(visual_result, violations)
    report_path = OUTPUT_DIR / "visual_a11y_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n[main] Full report saved to: {report_path}")

    post_pr_comment(pr_number, report)
    print("\n[main] Done. Every company wants this in 2026.")


def build_report(visual_result: dict, violations: list) -> str:
    lines = ["## 🔍 Visual Regression & Accessibility Report\n"]

    lines.append("### 📸 Visual Regression")
    lines.append(f"- **Pixels changed:** {visual_result['pct_pixels_changed']}%")
    lines.append(f"- **Verdict:** {visual_result['verdict']}")
    if visual_result["changed_region_bbox"]:
        lines.append(f"- **Changed region (px):** {visual_result['changed_region_bbox']}")
    lines.append("")

    lines.append(f"### ♿ Accessibility ({len(violations)} violation(s) found)")
    if not violations:
        lines.append("No accessibility violations detected.")
    else:
        by_impact = {"critical": [], "serious": [], "moderate": [], "minor": []}
        for v in violations:
            by_impact.setdefault(v["impact"], []).append(v)
        for impact in ["critical", "serious", "moderate", "minor"]:
            for v in by_impact.get(impact, []):
                lines.append(f"- **[{impact.upper()}] {v['rule']}** — {v['description']}")
                lines.append(f"  - *WCAG:* {v['wcag']}")
                lines.append(f"  - *Fix:* {v['fix']}")

    return "\n".join(lines)


def run_live(url: str, pr_number: str):
    from playwright.sync_api import sync_playwright
    from a11y_checker import run_axe_live

    print(f"[main] LIVE mode: capturing screenshot of {url}\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(url)

        candidate_path = OUTPUT_DIR / "live_candidate.png"
        page.screenshot(path=str(candidate_path), full_page=True)

        baseline_path = Path(__file__).resolve().parent / "baselines" / "current_baseline.png"
        if not baseline_path.exists():
            baseline_path.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(baseline_path), full_page=True)
            print(f"[main] No baseline found — saved this run as the new baseline: {baseline_path}")
            visual_result = {"pct_pixels_changed": 0.0, "verdict": "Baseline created.", "changed_region_bbox": None, "heatmap_path": ""}
        else:
            visual_result = compare_images(str(baseline_path), str(candidate_path))

        violations = run_axe_live(page)
        browser.close()

    report = build_report(visual_result, violations)
    report_path = OUTPUT_DIR / "visual_a11y_report.md"
    report_path.write_text(report)
    post_pr_comment(pr_number, report)
    print(f"[main] Report saved and posted. See {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Visual Regression & Accessibility Agent")
    parser.add_argument("--demo", action="store_true", help="Run offline mock demo")
    parser.add_argument("--url", help="Live URL to screenshot + scan (requires Playwright)")
    parser.add_argument("--pr", default="1", help="PR number to comment on")
    args = parser.parse_args()

    print(f"[main] Running in {config.mode.upper()} mode.\n")

    if args.url and config.is_live:
        run_live(args.url, args.pr)
    else:
        run_mock_demo(args.pr)


if __name__ == "__main__":
    main()

"""
Agent 1: Test Case Generator
=============================
Reads a Jira ticket (PRD / user story), generates positive/negative/edge
test cases, and exports them to TestRail (or a local CSV in mock mode).

USAGE
-----
  python main.py --ticket QA-123
  python main.py --file path/to/prd.txt
  python main.py                      # uses bundled sample PRD in mock mode

Set MODE=live in .env to hit real Jira/TestRail/LLM APIs.
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from jira_client import fetch_ticket_text, create_ticket_link_comment
from generator import generate_test_cases, to_markdown
from testrail_client import export_test_cases

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Test Case Generator Agent")
    parser.add_argument("--ticket", help="Jira ticket key, e.g. QA-123 (live mode) or any label (mock mode)")
    parser.add_argument("--file", help="Path to a local PRD/user-story text file")
    args = parser.parse_args()

    print(f"[main] Running in {config.mode.upper()} mode.\n")

    if args.file:
        prd_text = Path(args.file).read_text()
        ticket_label = Path(args.file).stem
    else:
        ticket_key = args.ticket or "QA-DEMO-1"
        prd_text = fetch_ticket_text(ticket_key)
        ticket_label = ticket_key

    print(f"[main] Loaded PRD/user story ({len(prd_text)} chars). Generating test cases...\n")
    cases = generate_test_cases(prd_text)
    print(f"[main] Generated {len(cases)} test cases.\n")

    # Save markdown report
    md_path = OUTPUT_DIR / f"{ticket_label}_test_cases.md"
    md_path.write_text(to_markdown(cases))
    print(f"[main] Markdown report saved to: {md_path}")

    # Export to TestRail (or CSV in mock mode)
    result = export_test_cases(cases, suite_name=f"{ticket_label} - Generated Suite")
    print(f"[main] {result}")

    # Optionally comment back on the Jira ticket
    create_ticket_link_comment(
        ticket_label,
        f"QA Agent generated {len(cases)} test cases. See TestRail suite / attached report.",
    )

    print("\n[main] Done.")


if __name__ == "__main__":
    main()

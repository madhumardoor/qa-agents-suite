"""
Agent 3: Bug Report & Log Analyzer Agent
===========================================
When CI fails: pulls the console log from Jenkins, parses out failures,
classifies root cause, creates Jira tickets with reproduction steps +
severity, and posts a summary to Slack. Ends the "copy-paste logs into
tickets" workflow.

USAGE
-----
  python main.py --job checkout-service-pipeline
  python main.py --log-file path/to/log.txt
  python main.py                                   # uses bundled sample log
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from jenkins_client import fetch_console_log, get_build_metadata
from log_parser import parse_log, summarize_with_llm
from jira_bug_creator import create_bug_tickets
from slack_notifier import post_message

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Bug Report & Log Analyzer Agent")
    parser.add_argument("--job", help="Jenkins job name")
    parser.add_argument("--build", default="lastFailedBuild", help="Build number (default: lastFailedBuild)")
    parser.add_argument("--log-file", help="Path to a local CI log file instead of fetching from Jenkins")
    args = parser.parse_args()

    print(f"[main] Running in {config.mode.upper()} mode.\n")

    job_name = args.job or "checkout-service-pipeline"

    if args.log_file:
        log_text = Path(args.log_file).read_text(encoding="utf-8")
        build_meta = {"number": "local", "url": args.log_file, "result": "FAILURE"}
    else:
        log_text = fetch_console_log(job_name, args.build)
        build_meta = get_build_metadata(job_name, args.build)

    print(f"[main] Fetched log ({len(log_text)} chars) for build {build_meta['number']}.\n")

    failures = parse_log(log_text)
    print(f"[main] Parsed {len(failures)} failure(s):\n")
    for f in failures:
        print(f"  - {f.test_name}")
        print(f"      error: {f.error_type} | root cause: {f.root_cause_label} | severity: {f.severity}")

    if not failures:
        print("\n[main] No failures found in this log — nothing to report.")
        return

    summary = summarize_with_llm(log_text, failures)
    print(f"\n[main] Root cause summary:\n{summary}\n")

    ticket_refs = create_bug_tickets(failures, build_url=build_meta["url"])

    slack_text = (
        f":red_circle: *CI Build Failed* — `{job_name}` build #{build_meta['number']}\n"
        f"{summary}\n\n"
        f"*Tickets created:* {', '.join(ticket_refs)}\n"
        f"*Build:* {build_meta['url']}"
    )
    post_message(slack_text)

    print("\n[main] Done. No more copy-paste logs.")


if __name__ == "__main__":
    main()

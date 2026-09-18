"""
log_parser.py
=============
Parses raw CI console logs to extract:
  - failed test names
  - stack traces / error types
  - a best-guess root cause classification
  - a severity rating

Works via regex/heuristics in mock mode (fast, deterministic, no API key
needed) and can optionally hand the extracted failures to an LLM in live
mode for a richer natural-language root-cause summary.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from shared.llm_client import call_llm

FAIL_LINE_RE = re.compile(r"^\s*(FAIL|✕|✗)\s+(.+)$", re.MULTILINE)
ERROR_TYPE_RE = re.compile(r"(TypeError|ReferenceError|AssertionError|Error|Timeout(?:Error)?|ETIMEDOUT|ECONNREFUSED)[:\s]")
STACK_FRAME_RE = re.compile(r"at\s+.+\((.+):(\d+):(\d+)\)")

ROOT_CAUSE_RULES = [
    (re.compile(r"ETIMEDOUT|timeout", re.I), "Network/Infra Timeout",
     "The service call timed out, suggesting the downstream dependency was slow, unavailable, or network-partitioned during the test run."),
    (re.compile(r"ECONNREFUSED", re.I), "Connection Refused",
     "The target service refused the connection — likely not running, wrong port, or a firewall/security-group issue."),
    (re.compile(r"Cannot read propert(y|ies) of undefined", re.I), "Null/Undefined Reference",
     "Code attempted to access a property on an undefined object, typically because an upstream API response shape changed or a dependency call failed silently."),
    (re.compile(r"AssertionError|expect.*toBe|Expected:.*Received:", re.I), "Assertion Mismatch",
     "The actual value returned by the system under test did not match the expected value — likely a genuine functional regression or an out-of-date test expectation."),
    (re.compile(r"401|403|Unauthorized|Forbidden", re.I), "Auth/Permissions Failure",
     "The request was rejected due to authentication or authorization issues — check for expired tokens/credentials in the test environment."),
]


@dataclass
class TestFailure:
    test_name: str
    error_type: str = "Unknown"
    error_message: str = ""
    file_location: str = ""
    root_cause_label: str = "Unclassified"
    root_cause_explanation: str = ""
    severity: str = "Medium"


def parse_log(log_text: str) -> List[TestFailure]:
    failures: List[TestFailure] = []

    # Split log into blocks around each "●" detailed failure section (Jest-style),
    # falling back to FAIL lines generically for other frameworks.
    blocks = re.split(r"\n\s*●\s+", log_text)
    detail_blocks = blocks[1:] if len(blocks) > 1 else []

    fail_names = [m.group(2).strip() for m in FAIL_LINE_RE.finditer(log_text)]

    if detail_blocks:
        for block, name_hint in zip(detail_blocks, fail_names + [None] * len(detail_blocks)):
            failures.append(_analyze_block(block, name_hint))
    elif fail_names:
        for name in fail_names:
            failures.append(TestFailure(test_name=name))

    return failures


def _analyze_block(block: str, name_hint: str) -> TestFailure:
    # Trim off any trailing content that belongs to the NEXT test's FAIL header,
    # since the split only breaks on "●" markers, not "FAIL" lines.
    next_fail_match = re.search(r"\n\s*FAIL\s+", block)
    if next_fail_match:
        block = block[:next_fail_match.start()]

    test_name = block.splitlines()[0].strip() if block.strip() else (name_hint or "Unknown test")

    error_match = ERROR_TYPE_RE.search(block)
    error_type = error_match.group(1) if error_match else "Error"

    # First non-empty line after the header that looks like a message
    message_lines = [l.strip() for l in block.splitlines()[1:4] if l.strip()]
    error_message = message_lines[0] if message_lines else ""

    frame_match = STACK_FRAME_RE.search(block)
    file_location = f"{frame_match.group(1)}:{frame_match.group(2)}" if frame_match else ""

    root_cause_label, root_cause_explanation = "Unclassified", "Root cause could not be automatically determined from the log; manual review recommended."
    for pattern, label, explanation in ROOT_CAUSE_RULES:
        if pattern.search(block):
            root_cause_label, root_cause_explanation = label, explanation
            break

    severity = "Critical" if root_cause_label in ("Network/Infra Timeout", "Connection Refused") else \
        "High" if root_cause_label == "Assertion Mismatch" else "Medium"

    return TestFailure(
        test_name=test_name,
        error_type=error_type,
        error_message=error_message,
        file_location=file_location,
        root_cause_label=root_cause_label,
        root_cause_explanation=root_cause_explanation,
        severity=severity,
    )


def summarize_with_llm(log_text: str, failures: List[TestFailure]) -> str:
    """Optional live-mode enrichment: ask the LLM for a human-readable narrative summary."""
    if not config.is_live or not config.require_or_warn(config.anthropic_api_key or config.openai_api_key, "ANTHROPIC_API_KEY/OPENAI_API_KEY"):
        return _mock_summary(failures)

    system = ("You are a senior SRE/QA engineer. Given a CI log and pre-extracted failures, "
              "write a concise 3-5 sentence root-cause summary a developer could read in Slack.")
    user = f"Extracted failures:\n{failures}\n\nFull log:\n{log_text[:4000]}"
    return call_llm(system, user, max_tokens=400)


def _mock_summary(failures: List[TestFailure]) -> str:
    if not failures:
        return "No test failures detected in this log."
    labels = {f.root_cause_label for f in failures}
    return (
        f"Build failed due to {len(failures)} test failure(s) in the following categories: "
        f"{', '.join(labels)}. Primary suspect: '{failures[0].test_name}' — {failures[0].root_cause_explanation}"
    )

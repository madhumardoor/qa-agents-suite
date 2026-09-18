"""
generator.py
============
Turns PRD/user-story text into a structured list of test cases:
positive, negative, and edge cases — the way a senior QA engineer would.

Mock mode: uses a deterministic rule-based generator tuned against the
sample PRD so the demo always produces sensible output with zero API keys.

Live mode: sends the PRD to an LLM (Claude by default) with a strict JSON
schema so the output is always machine-parseable.
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Dict

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from shared.llm_client import call_llm

SYSTEM_PROMPT = """You are a senior QA engineer. Given a PRD or user story, generate a
comprehensive set of test cases covering positive, negative, and edge cases.

Return ONLY valid JSON: a list of objects, each with keys:
  "title" (string), "category" ("Positive"|"Negative"|"Edge"),
  "priority" ("Low"|"Medium"|"High"|"Critical"),
  "preconditions" (string), "steps" (list of strings), "expected_result" (string).

Generate at least 50 test cases if the PRD has enough detail to justify it;
otherwise generate as many high-quality, non-redundant cases as the content supports.
No prose, no markdown fences — JSON array only."""


def generate_test_cases(prd_text: str) -> List[Dict]:
    if config.is_live and config.require_or_warn(config.anthropic_api_key or config.openai_api_key, "ANTHROPIC_API_KEY/OPENAI_API_KEY"):
        raw = call_llm(SYSTEM_PROMPT, prd_text, max_tokens=4000)
        raw = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print("[generator] WARNING: LLM did not return clean JSON, falling back to mock generator.")
            return _mock_generate(prd_text)

    return _mock_generate(prd_text)


def _mock_generate(prd_text: str) -> List[Dict]:
    """
    Rule-based generator: parses numbered acceptance criteria out of the PRD
    and expands each into positive / negative / edge test cases. Works on
    any PRD with numbered criteria lines, not just the bundled sample.
    """
    criteria = re.findall(r"\d+\.\s*(.+)", prd_text)
    if not criteria:
        criteria = [line.strip() for line in prd_text.splitlines() if line.strip()][:10]

    cases: List[Dict] = []

    for idx, criterion in enumerate(criteria, start=1):
        base_title = criterion.rstrip(".")

        # Positive case
        cases.append({
            "title": f"Verify: {base_title}",
            "category": "Positive",
            "priority": "High" if idx <= 3 else "Medium",
            "preconditions": "User is on the relevant page with valid test data available.",
            "steps": [
                "Navigate to the feature under test.",
                f"Perform the action described: '{base_title}'.",
                "Observe the system response.",
            ],
            "expected_result": f"System behaves as specified: {base_title}.",
        })

        # Negative case
        cases.append({
            "title": f"Negative: Reject invalid input for '{base_title[:50]}'",
            "category": "Negative",
            "priority": "High",
            "preconditions": "User is on the relevant page.",
            "steps": [
                "Navigate to the feature under test.",
                "Provide invalid, malformed, or out-of-range input relevant to this requirement.",
                "Submit / trigger the action.",
            ],
            "expected_result": "System rejects the input gracefully with a clear, non-technical error message. No crash, no data corruption.",
        })

        # Edge case
        cases.append({
            "title": f"Edge: Boundary condition for '{base_title[:50]}'",
            "category": "Edge",
            "priority": "Medium",
            "preconditions": "User is on the relevant page; test data at boundary values is prepared.",
            "steps": [
                "Navigate to the feature under test.",
                "Provide boundary-value input (min/max length, zero, empty, special characters, concurrent access, or timing edge as applicable).",
                "Observe system behavior at the boundary.",
            ],
            "expected_result": "System handles the boundary condition without error, data loss, or undefined behavior.",
        })

    # A few cross-cutting cases every serious QA suite includes
    cases.extend([
        {
            "title": "Cross-browser: Feature works on Chrome, Firefox, Safari, Edge (latest 2 versions)",
            "category": "Positive",
            "priority": "Medium",
            "preconditions": "Access to BrowserStack/Sauce Labs or local browser installs.",
            "steps": ["Execute the core happy-path flow on each target browser."],
            "expected_result": "Consistent behavior and layout across all supported browsers.",
        },
        {
            "title": "Accessibility: Feature is fully operable via keyboard only",
            "category": "Edge",
            "priority": "Medium",
            "preconditions": "Screen reader / keyboard-only testing environment.",
            "steps": ["Tab through all interactive elements.", "Trigger primary action using only Enter/Space."],
            "expected_result": "All controls reachable and operable without a mouse; focus order is logical.",
        },
        {
            "title": "Security: Session/token expiry is enforced correctly",
            "category": "Edge",
            "priority": "Critical",
            "preconditions": "Valid authenticated session.",
            "steps": ["Remain idle beyond the configured session timeout.", "Attempt an authenticated action."],
            "expected_result": "User is logged out / re-prompted for authentication; no stale session is honored.",
        },
        {
            "title": "Performance: Response within acceptable SLA under normal load",
            "category": "Positive",
            "priority": "High",
            "preconditions": "Baseline performance environment.",
            "steps": ["Execute the core action.", "Measure response time."],
            "expected_result": "Response completes within the SLA defined in the PRD (e.g., 2 seconds).",
        },
    ])

    return cases


def to_markdown(cases: List[Dict]) -> str:
    lines = ["# Generated Test Cases\n"]
    for i, tc in enumerate(cases, start=1):
        lines.append(f"## {i}. {tc['title']}")
        lines.append(f"- **Category:** {tc.get('category', '')}")
        lines.append(f"- **Priority:** {tc.get('priority', '')}")
        lines.append(f"- **Preconditions:** {tc.get('preconditions', '')}")
        lines.append("- **Steps:**")
        for step in tc.get("steps", []):
            lines.append(f"  1. {step}")
        lines.append(f"- **Expected Result:** {tc.get('expected_result', '')}\n")
    return "\n".join(lines)

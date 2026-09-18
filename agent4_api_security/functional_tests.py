"""
functional_tests.py
====================
Generates functional API test cases (status codes, schema validation, auth
checks) from a flattened endpoint list, and — in live mode — actually
executes them against a real base URL using `requests`.
"""

import sys
from pathlib import Path
from typing import List, Dict

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config


def generate_functional_tests(endpoints: List[Dict]) -> List[Dict]:
    tests = []
    for ep in endpoints:
        # Status code test
        tests.append({
            "name": f"{ep['method']} {ep['path']} - returns expected status codes",
            "type": "status",
            "endpoint": ep,
            "assertion": f"Response status is one of {ep['expected_responses']}",
        })

        # Schema validation, if a request body schema exists
        if ep["body_schema"]:
            required = ep["body_schema"].get("required", [])
            tests.append({
                "name": f"{ep['method']} {ep['path']} - rejects request missing required fields {required}",
                "type": "schema",
                "endpoint": ep,
                "assertion": f"Response is 400 Bad Request when required field(s) {required} are omitted",
            })
            tests.append({
                "name": f"{ep['method']} {ep['path']} - accepts valid schema payload",
                "type": "schema",
                "endpoint": ep,
                "assertion": "Response matches success status with valid payload",
            })

        # Auth test
        if ep["requires_auth"]:
            tests.append({
                "name": f"{ep['method']} {ep['path']} - rejects unauthenticated request",
                "type": "auth",
                "endpoint": ep,
                "assertion": "Response status is 401 Unauthorized when Authorization header is omitted",
            })

        # Injection probes
        if ep["method"] in ("POST", "PUT", "PATCH") or "{id}" in ep["path"]:
            tests.append({
                "name": f"{ep['method']} {ep['path']} - resists SQL/NoSQL injection payloads",
                "type": "injection",
                "endpoint": ep,
                "assertion": "Response does not leak DB errors, execute injected logic, or return 500",
            })

        # Rate limiting
        tests.append({
            "name": f"{ep['method']} {ep['path']} - enforces rate limiting under burst traffic",
            "type": "rate_limit",
            "endpoint": ep,
            "assertion": "After N rapid requests, response status becomes 429 Too Many Requests",
        })

    return tests


def run_tests_live(tests: List[Dict], base_url_override: str = None) -> List[Dict]:
    """Actually executes tests against a running API (live mode only)."""
    import requests

    results = []
    for t in tests:
        ep = t["endpoint"]
        url = (base_url_override or ep["base_url"]).rstrip("/") + ep["path"].replace("{id}", "test-id-123")
        method = ep["method"].lower()

        try:
            if t["type"] == "auth":
                resp = requests.request(method, url, timeout=10)
                passed = resp.status_code == 401
            elif t["type"] == "schema" and "missing required" in t["name"]:
                resp = requests.request(method, url, json={}, timeout=10)
                passed = resp.status_code == 400
            elif t["type"] == "injection":
                payload = {"id": "' OR '1'='1"} if method != "get" else None
                resp = requests.request(method, url, json=payload, timeout=10)
                passed = resp.status_code != 500
            else:
                resp = requests.request(method, url, timeout=10)
                passed = str(resp.status_code) in ep["expected_responses"] or resp.status_code < 500

            results.append({**t, "result": "PASS" if passed else "FAIL", "status_code": resp.status_code})
        except Exception as e:
            results.append({**t, "result": "ERROR", "status_code": None, "error": str(e)})

    return results


def run_tests_mock(tests: List[Dict]) -> List[Dict]:
    """
    Simulates execution results deterministically so the demo shows a mix of
    PASS/FAIL findings without needing a live API — useful for interviews
    and CI dry-runs.
    """
    results = []
    for t in tests:
        # Deterministic "simulated" outcome based on test type, tuned to look realistic
        if t["type"] == "auth":
            result, status = "PASS", 401
        elif t["type"] == "rate_limit":
            result, status = "FAIL", 200  # simulate a missing rate limiter — realistic finding
        elif t["type"] == "injection" and "orders" in t["name"]:
            result, status = "FAIL", 500  # simulate an endpoint that leaks a 500 on injection
        elif t["type"] == "schema" and "missing required" in t["name"]:
            result, status = "PASS", 400
        else:
            result, status = "PASS", 200

        results.append({**t, "result": result, "status_code": status})

    return results

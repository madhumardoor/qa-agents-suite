"""
Agent 4: API Test & Security Agent
=====================================
Takes an OpenAPI/Swagger spec URL, auto-generates functional tests (status
codes, schema validation, auth checks, injection probes, rate limiting) AND
runs an OWASP ZAP security scan, then produces one combined report. Designed
to run on a schedule (see scheduler.py / GitHub Actions example in README).

USAGE
-----
  python main.py --swagger http://your-api.com/swagger.json --target http://your-api.com
  python main.py                              # uses bundled sample spec, mock mode
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config
from spec_loader import load_spec, flatten_endpoints
from functional_tests import generate_functional_tests, run_tests_mock, run_tests_live
from zap_client import run_scan

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="API Test & Security Agent")
    parser.add_argument("--swagger", help="URL or local path to OpenAPI/Swagger spec")
    parser.add_argument("--target", help="Base URL of the running API to test/scan (live mode)")
    args = parser.parse_args()

    print(f"[main] Running in {config.mode.upper()} mode.\n")

    spec = load_spec(args.swagger)
    endpoints = flatten_endpoints(spec)
    print(f"[main] Parsed {len(endpoints)} endpoints from spec.\n")

    tests = generate_functional_tests(endpoints)
    print(f"[main] Generated {len(tests)} functional test cases.\n")

    target_url = args.target or spec.get("servers", [{}])[0].get("url", "http://localhost")
    if config.is_live and args.target:
        results = run_tests_live(tests, base_url_override=target_url)
    else:
        results = run_tests_mock(tests)

    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = sum(1 for r in results if r["result"] == "FAIL")
    errored = sum(1 for r in results if r["result"] == "ERROR")
    print(f"[main] Functional test results: {passed} PASS, {failed} FAIL, {errored} ERROR\n")

    print("[main] Running OWASP ZAP security scan...\n")
    findings = run_scan(target_url)
    risk_counts = {}
    for f in findings:
        risk_counts[f["risk"]] = risk_counts.get(f["risk"], 0) + 1
    print(f"[main] Security scan findings by risk: {risk_counts}\n")

    report = {
        "target_url": target_url,
        "functional_summary": {"pass": passed, "fail": failed, "error": errored, "total": len(results)},
        "functional_results": results,
        "security_findings": findings,
    }

    json_path = OUTPUT_DIR / "api_security_report.json"
    json_path.write_text(json.dumps(report, indent=2))
    print(f"[main] Full JSON report saved to: {json_path}")

    md_path = OUTPUT_DIR / "api_security_report.md"
    md_path.write_text(_to_markdown(report), encoding="utf-8")
    print(f"[main] Markdown report saved to: {md_path}")

    print("\n[main] Done. Shows you know API + Security.")


def _to_markdown(report: dict) -> str:
    lines = [f"# API Test & Security Report\n\n**Target:** {report['target_url']}\n"]
    s = report["functional_summary"]
    lines.append(f"## Functional Test Summary\n- Total: {s['total']}\n- Pass: {s['pass']}\n- Fail: {s['fail']}\n- Error: {s['error']}\n")

    lines.append("## Functional Test Results\n")
    for r in report["functional_results"]:
        icon = "✅" if r["result"] == "PASS" else "❌" if r["result"] == "FAIL" else "⚠️"
        lines.append(f"- {icon} **{r['name']}** — `{r['result']}` (status: {r.get('status_code')})")

    lines.append("\n## Security Findings (OWASP ZAP)\n")
    risk_order = {"High": 0, "Medium": 1, "Low": 2, "Informational": 3}
    for f in sorted(report["security_findings"], key=lambda x: risk_order.get(x["risk"], 4)):
        lines.append(f"### [{f['risk']}] {f['name']}")
        lines.append(f"- **URL:** {f['url']}")
        lines.append(f"- **Description:** {f['description']}")
        lines.append(f"- **Solution:** {f['solution']}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    main()

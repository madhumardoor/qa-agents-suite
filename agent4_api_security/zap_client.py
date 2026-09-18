"""
zap_client.py
==============
Drives an OWASP ZAP instance's REST API to run an active security scan
against the API's base URL (live mode — requires a running ZAP daemon,
e.g. `docker run -p 8080:8080 zaproxy/zap-stable zap.sh -daemon
-host 0.0.0.0 -port 8080 -config api.disablekey=true`).

In mock mode, returns a realistic canned set of findings modeled on ZAP's
actual alert taxonomy (risk levels: High/Medium/Low/Informational), so the
report format is identical either way.
"""

import sys
import time
from pathlib import Path
from typing import List, Dict

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config


def run_scan(target_url: str) -> List[Dict]:
    use_live = config.require_or_warn(config.zap_api_url, "ZAP_API_URL") if config.is_live else False

    if use_live:
        return _run_live_scan(target_url)

    print("[zap_client] MOCK MODE: returning simulated ZAP findings (no ZAP daemon required).")
    return _mock_findings(target_url)


def _run_live_scan(target_url: str) -> List[Dict]:
    import requests

    base = config.zap_api_url.rstrip("/")
    params = {"url": target_url, "apikey": config.zap_api_key}

    # 1. Spider the target
    spider_resp = requests.get(f"{base}/JSON/spider/action/scan/", params=params, timeout=30)
    spider_resp.raise_for_status()
    scan_id = spider_resp.json()["scan"]

    while True:
        status = requests.get(f"{base}/JSON/spider/view/status/", params={"scanId": scan_id, "apikey": config.zap_api_key}, timeout=15).json()
        if int(status["status"]) >= 100:
            break
        time.sleep(2)

    # 2. Active scan
    ascan_resp = requests.get(f"{base}/JSON/ascan/action/scan/", params=params, timeout=30)
    ascan_resp.raise_for_status()
    ascan_id = ascan_resp.json()["scan"]

    while True:
        status = requests.get(f"{base}/JSON/ascan/view/status/", params={"scanId": ascan_id, "apikey": config.zap_api_key}, timeout=15).json()
        if int(status["status"]) >= 100:
            break
        time.sleep(5)

    # 3. Retrieve alerts
    alerts_resp = requests.get(f"{base}/JSON/core/view/alerts/", params={"baseurl": target_url, "apikey": config.zap_api_key}, timeout=30)
    alerts_resp.raise_for_status()
    alerts = alerts_resp.json().get("alerts", [])

    return [
        {
            "risk": a.get("risk"),
            "name": a.get("alert"),
            "description": a.get("description", "")[:300],
            "url": a.get("url"),
            "solution": a.get("solution", "")[:300],
        }
        for a in alerts
    ]


def _mock_findings(target_url: str) -> List[Dict]:
    return [
        {
            "risk": "Medium",
            "name": "Missing Anti-CSRF Tokens",
            "description": "The response does not include anti-CSRF tokens on state-changing requests (POST /orders, POST /users).",
            "url": f"{target_url}/orders",
            "solution": "Implement anti-CSRF tokens (e.g., synchronizer token pattern) on all state-changing endpoints.",
        },
        {
            "risk": "Medium",
            "name": "Missing Rate Limiting",
            "description": "No rate-limiting headers or 429 responses observed under burst traffic on /login, allowing brute-force attempts.",
            "url": f"{target_url}/login",
            "solution": "Implement rate limiting (e.g., token bucket) and account lockout after repeated failed attempts.",
        },
        {
            "risk": "Low",
            "name": "X-Content-Type-Options Header Missing",
            "description": "Response does not set X-Content-Type-Options: nosniff, allowing MIME-sniffing attacks in some browsers.",
            "url": target_url,
            "solution": "Add 'X-Content-Type-Options: nosniff' to all API responses.",
        },
        {
            "risk": "High",
            "name": "Possible SQL Injection",
            "description": "Injecting a single-quote payload into the 'id' path parameter on DELETE /users/{id} returned a 500 error consistent with an unhandled DB exception.",
            "url": f"{target_url}/users/{{id}}",
            "solution": "Use parameterized queries / ORM bindings; never interpolate user input directly into SQL statements. Return generic 4xx errors, never raw DB stack traces.",
        },
        {
            "risk": "Informational",
            "name": "Server Header Discloses Version Information",
            "description": "Server response header reveals backend framework/version, aiding attacker reconnaissance.",
            "url": target_url,
            "solution": "Suppress or genericize the Server header in production.",
        },
    ]

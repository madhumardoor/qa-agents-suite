"""
jenkins_client.py
==================
Fetches the console log of a failed Jenkins build via the Jenkins REST API
(live mode) or returns a bundled sample log (mock mode).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config

MOCK_LOG_PATH = Path(__file__).resolve().parent / "mock_data" / "sample_jenkins_log.txt"


def fetch_console_log(job_name: str, build_number: str = "lastFailedBuild") -> str:
    use_live = config.require_or_warn(config.jenkins_api_token, "JENKINS_API_TOKEN") and \
        config.require_or_warn(config.jenkins_base_url, "JENKINS_BASE_URL")

    if use_live:
        import requests

        url = f"{config.jenkins_base_url.rstrip('/')}/job/{job_name}/{build_number}/consoleText"
        resp = requests.get(url, auth=(config.jenkins_user, config.jenkins_api_token), timeout=20)
        resp.raise_for_status()
        return resp.text

    print(f"[jenkins_client] MOCK MODE: returning bundled sample log instead of fetching '{job_name}#{build_number}'.")
    return MOCK_LOG_PATH.read_text()


def get_build_metadata(job_name: str, build_number: str = "lastFailedBuild") -> dict:
    use_live = config.require_or_warn(config.jenkins_api_token, "JENKINS_API_TOKEN") and \
        config.require_or_warn(config.jenkins_base_url, "JENKINS_BASE_URL")

    if use_live:
        import requests

        url = f"{config.jenkins_base_url.rstrip('/')}/job/{job_name}/{build_number}/api/json"
        resp = requests.get(url, auth=(config.jenkins_user, config.jenkins_api_token), timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return {"number": data.get("number"), "url": data.get("url"), "result": data.get("result")}

    return {"number": 482, "url": f"http://mock-jenkins/job/{job_name}/482/", "result": "FAILURE"}

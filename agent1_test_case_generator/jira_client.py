"""
jira_client.py
===============
Fetches a Jira ticket's description (PRD/user story) either from the real
Jira REST API (live mode) or from a local sample file (mock mode).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config

MOCK_PRD_PATH = Path(__file__).resolve().parent / "mock_data" / "sample_prd.txt"


def fetch_ticket_text(ticket_key: str) -> str:
    """Returns the plain-text description of a Jira ticket."""
    use_live = config.require_or_warn(config.jira_api_token, "JIRA_API_TOKEN") and \
        config.require_or_warn(config.jira_base_url, "JIRA_BASE_URL")

    if use_live:
        import requests
        from requests.auth import HTTPBasicAuth

        url = f"{config.jira_base_url.rstrip('/')}/rest/api/3/issue/{ticket_key}"
        resp = requests.get(
            url,
            auth=HTTPBasicAuth(config.jira_email, config.jira_api_token),
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # Jira Cloud stores description as Atlassian Document Format (ADF).
        # Flatten it into plain text.
        adf = data["fields"].get("description") or {}
        return _flatten_adf(adf) or data["fields"].get("summary", "")

    print(f"[jira_client] MOCK MODE: returning local sample PRD instead of fetching '{ticket_key}' from Jira.")
    return MOCK_PRD_PATH.read_text()


def _flatten_adf(node) -> str:
    """Recursively extracts plain text from Atlassian Document Format JSON."""
    if not isinstance(node, dict):
        return ""
    text = node.get("text", "")
    children = node.get("content", [])
    child_text = "\n".join(_flatten_adf(c) for c in children)
    return (text + "\n" + child_text).strip()


def create_ticket_link_comment(ticket_key: str, message: str) -> None:
    """Optional: post a comment back on the ticket once test cases are generated."""
    use_live = config.require_or_warn(config.jira_api_token, "JIRA_API_TOKEN")
    if not use_live:
        print(f"[jira_client] MOCK MODE: would comment on {ticket_key}: {message[:80]}...")
        return

    import requests
    from requests.auth import HTTPBasicAuth

    url = f"{config.jira_base_url.rstrip('/')}/rest/api/3/issue/{ticket_key}/comment"
    body = {"body": {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": message}]}
    ]}}
    resp = requests.post(
        url, json=body,
        auth=HTTPBasicAuth(config.jira_email, config.jira_api_token),
        timeout=15,
    )
    resp.raise_for_status()

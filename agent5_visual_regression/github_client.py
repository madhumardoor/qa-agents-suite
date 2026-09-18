"""
github_client.py
=================
Posts the visual regression + accessibility report as a comment on a GitHub
PR (live mode) or writes it to a local markdown file styled exactly like
the PR comment that would be posted (mock mode).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def post_pr_comment(pr_number: str, body: str) -> None:
    use_live = config.require_or_warn(config.github_token, "GITHUB_TOKEN") and \
        config.require_or_warn(config.github_repo, "GITHUB_REPO")

    if use_live:
        import requests

        url = f"https://api.github.com/repos/{config.github_repo}/issues/{pr_number}/comments"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {config.github_token}", "Accept": "application/vnd.github+json"},
            json={"body": body},
            timeout=15,
        )
        resp.raise_for_status()
        print(f"[github_client] Posted comment to PR #{pr_number}.")
        return

    out_path = OUTPUT_DIR / "pr_comment_preview.md"
    out_path.write_text(body, encoding="utf-8")
    print(f"[github_client] MOCK MODE: PR comment preview written to {out_path}")

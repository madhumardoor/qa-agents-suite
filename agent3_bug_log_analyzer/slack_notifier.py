"""
slack_notifier.py
==================
Posts a formatted failure summary to Slack (live mode) or prints it to the
console / writes a local text file styled like a Slack message (mock mode).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def post_message(text: str) -> None:
    use_live = config.require_or_warn(config.slack_bot_token, "SLACK_BOT_TOKEN")

    if use_live:
        import requests

        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {config.slack_bot_token}"},
            json={"channel": config.slack_channel, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        if not resp.json().get("ok"):
            print(f"[slack_notifier] Slack API error: {resp.json()}")
        return

    out_path = OUTPUT_DIR / "slack_message_preview.txt"
    out_path.write_text(text)
    print(f"[slack_notifier] MOCK MODE: message written to {out_path}\n")
    print("----- Slack message preview -----")
    print(text)
    print("----------------------------------")

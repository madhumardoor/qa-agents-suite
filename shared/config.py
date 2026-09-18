"""
shared/config.py
=================
Central configuration loader used by all 5 agents.

MODE SWITCHING
--------------
Every agent supports two modes, controlled by the MODE env var (or --mode CLI flag):

  MODE=mock   -> No API keys required. Agents use local sample data / fake responses
                 from the `mock_data/` folder inside each agent. Perfect for demos,
                 interviews, and CI smoke tests.

  MODE=live   -> Agents call real services: OpenAI/Claude, Jira, Jenkins, TestRail,
                 OWASP ZAP, Applitools/Percy, GitHub. Requires a filled-in .env file.

Copy `.env.example` to `.env` and fill in only the keys for the services you
actually want to hit. Anything left blank will cause that specific integration
to fall back to mock behavior automatically, even in live mode, and a warning
is printed.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


@dataclass
class Config:
    mode: str = field(default_factory=lambda: _get("MODE", "mock").lower())

    # LLM
    llm_provider: str = field(default_factory=lambda: _get("LLM_PROVIDER", "anthropic"))
    anthropic_api_key: str = field(default_factory=lambda: _get("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _get("OPENAI_API_KEY"))
    llm_model: str = field(default_factory=lambda: _get("LLM_MODEL", "claude-sonnet-4-6"))

    # Jira
    jira_base_url: str = field(default_factory=lambda: _get("JIRA_BASE_URL"))
    jira_email: str = field(default_factory=lambda: _get("JIRA_EMAIL"))
    jira_api_token: str = field(default_factory=lambda: _get("JIRA_API_TOKEN"))
    jira_project_key: str = field(default_factory=lambda: _get("JIRA_PROJECT_KEY", "QA"))

    # TestRail
    testrail_base_url: str = field(default_factory=lambda: _get("TESTRAIL_BASE_URL"))
    testrail_email: str = field(default_factory=lambda: _get("TESTRAIL_EMAIL"))
    testrail_api_key: str = field(default_factory=lambda: _get("TESTRAIL_API_KEY"))
    testrail_project_id: str = field(default_factory=lambda: _get("TESTRAIL_PROJECT_ID"))

    # Jenkins
    jenkins_base_url: str = field(default_factory=lambda: _get("JENKINS_BASE_URL"))
    jenkins_user: str = field(default_factory=lambda: _get("JENKINS_USER"))
    jenkins_api_token: str = field(default_factory=lambda: _get("JENKINS_API_TOKEN"))

    # Slack
    slack_bot_token: str = field(default_factory=lambda: _get("SLACK_BOT_TOKEN"))
    slack_channel: str = field(default_factory=lambda: _get("SLACK_CHANNEL", "#qa-alerts"))

    # OWASP ZAP
    zap_api_url: str = field(default_factory=lambda: _get("ZAP_API_URL", "http://localhost:8080"))
    zap_api_key: str = field(default_factory=lambda: _get("ZAP_API_KEY"))

    # Applitools / Percy
    applitools_api_key: str = field(default_factory=lambda: _get("APPLITOOLS_API_KEY"))
    percy_token: str = field(default_factory=lambda: _get("PERCY_TOKEN"))

    # GitHub (for PR comments)
    github_token: str = field(default_factory=lambda: _get("GITHUB_TOKEN"))
    github_repo: str = field(default_factory=lambda: _get("GITHUB_REPO"))

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    def require_or_warn(self, value: str, name: str) -> bool:
        """Returns True if the value is usable; prints a warning and returns False otherwise."""
        if self.is_live and value:
            return True
        if self.is_live and not value:
            print(f"[config] WARNING: {name} not set in .env — falling back to mock for this integration.")
        return False


config = Config()

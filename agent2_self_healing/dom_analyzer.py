"""
dom_analyzer.py
================
Parses DOM HTML into a list of candidate elements and scores them for
similarity against a broken locator's last-known attributes.

Similarity uses a weighted blend of:
  - tag match
  - attribute name overlap (id/name/class/data-testid/placeholder/type)
  - fuzzy text/string similarity on those attribute VALUES
  - role/type match (input type, button, etc.)

This is a real, working algorithm — no LLM required — which is what makes
self-healing fast enough to run on every test failure. GPT Vision (optional,
live mode) is used only as a second-opinion tiebreaker when confidence is low.
"""

import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config


@dataclass
class ElementCandidate:
    tag: str
    attrs: dict
    text: str
    xpath: str

    def as_locator_dict(self):
        return {
            "tag": self.tag,
            "id": self.attrs.get("id"),
            "name": self.attrs.get("name"),
            "class": self.attrs.get("class"),
            "data_testid": self.attrs.get("data-testid"),
            "placeholder": self.attrs.get("placeholder"),
            "type": self.attrs.get("type"),
            "text": self.text,
            "xpath": self.xpath,
        }


def parse_dom(html: str) -> List[ElementCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for tag in soup.find_all(["input", "button", "a", "select", "textarea"]):
        candidates.append(
            ElementCandidate(
                tag=tag.name,
                attrs={k: (" ".join(v) if isinstance(v, list) else v) for k, v in tag.attrs.items()},
                text=tag.get_text(strip=True),
                xpath=_build_simple_xpath(tag),
            )
        )
    return candidates


def _build_simple_xpath(tag) -> str:
    parts = [tag.name]
    if tag.get("id"):
        return f"//{tag.name}[@id='{tag.get('id')}']"
    if tag.get("data-testid"):
        return f"//{tag.name}[@data-testid='{tag.get('data-testid')}']"
    return "//" + "/".join(parts)


def _sim(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def score_candidate(broken_locator: dict, candidate: ElementCandidate) -> float:
    """
    broken_locator: dict with keys like id/name/class/placeholder/type/tag/text
    (the last known-good attributes of the element that just failed to be found)
    """
    score = 0.0
    weights = {
        "tag": 0.15,
        "type": 0.15,
        "id": 0.15,
        "name": 0.15,
        "placeholder": 0.15,
        "class": 0.10,
        "text": 0.15,
    }

    if broken_locator.get("tag") == candidate.tag:
        score += weights["tag"]

    if broken_locator.get("type") and broken_locator.get("type") == candidate.attrs.get("type"):
        score += weights["type"]

    score += weights["id"] * _sim(broken_locator.get("id"), candidate.attrs.get("id"))
    score += weights["name"] * _sim(broken_locator.get("name"), candidate.attrs.get("name"))
    score += weights["placeholder"] * _sim(broken_locator.get("placeholder"), candidate.attrs.get("placeholder"))
    score += weights["class"] * _sim(broken_locator.get("class"), candidate.attrs.get("class"))
    score += weights["text"] * _sim(broken_locator.get("text"), candidate.text)

    # data-testid is a strong modern signal — bonus if present and similar
    if candidate.attrs.get("data-testid"):
        score += 0.10 * _sim(broken_locator.get("name") or broken_locator.get("id"), candidate.attrs.get("data-testid"))

    return round(min(score, 1.0), 4)


def find_best_match(broken_locator: dict, new_dom_html: str, min_confidence: float = 0.35):
    """Returns (best_candidate, score) or (None, 0) if nothing clears the confidence bar."""
    candidates = parse_dom(new_dom_html)
    scored = [(c, score_candidate(broken_locator, c)) for c in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    if not scored or scored[0][1] < min_confidence:
        return None, 0.0
    return scored[0]

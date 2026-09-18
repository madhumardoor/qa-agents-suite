"""
a11y_checker.py
================
Runs accessibility checks against HTML. In live mode this would be driven
by axe-core via Playwright (see `run_axe_live` — requires
`playwright install chromium` and the axe-core JS bundle). In mock mode, it
parses static HTML with BeautifulSoup and applies the same rule categories
axe-core checks, including REAL WCAG contrast-ratio math (not simulated).
"""

import re
import sys
from pathlib import Path
from typing import List, Dict

from bs4 import BeautifulSoup

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config


def check_html(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    violations = []

    # Rule: img must have alt text (or explicit empty alt for decorative images)
    for img in soup.find_all("img"):
        if "alt" not in img.attrs:
            violations.append({
                "rule": "image-alt",
                "impact": "critical",
                "description": f"<img src='{img.get('src')}'> is missing an 'alt' attribute.",
                "wcag": "WCAG 2.1 - 1.1.1 Non-text Content",
                "fix": "Add a descriptive alt attribute, or alt=\"\" if the image is purely decorative.",
            })

    # Rule: form inputs should have an associated label
    for inp in soup.find_all("input"):
        input_id = inp.get("id")
        has_label = bool(input_id and soup.find("label", attrs={"for": input_id}))
        has_wrapping_label = inp.find_parent("label") is not None
        if not (has_label or has_wrapping_label):
            violations.append({
                "rule": "label",
                "impact": "critical",
                "description": f"<input name='{inp.get('name')}'> has no associated <label> (missing 'for' attribute linkage).",
                "wcag": "WCAG 2.1 - 1.3.1 Info and Relationships / 4.1.2 Name, Role, Value",
                "fix": f"Add <label for=\"{input_id or 'INPUT_ID'}\">...</label> or wrap the input in a <label> element.",
            })

    # Rule: clickable divs should be real buttons / have role+tabindex
    for div in soup.find_all("div", onclick=True):
        if not div.get("role") or not div.get("tabindex"):
            violations.append({
                "rule": "button-name",
                "impact": "serious",
                "description": "A <div onclick=...> is used as a clickable control without role='button' or keyboard support (tabindex).",
                "wcag": "WCAG 2.1 - 4.1.2 Name, Role, Value / 2.1.1 Keyboard",
                "fix": "Use a native <button> element, or add role=\"button\" tabindex=\"0\" and a keydown handler for Enter/Space.",
            })

    # Rule: inline color-contrast check on elements with explicit style colors
    for el in soup.find_all(style=True):
        style = el["style"]
        fg = _extract_color(style, "color")
        bg = _extract_color(style, "background") or _extract_color(style, "background-color")
        if fg and bg:
            ratio = contrast_ratio(fg, bg)
            if ratio < 4.5:
                violations.append({
                    "rule": "color-contrast",
                    "impact": "serious",
                    "description": f"Text color {fg} on background {bg} has a contrast ratio of {ratio}:1, below the WCAG AA minimum of 4.5:1.",
                    "wcag": "WCAG 2.1 - 1.4.3 Contrast (Minimum)",
                    "fix": f"Increase contrast to at least 4.5:1 (current: {ratio}:1). Consider darkening the text or lightening/darkening the background.",
                })
        elif fg and not bg:
            # Assume white page background if not explicitly set (common case)
            ratio = contrast_ratio(fg, "#ffffff")
            if ratio < 4.5:
                violations.append({
                    "rule": "color-contrast",
                    "impact": "serious",
                    "description": f"Text color {fg} on assumed white background has a contrast ratio of {ratio}:1, below WCAG AA minimum of 4.5:1.",
                    "wcag": "WCAG 2.1 - 1.4.3 Contrast (Minimum)",
                    "fix": f"Increase contrast to at least 4.5:1 (current: {ratio}:1).",
                })

    return violations


def _extract_color(style: str, prop: str) -> str:
    match = re.search(rf"{prop}\s*:\s*(#[0-9a-fA-F]{{3,6}}|rgb\([^)]+\))", style)
    return match.group(1) if match else None


def _hex_to_rgb(color: str) -> tuple:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(rgb: tuple) -> float:
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(color1: str, color2: str) -> float:
    """Real WCAG 2.1 contrast ratio calculation. Returns a value between 1 and 21."""
    if color1.startswith("rgb"):
        rgb1 = tuple(int(x) for x in re.findall(r"\d+", color1)[:3])
    else:
        rgb1 = _hex_to_rgb(color1)
    if color2.startswith("rgb"):
        rgb2 = tuple(int(x) for x in re.findall(r"\d+", color2)[:3])
    else:
        rgb2 = _hex_to_rgb(color2)

    l1, l2 = _relative_luminance(rgb1), _relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def run_axe_live(page) -> List[Dict]:
    """
    Live mode: inject and run the real axe-core library via Playwright.
    Requires axe-core to be available (npm package or CDN injection).
    """
    axe_source = Path(__file__).resolve().parent / "axe.min.js"
    if not axe_source.exists():
        raise RuntimeError(
            "axe.min.js not found. Download it from https://github.com/dequelabs/axe-core/releases "
            "and place it in agent5_visual_regression/ to enable live axe-core scanning."
        )
    page.add_script_tag(path=str(axe_source))
    results = page.evaluate("async () => await axe.run()")
    return [
        {
            "rule": v["id"],
            "impact": v.get("impact", "unknown"),
            "description": v["description"],
            "wcag": ", ".join(v.get("tags", [])),
            "fix": v.get("help", ""),
        }
        for v in results.get("violations", [])
    ]

"""
visual_diff.py
===============
Real pixel-level image comparison between a baseline and candidate
screenshot. This works identically in mock and live mode — the only thing
that differs is where the screenshots come from (bundled PNGs vs. a live
Playwright screenshot capture in screenshot_capture.py).

Produces:
  - a diff heatmap image (red = changed pixels)
  - percentage of pixels changed
  - bounding boxes of the largest changed regions (so the report can say
    "layout shift detected near coordinates X,Y" instead of just "5% diff")
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple

from PIL import Image, ImageChops, ImageDraw

sys.path.append(str(Path(__file__).resolve().parent.parent))

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def compare_images(baseline_path: str, candidate_path: str, diff_threshold: int = 30) -> Dict:
    baseline = Image.open(baseline_path).convert("RGB")
    candidate = Image.open(candidate_path).convert("RGB")

    if baseline.size != candidate.size:
        candidate = candidate.resize(baseline.size)

    diff = ImageChops.difference(baseline, candidate)
    diff_gray = diff.convert("L")

    bbox = diff_gray.point(lambda p: 255 if p > diff_threshold else 0).getbbox()

    total_pixels = baseline.size[0] * baseline.size[1]
    changed_pixels = sum(1 for p in diff_gray.point(lambda x: 255 if x > diff_threshold else 0).getdata() if p == 255)
    pct_changed = round((changed_pixels / total_pixels) * 100, 2)

    # Build a visual heatmap: candidate image with changed regions highlighted in red
    heatmap = candidate.copy()
    draw = ImageDraw.Draw(heatmap)
    mask = diff_gray.point(lambda p: 255 if p > diff_threshold else 0)
    red_overlay = Image.new("RGB", heatmap.size, (255, 0, 0))
    heatmap = Image.composite(red_overlay, heatmap, mask)

    if bbox:
        draw = ImageDraw.Draw(heatmap)
        draw.rectangle(bbox, outline="yellow", width=3)

    heatmap_path = OUTPUT_DIR / "diff_heatmap.png"
    heatmap.save(heatmap_path)

    return {
        "pct_pixels_changed": pct_changed,
        "changed_region_bbox": bbox,
        "heatmap_path": str(heatmap_path),
        "verdict": _verdict(pct_changed),
    }


def _verdict(pct_changed: float) -> str:
    if pct_changed < 0.1:
        return "No visual regression detected."
    if pct_changed < 2.0:
        return "Minor visual difference detected — likely anti-aliasing/rendering noise, review recommended."
    return "Significant visual regression detected — layout or styling has changed."

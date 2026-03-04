"""
Slide builder — loads the real DOMO_BRAND FORMAT TEMPLATE and populates
placeholders. The AI picks layout_index per slide from the full 309-layout
catalog, so this builder is generic — it works with ANY layout.
"""

import io
from pathlib import Path
from typing import Dict, Any, List, Optional

from pptx import Presentation
from pptx.oxml.ns import qn

from config import TEMPLATES_DIR

TEMPLATE_PATH = TEMPLATES_DIR / "domo_brand_template.pptx"


def build_presentation(
    slides: List[Dict[str, Any]],
    image_map: Optional[Dict[int, str]] = None,
    title: str = "Untitled",
    **kwargs,
) -> bytes:
    """
    Build a .pptx by loading the real Domo template.
    Each slide dict must have 'layout_index' (0-308) picked by the AI.
    """
    image_map = image_map or {}

    prs = Presentation(str(TEMPLATE_PATH))
    _clear_slides(prs)

    total_layouts = len(prs.slide_layouts)

    for sd in slides:
        layout_idx = sd.get("layout_index", 12)
        if layout_idx < 0 or layout_idx >= total_layouts:
            layout_idx = 12  # Fallback to basic bullets

        layout = prs.slide_layouts[layout_idx]
        slide = prs.slides.add_slide(layout)

        # Get available placeholders
        phs = {ph.placeholder_format.idx: ph for ph in slide.placeholders}

        # PRIMARY: Use placeholder_map if AI provided it
        ph_map = sd.get("placeholder_map", {})
        if ph_map:
            for idx_str, content in ph_map.items():
                idx = int(idx_str)
                if idx in phs and content:
                    _set_placeholder(phs[idx], content)

        # FALLBACK: Use structured fields to populate common placeholders
        _populate_from_fields(phs, sd, image_map.get(sd.get("position", 0)))

        # Speaker notes
        notes = sd.get("speaker_notes", "")
        if notes:
            try:
                slide.notes_slide.notes_text_frame.text = notes
            except Exception:
                pass

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _clear_slides(prs: Presentation):
    """Remove all existing slides from the presentation."""
    sldIdLst = prs.slides._sldIdLst
    while len(sldIdLst):
        rId = sldIdLst[0].get(qn('r:id'))
        if rId:
            prs.part.drop_rel(rId)
        del sldIdLst[0]


def _set_placeholder(ph, content: str):
    """Set a placeholder's content. Handles text and multi-line."""
    if not content:
        return
    if hasattr(ph, 'text_frame'):
        # Check if content has newlines — if so, create multiple paragraphs
        lines = content.split("\n")
        if len(lines) > 1:
            tf = ph.text_frame
            tf.clear()
            for i, line in enumerate(lines):
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.text = line.strip()
        else:
            ph.text_frame.text = content


def _populate_from_fields(phs: Dict, sd: Dict, image_path: Optional[str]):
    """
    Populate placeholders from structured fields as a fallback
    (in case placeholder_map is missing or incomplete).
    Only sets a placeholder if it wasn't already set by placeholder_map.
    """
    ph_map = sd.get("placeholder_map", {})
    already_set = {int(k) for k in ph_map.keys()} if ph_map else set()

    def _try_set(idx, text):
        if idx not in already_set and idx in phs and text:
            _set_placeholder(phs[idx], text)

    # PH0 = Title/headline
    _try_set(0, sd.get("headline", ""))

    # PH1 = Body/subtitle
    body = sd.get("body", "")
    if not body and sd.get("bullets"):
        body = "\n".join(sd["bullets"])
    _try_set(1, body)

    # PH10 = Secondary text / bullet area
    bullets = sd.get("bullets", [])
    if bullets and 10 in phs and 10 not in already_set:
        tf = phs[10].text_frame
        tf.clear()
        for i, bullet in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = bullet

    # PH12 = Body (blue layouts)
    _try_set(12, sd.get("body", ""))

    # PH13 = Description/subtitle
    _try_set(13, sd.get("subheadline", ""))

    # PH14 = Date/notes
    _try_set(14, sd.get("date_line", ""))

    # PH20 = Quote attribution
    _try_set(20, sd.get("quote_attribution", ""))

    # Icons: PH17/18, PH20/21, PH23/24
    points = sd.get("icon_points", [])
    if points:
        if len(points) >= 1:
            _try_set(17, points[0].get("label", ""))
            _try_set(18, points[0].get("description", ""))
        if len(points) >= 2:
            _try_set(20, points[1].get("label", ""))
            _try_set(21, points[1].get("description", ""))
        if len(points) >= 3:
            _try_set(23, points[2].get("label", ""))
            _try_set(24, points[2].get("description", ""))

    # Image placeholders
    if image_path and Path(image_path).exists():
        for img_idx in (11, 10, 15, 13, 19, 22, 25):
            if img_idx in phs and img_idx not in already_set:
                try:
                    phs[img_idx].insert_picture(image_path)
                    break
                except Exception:
                    continue

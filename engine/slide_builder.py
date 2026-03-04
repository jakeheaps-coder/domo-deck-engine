"""
Slide builder — loads the real DOMO_BRAND FORMAT TEMPLATE and populates
its native placeholders. All design (fonts, colors, backgrounds, logos,
shapes) comes from the template — we only inject content.
"""

import io
from pathlib import Path
from typing import Dict, Any, List, Optional

from pptx import Presentation
from pptx.util import Inches
from pptx.oxml.ns import qn

from config import TEMPLATES_DIR
from models.deck_config import DESIGN_STYLES, TEMPLATE_STYLE_MAP

TEMPLATE_PATH = TEMPLATES_DIR / "domo_brand_template.pptx"


def build_presentation(
    slides: List[Dict[str, Any]],
    design_style: str = "executive_blue",
    image_map: Optional[Dict[int, str]] = None,
    title: str = "Untitled",
) -> bytes:
    """
    Build a .pptx by loading the real Domo template and populating placeholders.

    Args:
        slides: List of slide content dicts
        design_style: "executive_blue" | "clean_white" | "gradient"
        image_map: {slide_position: image_path}
        title: Deck title (for metadata)

    Returns:
        .pptx file as bytes
    """
    image_map = image_map or {}
    style = DESIGN_STYLES.get(design_style, DESIGN_STYLES["executive_blue"])

    # Load the template (preserves all masters, themes, fonts, colors)
    prs = Presentation(str(TEMPLATE_PATH))

    # Clear all 1085 example slides — keep only layouts
    _clear_slides(prs)

    # Build each slide using the correct layout
    for sd in slides:
        slide_type = sd.get("slide_type", "bullets")
        position = sd.get("position", 0)
        img = image_map.get(position)

        # Resolve the layout index from the design style
        layout_idx = style.get(slide_type, style.get("bullets", 12))
        layout = prs.slide_layouts[layout_idx]
        slide = prs.slides.add_slide(layout)

        # Populate based on slide type
        _populate_slide(slide, sd, slide_type, layout_idx, img)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _clear_slides(prs: Presentation):
    """Remove all existing slides from the presentation (keep layouts only)."""
    sldIdLst = prs.slides._sldIdLst
    while len(sldIdLst):
        rId = sldIdLst[0].get(qn('r:id'))
        if rId:
            prs.part.drop_rel(rId)
        del sldIdLst[0]


def _populate_slide(slide, data: Dict, slide_type: str, layout_idx: int, image_path: Optional[str]):
    """Populate a slide's placeholders based on its type."""
    phs = {ph.placeholder_format.idx: ph for ph in slide.placeholders}

    if slide_type == "title":
        _populate_title(phs, data)
    elif slide_type == "section":
        _populate_section(phs, data)
    elif slide_type in ("quote",):
        _populate_quote(phs, data, layout_idx)
    elif slide_type == "bullets":
        _populate_bullets(phs, data)
    elif slide_type in ("one_column", "paragraph"):
        _populate_one_column(phs, data)
    elif slide_type in ("two_column", "emphasis_2col"):
        _populate_two_column(phs, data)
    elif slide_type in ("text_image", "large_image", "text_landscape",
                         "phone_mockup", "screen_mockup", "intro_image"):
        _populate_text_image(phs, data, image_path)
    elif slide_type == "emphasis":
        _populate_emphasis(phs, data)
    elif slide_type in ("icons_1", "icons_2", "icons_3",
                         "icons_1_desc", "icons_2_desc", "icons_3_desc"):
        _populate_icons(phs, data, slide_type)
    elif slide_type == "agenda":
        _populate_agenda(phs, data, image_path)
    elif slide_type == "close":
        _populate_close(phs, data)
    else:
        # Fallback: try to populate whatever placeholders exist
        _populate_generic(phs, data)

    # Add speaker notes if provided
    notes = data.get("speaker_notes", "")
    if notes and hasattr(slide, 'notes_slide'):
        try:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = notes
        except Exception:
            pass


# ── Title (layouts 0, 1, 2) ────────────────────────────────────────
# PH0=title, PH13=description, PH14=date/notes

def _populate_title(phs, data):
    _set_ph(phs, 0, data.get("headline", ""))
    _set_ph(phs, 13, data.get("subheadline", ""))
    _set_ph(phs, 14, data.get("body", ""))  # date/notes line


# ── Section (layouts 3, 4, 5) ──────────────────────────────────────
# PH0=title, PH13=description

def _populate_section(phs, data):
    _set_ph(phs, 0, data.get("headline", ""))
    _set_ph(phs, 13, data.get("subheadline", ""))


# ── Quote (layouts 10, 11) ─────────────────────────────────────────
# PH0=quote text, PH20=attribution

def _populate_quote(phs, data, layout_idx):
    quote = data.get("quote", data.get("body", ""))
    # Add smart quotes
    if quote and not quote.startswith("\u201C"):
        quote = f"\u201C{quote}\u201D"
    _set_ph(phs, 0, quote)
    _set_ph(phs, 20, data.get("quote_attribution", ""))


# ── Bullets (layout 12) ────────────────────────────────────────────
# PH0=title, PH10=bullets (multi-paragraph)

def _populate_bullets(phs, data):
    _set_ph(phs, 0, data.get("headline", ""))
    bullets = data.get("bullets", [])
    if bullets and 10 in phs:
        tf = phs[10].text_frame
        tf.clear()
        for i, bullet in enumerate(bullets):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = bullet
            # Inherit formatting from the placeholder's default style
    elif data.get("body") and 10 in phs:
        phs[10].text_frame.text = data["body"]


# ── One Column (layout 13) ─────────────────────────────────────────
# PH0=title, PH1=body

def _populate_one_column(phs, data):
    _set_ph(phs, 0, data.get("headline", ""))
    body = data.get("body", "")
    if not body and data.get("bullets"):
        body = "\n".join(data["bullets"])
    _set_ph(phs, 1, body)


# ── Two Column (layouts 15, 20) ────────────────────────────────────
# PH0=title, PH1=left column, PH10=right column

def _populate_two_column(phs, data):
    _set_ph(phs, 0, data.get("headline", ""))
    bullets = data.get("bullets", [])
    if bullets:
        mid = max(len(bullets) // 2, 1)
        _set_ph(phs, 1, "\n".join(bullets[:mid]))
        _set_ph(phs, 10, "\n".join(bullets[mid:]))
    elif data.get("body"):
        sentences = [s.strip() for s in data["body"].split(". ") if s.strip()]
        mid = max(len(sentences) // 2, 1)
        _set_ph(phs, 1, ". ".join(sentences[:mid]) + ".")
        _set_ph(phs, 10, ". ".join(sentences[mid:]))


# ── Text + Image (layouts 16, 17) ──────────────────────────────────
# PH0=title, PH1=text, PH11=picture

def _populate_text_image(phs, data, image_path):
    _set_ph(phs, 0, data.get("headline", ""))
    body = data.get("body", "")
    if not body and data.get("bullets"):
        body = "\n".join(data["bullets"])
    _set_ph(phs, 1, body)

    if image_path and Path(image_path).exists() and 11 in phs:
        try:
            phs[11].insert_picture(image_path)
        except Exception:
            pass


# ── Emphasis / Blue (layout 18) ────────────────────────────────────
# PH0=title, PH12=body

def _populate_emphasis(phs, data):
    _set_ph(phs, 0, data.get("headline", ""))
    body = data.get("body", "")
    if not body and data.get("bullets"):
        body = "\n".join(f"\u2022 {b}" for b in data["bullets"])
    _set_ph(phs, 12, body)


# ── Icons (layouts 23, 24, 25) ──────────────────────────────────────
# Layout 23 (1 icon): PH0=title, PH17=icon title, PH18=icon text, PH19=icon image
# Layout 24 (2 icons): + PH20=title2, PH21=text2, PH22=image2
# Layout 25 (3 icons): + PH23=title3, PH24=text3, PH25=image3
#   NOTE: Layout 25 ordering is: PH23/24/25=LEFT, PH17/18/19=CENTER, PH20/21/22=RIGHT

def _populate_icons(phs, data, slide_type):
    _set_ph(phs, 0, data.get("headline", ""))
    points = data.get("icon_points", [])
    if not points and data.get("bullets"):
        points = [{"label": b[:30], "description": b} for b in data["bullets"][:3]]

    # icons_1 and icons_1_desc share the same placeholder structure
    if slide_type in ("icons_1", "icons_1_desc") and len(points) >= 1:
        _set_ph(phs, 17, points[0].get("label", ""))
        _set_ph(phs, 18, points[0].get("description", ""))
    elif slide_type in ("icons_2", "icons_2_desc") and len(points) >= 2:
        _set_ph(phs, 17, points[0].get("label", ""))
        _set_ph(phs, 18, points[0].get("description", ""))
        _set_ph(phs, 20, points[1].get("label", ""))
        _set_ph(phs, 21, points[1].get("description", ""))
    elif slide_type in ("icons_3", "icons_3_desc") and len(points) >= 3:
        # Layout 25/28: PH23/24/25=LEFT, PH17/18/19=CENTER, PH20/21/22=RIGHT
        _set_ph(phs, 23, points[0].get("label", ""))
        _set_ph(phs, 24, points[0].get("description", ""))
        _set_ph(phs, 17, points[1].get("label", ""))
        _set_ph(phs, 18, points[1].get("description", ""))
        _set_ph(phs, 20, points[2].get("label", ""))
        _set_ph(phs, 21, points[2].get("description", ""))


# ── Agenda (layout 52) ─────────────────────────────────────────────
# PH0=title, PH1=body, PH13=image

def _populate_agenda(phs, data, image_path):
    _set_ph(phs, 0, data.get("headline", ""))
    body = data.get("body", "")
    if not body and data.get("bullets"):
        body = "\n".join(data["bullets"])
    _set_ph(phs, 1, body)
    if image_path and Path(image_path).exists() and 13 in phs:
        try:
            phs[13].insert_picture(image_path)
        except Exception:
            pass


# ── Close (layouts 31, 32) ─────────────────────────────────────────

def _populate_close(phs, data):
    _set_ph(phs, 0, data.get("headline", "Thank You"))


# ── Generic fallback ────────────────────────────────────────────────

def _populate_generic(phs, data):
    """Try to populate any available placeholders with whatever content we have."""
    _set_ph(phs, 0, data.get("headline", ""))
    _set_ph(phs, 1, data.get("body", ""))
    if data.get("bullets") and 10 in phs:
        tf = phs[10].text_frame
        tf.clear()
        for i, b in enumerate(data["bullets"]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = b
    _set_ph(phs, 13, data.get("subheadline", ""))


# ── Helper ──────────────────────────────────────────────────────────

def _set_ph(phs: Dict[int, Any], idx: int, text: str):
    """Set a placeholder's text if it exists and text is non-empty."""
    if idx in phs and text:
        phs[idx].text_frame.text = text

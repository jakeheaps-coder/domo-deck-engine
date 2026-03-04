"""
Content writer — resolves slide content from multiple sources AND picks
the best layout from the full 309-layout catalog for each slide.

The AI sees the entire layout catalog and chooses layouts that:
1. Match the content (bullets → bullet layout, quote → quote layout, etc.)
2. Create visual variety (don't repeat the same layout)
3. Stay coherent (consistent color family based on audience)
"""

from pathlib import Path
from typing import Dict, Any, List
from helpers.gemini_helper import generate_structured
from models.deck_config import ContentInput

CATALOG_PATH = Path(__file__).parent.parent / "templates" / "layout_catalog.txt"

SYSTEM_PROMPT = """You are an expert presentation designer and content writer for Domo.

You have access to a PowerPoint template with 309 slide layouts. For each slide,
you must pick the BEST layout_index from the catalog AND write the content.

CONTENT RULES:
- Headlines: 5-8 words max. Active voice. Declarative statements, NOT imperatives.
  GOOD: "Retention Hit Record 94.2%" BAD: "Achieve Record Retention Rates"
- Bullets: 3-5 per slide. Each 8-12 words. Start with action verbs.
- Body text: 2-3 sentences max.
- Speaker notes: 2-4 sentences of what to SAY.
- Quote slides: Attribution as "– Name, Title"
- Icon slides: 3-5 word label + 1 sentence description per point.

LAYOUT SELECTION RULES:
- Use layouts 0-2 for title slides (0=blue, 1=white, 2=gradient)
- Use layouts 3-5 for section breaks (3=blue, 4=white, 5=gradient)
- Use layouts 10-11 for quotes (10=blue, 11=white)
- Use layouts 12-22 for content slides (bullets, columns, images, blue variants)
- Use layouts 23-30 for icon slides and mockups
- Use layouts 31-32 for closing slides
- Layouts 33+ are specialty (timelines, image galleries, dashboards, testimonials, etc.)
  Use these for visual variety when the content calls for it.
- NEVER repeat the same layout_index in consecutive slides.
- Pick a consistent color family for the deck (blue OR white OR gradient for structural slides).
- Mix content layouts for variety (don't use layout 12 for every content slide).

PLACEHOLDER RULES — each layout has specific placeholders. You must provide content
that matches the placeholders available in that layout:
- PH0 = Title/headline (almost all layouts have this)
- PH1 = Body text or subtitle
- PH10 = Secondary text or bullet area
- PH11-PH15 = Picture placeholders (provide image_prompt if needed)
- PH12 = Body text (blue layouts)
- PH13 = Description/subtitle
- PH14 = Date/notes line
- PH17/18 = Icon title/description (1st icon)
- PH20/21 = Icon title/description (2nd icon)
- PH23/24 = Icon title/description (3rd icon, LEFT position in layout 25)

OUTPUT FORMAT — JSON array of slide objects:
{
  "position": <int>,
  "layout_index": <int 0-308>,
  "layout_name": "<name from catalog>",
  "headline": "<string>",
  "subheadline": "<string or null>",
  "body": "<string or null>",
  "bullets": ["<string>", ...] or null,
  "icon_points": [{"label": "<str>", "description": "<str>"}] or null,
  "quote": "<string or null>",
  "quote_attribution": "<string or null>",
  "speaker_notes": "<string>",
  "image_prompt": "<string or null>",
  "placeholder_map": {"<PH_index>": "<content>"}
}

The placeholder_map is the PRIMARY way content gets into the slide.
Map placeholder indices (as strings) to content values.
"""


def _load_catalog() -> str:
    if CATALOG_PATH.exists():
        return CATALOG_PATH.read_text()
    return ""


def resolve_content(
    content: ContentInput,
    deck_title: str,
    audience: str,
    tone: str,
    purpose: str,
    key_messages: List[str],
    slide_count: str = "10-15",
    research_summary: str = "",
    additional_context: str = "",
    design_preference: str = "blue",
) -> List[Dict[str, Any]]:
    """
    Resolve content for all slides. Gemini picks layouts from the full catalog.
    """
    # User explicit slides
    user_map: Dict[int, Dict] = {}
    for sc in content.per_slide:
        user_map[sc.position] = sc.model_dump(exclude_none=True)

    catalog = _load_catalog()
    target = {"5-8": 7, "10-15": 12, "15-20": 17, "20+": 22}.get(slide_count, 12)

    user_block = ""
    if content.outline:
        user_block += f"\nUSER OUTLINE:\n{content.outline}\n"
    if content.talking_points:
        user_block += "\nUSER TALKING POINTS:\n" + "\n".join(f"- {t}" for t in content.talking_points) + "\n"
    if content.source_text:
        user_block += f"\nUSER SOURCE TEXT:\n{content.source_text[:3000]}\n"

    user_slides_block = ""
    if user_map:
        user_slides_block = "\nUSER-PROVIDED SLIDE CONTENT (use verbatim, pick appropriate layout):\n"
        for pos, sc in sorted(user_map.items()):
            user_slides_block += f"  Slide {pos}: {sc}\n"

    msgs = "\n".join(f"- {m}" for m in key_messages if m) if key_messages else "- Not specified"

    prompt = f"""Design a {target}-slide presentation and pick the best layout for each slide.

DECK TITLE: {deck_title}
AUDIENCE: {audience}
TONE: {tone}
PURPOSE: {purpose}
COLOR PREFERENCE: {design_preference} (use this color family for title/section/close slides)

KEY MESSAGES:
{msgs}
{user_block}{user_slides_block}
{"RESEARCH DATA (use to enrich content):" + chr(10) + research_summary if research_summary else ""}
ADDITIONAL CONTEXT: {additional_context}

LAYOUT CATALOG (index|name|placeholders):
{catalog}

Generate exactly {target} slides. For each slide, pick the best layout_index from the catalog above.
Create visual variety — use different layout types, don't repeat layouts consecutively.
Include a placeholder_map that maps placeholder indices to content for that layout.
Return a JSON array of slide objects."""

    result = generate_structured(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.6)

    if "error" in result:
        return _fallback(target, deck_title, purpose)
    if isinstance(result, list):
        slides = result
    elif isinstance(result, dict) and "slides" in result:
        slides = result["slides"]
    else:
        return _fallback(target, deck_title, purpose)

    # Merge user content (user wins)
    for i, slide in enumerate(slides):
        slide["position"] = i
        if i in user_map:
            for k, v in user_map[i].items():
                if v is not None:
                    slide[k] = v

    return slides


def _fallback(count, title, purpose):
    layouts = [0, 3, 12, 15, 12, 18, 3, 12, 25, 12, 3, 31]
    while len(layouts) < count:
        layouts.insert(-1, 12)
    return [
        {
            "position": i,
            "layout_index": layouts[i] if i < len(layouts) else 12,
            "headline": title if i == 0 else f"Section {i}",
            "subheadline": purpose if i == 0 else None,
            "bullets": ["Point 1", "Point 2", "Point 3"] if layouts[i] == 12 else None,
            "placeholder_map": {},
        }
        for i in range(count)
    ]

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

SYSTEM_PROMPT = """You are a world-class presentation strategist who has coached Fortune 500 CEOs,
built decks that closed billion-dollar deals, and trained thousands of executives on
presentation best practices. You write for Domo, a data and AI platform company.

You have access to a PowerPoint template with 309 professionally designed slide layouts.
Your job: pick the perfect layout for each slide AND write compelling, specific content.

═══════════════════════════════════════════════════════════════
PRESENTATION BEST PRACTICES (FOLLOW THESE EXACTLY)
═══════════════════════════════════════════════════════════════

1. NARRATIVE ARC — Every deck tells a story with a beginning, middle, and end:
   - Opening: Set context. Why are we here? What's at stake?
   - Build: Present evidence, data, insights. Each slide advances the argument.
   - Climax: The key insight, recommendation, or ask.
   - Close: Clear next steps or call to action. Never end with "Thank You" alone —
     always include a takeaway or next step alongside it.

2. ONE IDEA PER SLIDE — If a slide has two ideas, split it into two slides.
   The audience should get the point in 3 seconds by reading the headline alone.

3. HEADLINES ARE THE PRESENTATION — Write headlines as complete takeaways,
   not topic labels. The audience should be able to read ONLY the headlines of
   every slide and understand the entire story.
   WRONG: "Q1 Results" / "Revenue Overview" / "Next Steps"
   RIGHT: "Q1 Revenue Grew 23% to $142M" / "Enterprise Drove 80% of Growth" / "Expand Into Mid-Market by Q3"
   WRONG: Imperatives like "Achieve Growth" or "Drive Results"
   RIGHT: Declarative facts like "Growth Reached Record Levels"

4. SPECIFIC > GENERIC — Never use vague language. Include actual numbers,
   percentages, dollar amounts, customer names, product names, dates.
   WRONG: "Significant improvement in key metrics"
   RIGHT: "Gross retention hit 94.2% — highest since Q3 FY24"

5. BULLETS THAT BREATHE — Each bullet is one complete thought (8-15 words).
   Start with a strong verb or number. No sub-bullets. 3-5 bullets max.
   WRONG: "We have been working on improving our customer retention rates"
   RIGHT: "Retained 94.2% of customers — up 3.1 points YoY"

6. VISUAL VARIETY — Alternate layout types to keep the audience engaged:
   - After 2 text-heavy slides, use an icon, image, or quote slide
   - Use 2-column layouts for comparisons (before/after, pros/cons, old/new)
   - Use icon layouts for 2-3 parallel concepts or pillars
   - Use quote layouts for customer voices or key statements
   - Use section breaks to signal topic changes (not as filler)

7. SPEAKER NOTES = WHAT TO SAY — Not a repeat of the slide. The notes are
   the presenter's script: transitions, context, anecdotes, data sources.
   "This slide shows our retention story. The 94.2% number is our best in 3 years,
   driven primarily by the enterprise segment where we invested in dedicated CSMs."

═══════════════════════════════════════════════════════════════
CRITICAL RULES — VIOLATIONS WILL BE REJECTED
═══════════════════════════════════════════════════════════════

- EVERY slide must have real, specific content. NEVER return placeholder text
  like "Enter text here", "Click to edit", "Add content", or empty strings.
- EVERY talking point the user provided MUST appear in the deck. Do not drop any.
- EVERY key message MUST be a headline on at least one slide.
- Section breaks must have a purpose — they signal a topic shift. Use 2-3 max.
  Do NOT use them as filler. Each section title should preview what's coming.
- The title slide MUST contain the deck title, a subtitle, and date/context.
- The closing slide MUST contain a clear next step or CTA, not just "Thank You".

═══════════════════════════════════════════════════════════════
LAYOUT SELECTION (309 LAYOUTS AVAILABLE)
═══════════════════════════════════════════════════════════════

Layouts 0-2: Title slides (0=blue, 1=white, 2=gradient). PH0=title, PH13=subtitle, PH14=date.
Layouts 3-5: Section breaks (3=blue, 4=white, 5=gradient). PH0=title, PH13=subtitle.
Layouts 6-9: Speaker/bio slides. PH10=photo, PH18=name, PH19=title.
Layouts 10-11: Quote slides (10=blue, 11=white). PH0=quote text, PH20=attribution.
Layout 12: Bullets. PH0=title, PH10=bullet list (multi-paragraph).
Layout 13: 1-column body. PH0=title, PH1=body text.
Layouts 14-15: 2-column. PH0=title, PH1=left col, PH10=right col (layout 15).
Layouts 16-17: Text + picture. PH0=title, PH1=text, PH11=picture.
Layout 18: Blue emphasis. PH0=title, PH12=body.
Layouts 19-22: Blue variants of columns/images.
Layouts 23-28: Icon layouts (1/2/3 icons). PH0=title, PH17/18=icon1 title/desc, PH20/21=icon2, PH23/24=icon3.
Layouts 29-30: Mockups (phone/screen). PH0=title, PH1=text, PH11=picture.
Layouts 31-32: Closing slides. PH0=title.
Layouts 33+: Specialty — timelines, image galleries, dashboards, testimonials, org charts, etc.

RULES:
- NEVER repeat the same layout_index on consecutive slides
- Use a consistent color family for structural slides (title, sections, close)
- Content slides (12-30) can mix freely for variety
- Use at least 4 DIFFERENT layout types across the deck
- Use specialty layouts (33+) when content calls for it (timelines, team intros, etc.)

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

Return a JSON array. Each slide object:
{
  "position": <int>,
  "layout_index": <int 0-308>,
  "layout_name": "<name from catalog>",
  "headline": "<complete takeaway headline>",
  "subheadline": "<context or subtitle>" or null,
  "body": "<paragraph text>" or null,
  "bullets": ["<specific bullet>", ...] or null,
  "icon_points": [{"label": "<3-5 words>", "description": "<1 sentence>"}] or null,
  "quote": "<quote text>" or null,
  "quote_attribution": "<– Name, Title>" or null,
  "speaker_notes": "<what the presenter should SAY>",
  "image_prompt": "<description for AI image generation>" or null,
  "placeholder_map": {"<PH_index_as_string>": "<content>"}
}

The placeholder_map is the PRIMARY way content reaches the slide. You MUST populate
every text placeholder that exists in the chosen layout. Map placeholder indices
(as strings like "0", "1", "10", "13") to their content.
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

    prompt = f"""Design a {target}-slide presentation. Pick the best layout AND write compelling content for each slide.

DECK TITLE: {deck_title}
AUDIENCE: {audience}
TONE: {tone}
PURPOSE: {purpose}
COLOR PREFERENCE: {design_preference} (use this color family for title/section/close slides)

KEY MESSAGES (EACH must be a headline on at least one slide):
{msgs}
{user_block}{user_slides_block}
{"RESEARCH DATA (weave into slides as supporting evidence — real numbers, proof points):" + chr(10) + research_summary if research_summary else ""}
ADDITIONAL CONTEXT: {additional_context}

LAYOUT CATALOG (index|name|placeholders):
{catalog}

REQUIREMENTS:
1. Generate exactly {target} slides with real, specific, compelling content on EVERY slide.
2. Every talking point and key message MUST appear in the deck — do not drop any.
3. Headlines must be complete takeaways: "Retention Hit 94.2% — Best in 3 Years" not "Retention Overview".
4. Pick a different layout_index for variety — use at least 5 different layouts across the deck.
5. Every placeholder_map must populate ALL text placeholders in the chosen layout — no empty placeholders.
6. Section breaks (layouts 3-5) should have a meaningful title that previews the next section.
7. Include speaker_notes on EVERY slide — what should the presenter SAY (not read).
8. NO placeholder text. NO generic content. EVERY word must be specific to this deck.

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

"""
Content writer — resolves slide content from multiple sources.

Priority order per slide:
1. User-provided explicit content (per_slide) → use verbatim
2. User talking points + outline → Gemini structures into slides
3. KG research (if auto_research=true) → enriches with data
4. Gemini generation → fills remaining gaps
"""

from typing import Dict, Any, List
from helpers.gemini_helper import generate_structured
from models.deck_config import ContentInput


SYSTEM_PROMPT = """You are an expert presentation content writer for Domo, a data and AI platform company.

BRAND VOICE:
- Confident but not arrogant. Data-backed. Forward-looking.
- Speak to outcomes, not features.
- Use active voice. Short sentences. One idea per slide.

SLIDE CONTENT RULES:
- Headlines: 5-8 words max. Active voice. No ending punctuation.
- Bullets: 3-5 per slide. Each 8-12 words. Start with action verbs.
- Body text: 2-3 sentences max.
- Speaker notes: 2-4 sentences of what to SAY.
- Quote slides: Attribution as "– Name, Title"
- Icon slides: 3-5 word label + 1 sentence description per point.

OUTPUT: Return a JSON array of slide objects. Each must have:
{
  "position": <int>,
  "slide_type": "<string>",
  "headline": "<string>",
  "subheadline": "<string or null>",
  "body": "<string or null>",
  "bullets": ["<string>", ...] or null,
  "icon_points": [{"label": "<str>", "description": "<str>"}] or null,
  "quote": "<string or null>",
  "quote_attribution": "<string or null>",
  "speaker_notes": "<string>",
  "image_prompt": "<string or null>"
}
"""


def resolve_content(
    slide_sequence: List[str],
    content: ContentInput,
    deck_title: str,
    audience: str,
    tone: str,
    purpose: str,
    key_messages: List[str],
    research_summary: str = "",
    additional_context: str = "",
) -> List[Dict[str, Any]]:
    """
    Resolve content for all slides, merging user input with AI generation.
    """
    # Build user content map by position
    user_map: Dict[int, Dict] = {}
    for sc in content.per_slide:
        user_map[sc.position] = sc.model_dump(exclude_none=True)

    # Check which slides need AI
    needs_ai = [i for i in range(len(slide_sequence)) if i not in user_map]

    # If user provided everything AND no outline/talking points, skip AI
    has_user_text = bool(content.outline or content.talking_points or content.source_text)
    if not needs_ai and not has_user_text:
        return _from_user_only(slide_sequence, user_map)

    # Generate AI content for missing slides
    ai_slides = _generate_ai(
        slide_sequence, needs_ai, content, deck_title,
        audience, tone, purpose, key_messages,
        research_summary, additional_context,
    )
    ai_by_pos = {s.get("position", i): s for i, s in enumerate(ai_slides)}

    # Merge: user content wins
    final = []
    for i, stype in enumerate(slide_sequence):
        if i in user_map:
            slide = user_map[i]
            slide["position"] = i
            slide["slide_type"] = stype
            final.append(slide)
        elif i in ai_by_pos:
            slide = ai_by_pos[i]
            slide["slide_type"] = stype
            final.append(slide)
        else:
            final.append({"position": i, "slide_type": stype, "headline": ""})
    return final


def _from_user_only(seq, user_map):
    slides = []
    for i, stype in enumerate(seq):
        if i in user_map:
            s = user_map[i]
            s["position"] = i
            s["slide_type"] = stype
            slides.append(s)
        else:
            slides.append({"position": i, "slide_type": stype, "headline": ""})
    return slides


def _generate_ai(seq, needs_ai, content, title, audience, tone, purpose, msgs, research, ctx):
    descs = []
    for i, stype in enumerate(seq):
        tag = " [USER PROVIDED]" if i not in needs_ai else ""
        descs.append(f"Slide {i+1}: type={stype}{tag}")

    user_block = ""
    if content.outline:
        user_block += f"\nUSER OUTLINE:\n{content.outline}\n"
    if content.talking_points:
        user_block += "\nUSER TALKING POINTS:\n" + "\n".join(f"- {t}" for t in content.talking_points) + "\n"
    if content.source_text:
        user_block += f"\nUSER SOURCE TEXT:\n{content.source_text[:3000]}\n"

    msgs_block = "\n".join(f"- {m}" for m in msgs if m) if msgs else "- Not specified"

    prompt = f"""Generate content for a {len(seq)}-slide presentation.

DECK TITLE: {title}
AUDIENCE: {audience}
TONE: {tone}
PURPOSE: {purpose}

KEY MESSAGES:
{msgs_block}

SLIDE SEQUENCE:
{chr(10).join(descs)}
{user_block}
{"RESEARCH DATA (enrich, don't override user content):" + chr(10) + research if research else ""}
ADDITIONAL CONTEXT: {ctx}

Generate content ONLY for slides NOT marked [USER PROVIDED].
Return a JSON array of slide objects."""

    result = generate_structured(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.6)

    if "error" in result:
        return _fallback(seq, title, purpose)
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "slides" in result:
        return result["slides"]
    return _fallback(seq, title, purpose)


def _fallback(seq, title, purpose):
    return [
        {
            "position": i,
            "slide_type": stype,
            "headline": title if i == 0 else f"Section {i}",
            "subheadline": purpose if i == 0 else None,
            "bullets": ["Point 1", "Point 2", "Point 3"] if stype == "bullets" else None,
            "speaker_notes": f"[Slide {i+1}: {stype}]",
        }
        for i, stype in enumerate(seq)
    ]

"""
Content writer — uses Gemini to generate slide content based on research
and deck configuration.
"""

import json
from typing import Dict, Any, List, Optional
from helpers.gemini_helper import generate_structured
from models.deck_config import LAYOUTS


SYSTEM_PROMPT = """You are an expert presentation content writer for Domo, a data and AI platform company.

BRAND VOICE:
- Confident but not arrogant. Data-backed. Forward-looking.
- Speak to outcomes, not features. "See your data in action" not "We have dashboards."
- Use active voice. Short sentences. One idea per slide.
- Executive audiences: lead with metrics, be concise, skip jargon.
- Team audiences: be more narrative, celebrate wins, include context.

SLIDE CONTENT RULES:
- Headlines: 5-8 words max. Active voice. No punctuation.
- Subheadlines: 1 sentence max. Provides context for the headline.
- Bullets: 3-5 per slide. Each bullet is 1 line (8-12 words). Start with action verbs.
- Body text: 2-3 sentences max. Tell a mini-story or provide evidence.
- Speaker notes: 2-4 sentences. What the presenter should SAY (not read from the slide).
- Quote slides: Attribution format is "— Name, Title"
- Icon slides: Each icon point gets a 3-5 word label + 1 sentence description.

OUTPUT FORMAT:
Return a JSON array of slide objects. Each slide must have:
{
  "position": <int>,
  "layout_id": <int>,
  "headline": "<string>",
  "subheadline": "<string or null>",
  "body": "<string or null>",
  "bullets": ["<string>", ...] or null,
  "icon_points": [{"label": "<string>", "description": "<string>"}] or null,
  "quote": "<string or null>",
  "quote_attribution": "<string or null>",
  "speaker_notes": "<string>",
  "image_prompt": "<string or null>"
}
"""


def generate_slide_content(
    deck_title: str,
    audience: str,
    tone: str,
    purpose: str,
    key_messages: List[str],
    layout_sequence: List[int],
    research_summary: str,
    additional_context: str = "",
    template_notes: str = "",
) -> List[Dict[str, Any]]:
    """
    Generate content for all slides in the deck.

    Args:
        deck_title: The presentation title
        audience: Target audience
        tone: Tone/style to use
        purpose: What the deck is about
        key_messages: Key points to hit
        layout_sequence: Ordered list of layout IDs
        research_summary: Text summary from the researcher
        additional_context: Any extra instructions

    Returns:
        List of slide content dicts, one per slide
    """
    # Build the layout description for each slide
    slide_descriptions = []
    for i, layout_id in enumerate(layout_sequence):
        layout = LAYOUTS.get(layout_id, {"label": "Unknown", "type": "bullets"})
        slide_descriptions.append(f"Slide {i+1}: Layout {layout_id} ({layout['label']}) — {layout['type']} slide. Use: {layout.get('use', '')}")

    slides_block = "\n".join(slide_descriptions)
    messages_block = "\n".join(f"- {m}" for m in key_messages if m) if key_messages else "- Not specified"

    prompt = f"""Generate content for a {len(layout_sequence)}-slide presentation.

DECK TITLE: {deck_title}
AUDIENCE: {audience}
TONE: {tone}
PURPOSE: {purpose}

KEY MESSAGES TO INCORPORATE:
{messages_block}

SLIDE SEQUENCE:
{slides_block}

RESEARCH DATA (use this to inform content — do not copy verbatim):
{research_summary}

TEMPLATE NOTES: {template_notes}
ADDITIONAL CONTEXT: {additional_context}

Generate compelling, specific content for each slide. Use the research data to add real product names, features, metrics, and competitive points. Make every headline punchy and every bullet actionable. Return the JSON array of slide objects."""

    result = generate_structured(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.6)

    if "error" in result:
        # Return fallback content
        return _generate_fallback(layout_sequence, deck_title, purpose)

    # Handle both direct array and wrapped responses
    if isinstance(result, list):
        slides = result
    elif isinstance(result, dict) and "slides" in result:
        slides = result["slides"]
    else:
        return _generate_fallback(layout_sequence, deck_title, purpose)

    return slides


def rewrite_slide(
    slide_content: Dict[str, Any],
    instruction: str,
    tone: str = "Executive",
) -> Dict[str, Any]:
    """Rewrite a single slide's content with specific instructions."""
    prompt = f"""Rewrite this slide content following the instruction below.

CURRENT CONTENT:
{json.dumps(slide_content, indent=2)}

INSTRUCTION: {instruction}
TONE: {tone}

Return the updated slide as a single JSON object with the same fields."""

    result = generate_structured(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.5)
    if "error" in result:
        return slide_content  # Return original on failure
    return result


def _generate_fallback(layout_sequence: List[int], title: str, purpose: str) -> List[Dict[str, Any]]:
    """Generate basic placeholder content if Gemini fails."""
    slides = []
    for i, layout_id in enumerate(layout_sequence):
        layout = LAYOUTS.get(layout_id, {"label": "Bullets", "type": "bullets"})
        slide = {
            "position": i,
            "layout_id": layout_id,
            "headline": title if i == 0 else f"Section {i}",
            "subheadline": purpose if i == 0 else None,
            "body": None,
            "bullets": ["Point 1", "Point 2", "Point 3"] if layout["type"] == "bullets" else None,
            "speaker_notes": f"[Slide {i+1}: {layout['label']}]",
            "image_prompt": None,
        }
        slides.append(slide)
    return slides

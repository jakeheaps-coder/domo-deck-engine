"""
Critique agent — reviews the deck as the intended audience and returns
specific, actionable improvements. Applied automatically before final assembly.
"""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from helpers.gemini_helper import generate_structured


class SlideFix(BaseModel):
    slide_position: int
    issue: str
    fix: str
    severity: str  # "high" | "medium"
    new_headline: Optional[str] = None
    new_bullets: Optional[list[str]] = None
    new_body: Optional[str] = None
    new_subheadline: Optional[str] = None


class CritiqueResult(BaseModel):
    overall_score: int = 5  # 1-10
    summary: str = ""
    fixes: List[SlideFix] = Field(default_factory=list)


CRITIQUE_PROMPT = """You are a {audience} member reviewing a presentation titled "{title}".
Purpose: {purpose}
Tone expected: {tone}

You are sitting in the meeting. Critique this deck honestly and specifically.

SLIDES:
{slides_json}

KEY MESSAGES THE PRESENTER WANTS TO LAND:
{key_messages}

EVALUATE EACH SLIDE FOR:
1. FLOW: Does the deck tell a coherent story? Clear narrative arc?
2. CLARITY: Is each slide's message immediately clear? Any jargon?
3. EVIDENCE: Are claims backed by data? Unsupported assertions?
4. CONCISENESS: Too wordy? Headlines too long (max 8 words)?
5. KEY MESSAGES: Do the key messages come through clearly?
6. MISSING: Anything this audience would expect to see?
7. REDUNDANCY: Any slides repetitive or unnecessary?

Return JSON:
{{
  "overall_score": <1-10>,
  "summary": "<2-3 sentence overall assessment>",
  "fixes": [
    {{
      "slide_position": <int>,
      "issue": "<what's wrong>",
      "fix": "<what to do>",
      "severity": "high" or "medium",
      "new_headline": "<rewritten headline or null>",
      "new_bullets": ["<rewritten bullets>"] or null,
      "new_body": "<rewritten body or null>",
      "new_subheadline": "<rewritten subheadline or null>"
    }}
  ]
}}

Only return HIGH and MEDIUM severity issues. Give exact rewrites, not vague suggestions."""


def critique_deck(
    slides: List[Dict[str, Any]],
    audience: str,
    tone: str,
    purpose: str,
    title: str,
    key_messages: List[str],
) -> CritiqueResult:
    """
    Review the deck as the intended audience and return improvements.
    """
    # Build a clean view of slides for the critic
    clean_slides = []
    for s in slides:
        clean = {
            "position": s.get("position"),
            "slide_type": s.get("slide_type"),
            "headline": s.get("headline", ""),
            "subheadline": s.get("subheadline"),
            "bullets": s.get("bullets"),
            "body": s.get("body"),
            "quote": s.get("quote"),
        }
        clean_slides.append(clean)

    msgs_text = "\n".join(f"- {m}" for m in key_messages if m) if key_messages else "- None specified"

    prompt = CRITIQUE_PROMPT.format(
        audience=audience,
        title=title,
        purpose=purpose,
        tone=tone,
        slides_json=json.dumps(clean_slides, indent=2),
        key_messages=msgs_text,
    )

    result = generate_structured(prompt, temperature=0.4)

    if "error" in result:
        print(f"Critique agent error: {result['error']}")
        return CritiqueResult(overall_score=7, summary="Critique unavailable.", fixes=[])

    try:
        return CritiqueResult(**result)
    except Exception as e:
        print(f"Critique parse error: {e}")
        return CritiqueResult(overall_score=7, summary="Critique parse failed.", fixes=[])


def apply_fixes(slides: List[Dict[str, Any]], critique: CritiqueResult) -> List[Dict[str, Any]]:
    """
    Apply the critique's fixes to the slide content.
    Only applies high and medium severity fixes.
    """
    fix_map: Dict[int, SlideFix] = {}
    for fix in critique.fixes:
        if fix.severity in ("high", "medium"):
            fix_map[fix.slide_position] = fix

    if not fix_map:
        return slides

    updated = []
    for slide in slides:
        pos = slide.get("position", -1)
        if pos in fix_map:
            fix = fix_map[pos]
            slide = dict(slide)  # copy
            if fix.new_headline:
                slide["headline"] = fix.new_headline
            if fix.new_subheadline:
                slide["subheadline"] = fix.new_subheadline
            if fix.new_bullets:
                slide["bullets"] = fix.new_bullets
            if fix.new_body:
                slide["body"] = fix.new_body
        updated.append(slide)

    return updated

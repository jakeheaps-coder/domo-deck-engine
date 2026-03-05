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


CRITIQUE_PROMPT = """You are a senior {audience} member — demanding, time-constrained, and allergic
to fluff. You are reviewing a presentation titled "{title}".
Purpose: {purpose}
Tone expected: {tone}

You have 30 minutes. Every slide must earn its place. Critique this deck ruthlessly.

SLIDES:
{slides_json}

KEY MESSAGES THE PRESENTER WANTS TO LAND:
{key_messages}

EVALUATE WITH ZERO TOLERANCE:

1. EMPTY OR PLACEHOLDER CONTENT — Any slide with generic text like "Enter text",
   "Click to edit", empty headlines, or vague language is an automatic HIGH severity fix.
   Rewrite it with specific, relevant content.

2. HEADLINE TEST — Read ONLY the headlines in sequence. Do they tell the complete story?
   If not, rewrite the weak ones as complete takeaways with data.
   BAD: "Q1 Performance" → GOOD: "Q1 Revenue Grew 23% to $142M"
   BAD: "Achieve Growth" → GOOD: "Enterprise Grew 34% YoY"

3. NARRATIVE ARC — Opening sets context → Body builds evidence → Climax delivers insight → Close has clear next step. Flag any gaps.

4. SPECIFICITY — Every claim needs a number. "Strong growth" → "34% YoY growth".
   "Good retention" → "94.2% gross retention". Flag vague slides.

5. KEY MESSAGE COVERAGE — Each key message MUST appear as a headline.
   If a key message is missing, flag it as HIGH and write the missing slide content.

6. REDUNDANCY — Merge or cut any slides that repeat the same point.

7. FILLER — Section breaks without purpose, slides with only a headline and no
   supporting content, "Thank You" slides with no next step — flag all of these.

Return JSON:
{{
  "overall_score": <1-10>,
  "summary": "<2-3 sentence assessment>",
  "fixes": [
    {{
      "slide_position": <int>,
      "issue": "<specific problem>",
      "fix": "<specific action>",
      "severity": "high" or "medium",
      "new_headline": "<rewritten headline with data>" or null,
      "new_bullets": ["<specific, rewritten bullets>"] or null,
      "new_body": "<rewritten body text>" or null,
      "new_subheadline": "<rewritten subheadline>" or null
    }}
  ]
}}

Rules:
- Only HIGH and MEDIUM severity. Be specific — exact rewrites, not suggestions.
- For empty slides, write the FULL replacement content (headline + bullets or body).
- Use the actual data from the talking points and key messages in your rewrites."""


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

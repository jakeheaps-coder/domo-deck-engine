"""
Orchestrator — coordinates the full deck generation pipeline:
1. Research (optional — KG API)
2. Content + layout selection (Gemini picks from 309 layouts)
3. Critique agent reviews and improves
4. Media generation (optional)
5. Assemble .pptx from real template
"""

import uuid
import time
import threading
from typing import Dict, Any, Optional, List

from config import OUTPUT_DIR
from models.deck_config import DeckConfig, TEMPLATE_STYLE_MAP
from engine.researcher import research_for_deck, summarize_research
from engine.content_writer import resolve_content
from engine.critique_agent import critique_deck, apply_fixes
from engine.media_generator import generate_batch_images
from engine.slide_builder import build_presentation


_jobs: Dict[str, Dict[str, Any]] = {}


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs.get(job_id)


def generate_deck(config: DeckConfig) -> str:
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "status": "queued", "progress": 0, "message": "Queued",
        "config": config.model_dump(), "created_at": time.time(),
        "file_path": None, "error": None, "critique": None,
    }
    threading.Thread(target=_run_pipeline, args=(job_id, config), daemon=True).start()
    return job_id


def generate_deck_sync(config: DeckConfig) -> bytes:
    """Synchronous generation — returns .pptx bytes."""
    # 1. Research
    research_summary = ""
    if config.auto_research:
        research = research_for_deck(
            audience=config.audience, industry=config.industry or "",
            products=config.products, competitors=config.competitors,
            topic=config.purpose,
        )
        research_summary = summarize_research(research)

    # 2. Content + layout selection (AI picks layouts from full catalog)
    design_pref = config.design_style or TEMPLATE_STYLE_MAP.get(config.template, "blue")
    # Map style names to color preference for the AI
    color_map = {"executive_blue": "blue", "clean_white": "white", "gradient": "gradient"}
    color_pref = color_map.get(design_pref, design_pref)

    slides = resolve_content(
        content=config.content,
        deck_title=config.title,
        audience=config.audience,
        tone=config.tone,
        purpose=config.purpose,
        key_messages=config.key_messages,
        slide_count=config.slide_count,
        research_summary=research_summary,
        additional_context=config.additional_context,
        design_preference=color_pref,
    )

    # 3. Critique + improve
    if config.enable_critique:
        critique = critique_deck(
            slides=slides, audience=config.audience, tone=config.tone,
            purpose=config.purpose, title=config.title, key_messages=config.key_messages,
        )
        print(f"Critique: score={critique.overall_score}/10 — {critique.summary}")
        for fix in critique.fixes:
            print(f"  [{fix.severity}] Slide {fix.slide_position}: {fix.issue}")
        slides = apply_fixes(slides, critique)

        if critique.overall_score < 7:
            print("Score < 7, running second critique...")
            c2 = critique_deck(
                slides=slides, audience=config.audience, tone=config.tone,
                purpose=config.purpose, title=config.title, key_messages=config.key_messages,
            )
            print(f"Re-critique: score={c2.overall_score}/10")
            slides = apply_fixes(slides, c2)

    # 4. Media (optional)
    image_map = {}
    if config.auto_media:
        image_map = generate_batch_images(slides, uuid.uuid4().hex[:8])

    # 5. Assemble
    return build_presentation(slides=slides, image_map=image_map, title=config.title)


def _run_pipeline(job_id: str, config: DeckConfig):
    try:
        _update(job_id, "researching", 10, "Researching content...")
        research_summary = ""
        if config.auto_research:
            research = research_for_deck(
                audience=config.audience, industry=config.industry or "",
                products=config.products, competitors=config.competitors,
                topic=config.purpose,
            )
            research_summary = summarize_research(research)

        _update(job_id, "writing", 25, "AI selecting layouts + writing content...")
        design_pref = config.design_style or TEMPLATE_STYLE_MAP.get(config.template, "blue")
        color_map = {"executive_blue": "blue", "clean_white": "white", "gradient": "gradient"}

        slides = resolve_content(
            content=config.content,
            deck_title=config.title, audience=config.audience,
            tone=config.tone, purpose=config.purpose,
            key_messages=config.key_messages, slide_count=config.slide_count,
            research_summary=research_summary,
            additional_context=config.additional_context,
            design_preference=color_map.get(design_pref, design_pref),
        )

        if config.enable_critique:
            _update(job_id, "critiquing", 50, "Reviewing deck as intended audience...")
            critique = critique_deck(
                slides=slides, audience=config.audience, tone=config.tone,
                purpose=config.purpose, title=config.title, key_messages=config.key_messages,
            )
            _jobs[job_id]["critique"] = critique.model_dump()
            slides = apply_fixes(slides, critique)

            if critique.overall_score < 7:
                _update(job_id, "improving", 60, "Improving based on critique...")
                c2 = critique_deck(
                    slides=slides, audience=config.audience, tone=config.tone,
                    purpose=config.purpose, title=config.title, key_messages=config.key_messages,
                )
                slides = apply_fixes(slides, c2)

        image_map = {}
        if config.auto_media:
            _update(job_id, "generating_media", 70, "Generating graphics...")
            image_map = generate_batch_images(slides, job_id)

        _update(job_id, "assembling", 85, "Building PowerPoint...")
        pptx_bytes = build_presentation(slides=slides, image_map=image_map, title=config.title)

        path = OUTPUT_DIR / f"{job_id}.pptx"
        path.write_bytes(pptx_bytes)
        _update(job_id, "complete", 100, "Done!", file_path=str(path))

    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        _jobs[job_id]["message"] = f"Failed: {e}"


def _update(job_id, status, progress, message, file_path=None):
    if job_id in _jobs:
        _jobs[job_id].update(status=status, progress=progress, message=message)
        if file_path:
            _jobs[job_id]["file_path"] = file_path

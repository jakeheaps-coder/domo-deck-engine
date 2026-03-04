"""
Orchestrator — coordinates the full deck generation pipeline:
1. Resolve slide sequence + design style
2. Resolve content (user input → KG → Gemini)
3. Critique agent reviews and improves
4. Media generation (optional)
5. Assemble .pptx from real template
"""

import uuid
import time
import threading
from typing import Dict, Any, Optional, List

from config import OUTPUT_DIR
from models.deck_config import (
    DeckConfig, DESIGN_STYLES, TEMPLATE_STYLE_MAP,
    TEMPLATE_SEQUENCES, ContentInput,
)
from engine.researcher import research_for_deck, summarize_research
from engine.content_writer import resolve_content
from engine.critique_agent import critique_deck, apply_fixes
from engine.media_generator import generate_batch_images
from engine.slide_builder import build_presentation


# In-memory job store
_jobs: Dict[str, Dict[str, Any]] = {}


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs.get(job_id)


def generate_deck(config: DeckConfig) -> str:
    """Start async deck generation. Returns job ID."""
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "status": "queued", "progress": 0,
        "message": "Queued", "config": config.model_dump(),
        "created_at": time.time(), "file_path": None, "error": None,
        "critique": None,
    }
    thread = threading.Thread(target=_run_pipeline, args=(job_id, config), daemon=True)
    thread.start()
    return job_id


def generate_deck_sync(config: DeckConfig) -> bytes:
    """Synchronous generation — returns .pptx bytes directly."""
    job_id = uuid.uuid4().hex[:12]

    # 1. Resolve design style + slide sequence
    design_style = _resolve_style(config)
    slide_sequence = _resolve_sequence(config)

    # 2. Research (optional)
    research_summary = ""
    if config.auto_research:
        research = research_for_deck(
            audience=config.audience,
            industry=config.industry or "",
            products=config.products,
            competitors=config.competitors,
            topic=config.purpose,
        )
        research_summary = summarize_research(research)

    # 3. Content resolution
    slides = resolve_content(
        slide_sequence=slide_sequence,
        content=config.content,
        deck_title=config.title,
        audience=config.audience,
        tone=config.tone,
        purpose=config.purpose,
        key_messages=config.key_messages,
        research_summary=research_summary,
        additional_context=config.additional_context,
    )

    # 4. Critique + improve
    if config.enable_critique:
        critique = critique_deck(
            slides=slides,
            audience=config.audience,
            tone=config.tone,
            purpose=config.purpose,
            title=config.title,
            key_messages=config.key_messages,
        )
        print(f"Critique: score={critique.overall_score}/10 — {critique.summary}")
        for fix in critique.fixes:
            print(f"  [{fix.severity}] Slide {fix.slide_position}: {fix.issue}")

        slides = apply_fixes(slides, critique)

        # Re-critique if score < 7 (max 1 retry)
        if critique.overall_score < 7:
            print("Score < 7, running second critique...")
            critique2 = critique_deck(
                slides=slides, audience=config.audience, tone=config.tone,
                purpose=config.purpose, title=config.title, key_messages=config.key_messages,
            )
            print(f"Re-critique: score={critique2.overall_score}/10")
            slides = apply_fixes(slides, critique2)

    # 5. Media (optional)
    image_map = {}
    if config.auto_media:
        image_map = generate_batch_images(slides, job_id)

    # 6. Assemble
    pptx_bytes = build_presentation(
        slides=slides,
        design_style=design_style,
        image_map=image_map,
        title=config.title,
    )

    return pptx_bytes


def _run_pipeline(job_id: str, config: DeckConfig):
    """Background pipeline."""
    try:
        design_style = _resolve_style(config)
        slide_sequence = _resolve_sequence(config)

        # Research
        _update(job_id, "researching", 10, "Researching content...")
        research_summary = ""
        if config.auto_research:
            research = research_for_deck(
                audience=config.audience, industry=config.industry or "",
                products=config.products, competitors=config.competitors,
                topic=config.purpose,
            )
            research_summary = summarize_research(research)

        # Content
        _update(job_id, "writing", 30, "Generating slide content...")
        slides = resolve_content(
            slide_sequence=slide_sequence, content=config.content,
            deck_title=config.title, audience=config.audience,
            tone=config.tone, purpose=config.purpose,
            key_messages=config.key_messages, research_summary=research_summary,
            additional_context=config.additional_context,
        )

        # Critique
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
                critique2 = critique_deck(
                    slides=slides, audience=config.audience, tone=config.tone,
                    purpose=config.purpose, title=config.title, key_messages=config.key_messages,
                )
                slides = apply_fixes(slides, critique2)

        # Media
        image_map = {}
        if config.auto_media:
            _update(job_id, "generating_media", 70, "Generating slide graphics...")
            image_map = generate_batch_images(slides, job_id)

        # Assembly
        _update(job_id, "assembling", 85, "Building PowerPoint...")
        pptx_bytes = build_presentation(
            slides=slides, design_style=design_style,
            image_map=image_map, title=config.title,
        )

        output_path = OUTPUT_DIR / f"{job_id}.pptx"
        output_path.write_bytes(pptx_bytes)
        _update(job_id, "complete", 100, "Done!", file_path=str(output_path))

    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        _jobs[job_id]["message"] = f"Failed: {e}"


def _update(job_id, status, progress, message, file_path=None):
    if job_id in _jobs:
        _jobs[job_id].update(status=status, progress=progress, message=message)
        if file_path:
            _jobs[job_id]["file_path"] = file_path


def _resolve_style(config: DeckConfig) -> str:
    if config.design_style:
        return config.design_style
    return TEMPLATE_STYLE_MAP.get(config.template, "executive_blue")


def _resolve_sequence(config: DeckConfig) -> List[str]:
    if config.slide_sequence:
        return config.slide_sequence

    seq = list(TEMPLATE_SEQUENCES.get(config.template, [
        "title", "section", "bullets", "bullets", "bullets",
        "section", "bullets", "bullets", "close"
    ]))

    # Adjust length based on slide_count
    target = {"5-8": 7, "10-15": 12, "15-20": 17, "20+": 22}.get(config.slide_count, 12)

    if len(seq) < target:
        while len(seq) < target:
            seq.insert(-1, "bullets")
    elif len(seq) > target:
        # Trim from middle, keep first 3 and last 2
        keep_start, keep_end = 3, 2
        middle = seq[keep_start:-keep_end]
        trim = target - keep_start - keep_end
        seq = seq[:keep_start] + middle[:max(trim, 1)] + seq[-keep_end:]

    return seq

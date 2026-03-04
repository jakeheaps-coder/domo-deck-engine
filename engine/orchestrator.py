"""
Orchestrator — coordinates the full deck generation pipeline:
Research → Content Writing → Media Generation → Slide Assembly
"""

import uuid
import time
import threading
from typing import Dict, Any, Optional

from config import OUTPUT_DIR
from models.deck_config import DeckConfig, TEMPLATE_PRESETS, LAYOUTS
from engine.researcher import research_for_deck, summarize_research
from engine.content_writer import generate_slide_content
from engine.media_generator import generate_batch_images
from engine.slide_builder import build_presentation


# In-memory job store (swap for Redis/Firestore in production)
_jobs: Dict[str, Dict[str, Any]] = {}


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs.get(job_id)


def generate_deck(config: DeckConfig) -> str:
    """
    Start an async deck generation job.

    Returns:
        Job ID to poll for status
    """
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued for generation",
        "config": config.model_dump(),
        "created_at": time.time(),
        "file_path": None,
        "error": None,
    }

    # Run generation in background thread
    thread = threading.Thread(target=_run_pipeline, args=(job_id, config), daemon=True)
    thread.start()

    return job_id


def generate_deck_sync(config: DeckConfig) -> bytes:
    """
    Synchronous deck generation — returns .pptx bytes directly.
    Use for testing or when you want to block until completion.
    """
    job_id = uuid.uuid4().hex[:12]

    # 1. Determine layout sequence
    layout_sequence = _get_layout_sequence(config)

    # 2. Research
    research = {}
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

    # 3. Content
    template_preset = TEMPLATE_PRESETS.get(config.template, {})
    slides = generate_slide_content(
        deck_title=config.title,
        audience=config.audience,
        tone=config.tone,
        purpose=config.purpose,
        key_messages=config.key_messages,
        layout_sequence=layout_sequence,
        research_summary=research_summary,
        additional_context=config.additional_context,
        template_notes=template_preset.get("notes", ""),
    )

    # 4. Media
    image_map = {}
    if config.auto_media:
        image_map = generate_batch_images(slides, job_id)

    # 5. Assembly
    pptx_bytes = build_presentation(
        slides=slides,
        title=config.title,
        image_map=image_map,
        background_style=config.theme.background_style,
    )

    return pptx_bytes


def _run_pipeline(job_id: str, config: DeckConfig):
    """Background pipeline execution."""
    try:
        _update_job(job_id, "researching", 10, "Researching content via Knowledge Graph...")

        # 1. Layout sequence
        layout_sequence = _get_layout_sequence(config)

        # 2. Research
        research = {}
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

        _update_job(job_id, "writing", 30, "Generating slide content with Gemini...")

        # 3. Content
        template_preset = TEMPLATE_PRESETS.get(config.template, {})
        slides = generate_slide_content(
            deck_title=config.title,
            audience=config.audience,
            tone=config.tone,
            purpose=config.purpose,
            key_messages=config.key_messages,
            layout_sequence=layout_sequence,
            research_summary=research_summary,
            additional_context=config.additional_context,
            template_notes=template_preset.get("notes", ""),
        )

        # 4. Media
        image_map = {}
        if config.auto_media:
            _update_job(job_id, "generating_media", 55, "Generating slide graphics...")
            image_map = generate_batch_images(slides, job_id)

        _update_job(job_id, "assembling", 80, "Building PowerPoint file...")

        # 5. Assembly
        pptx_bytes = build_presentation(
            slides=slides,
            title=config.title,
            image_map=image_map,
            background_style=config.theme.background_style,
        )

        # Save to output dir
        output_path = OUTPUT_DIR / f"{job_id}.pptx"
        output_path.write_bytes(pptx_bytes)

        _update_job(job_id, "complete", 100, "Deck generation complete!", file_path=str(output_path))

    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        _jobs[job_id]["message"] = f"Generation failed: {e}"


def _update_job(job_id: str, status: str, progress: int, message: str, file_path: str = None):
    if job_id in _jobs:
        _jobs[job_id]["status"] = status
        _jobs[job_id]["progress"] = progress
        _jobs[job_id]["message"] = message
        if file_path:
            _jobs[job_id]["file_path"] = file_path


def _get_layout_sequence(config: DeckConfig) -> list[int]:
    """Determine the slide layout sequence from config."""
    # If explicit slides provided, use those
    if config.slides:
        return [s.layout_id for s in config.slides]

    # Otherwise use template defaults
    preset = TEMPLATE_PRESETS.get(config.template)
    if preset:
        layouts = list(preset["default_layouts"])
        # Adjust count based on slide_count setting
        target = _parse_slide_count(config.slide_count)
        if len(layouts) < target:
            # Pad with bullets slides
            while len(layouts) < target:
                layouts.insert(-1, 12)  # Insert bullets before closing
        elif len(layouts) > target:
            # Trim from the middle (keep first 3 and last 2)
            keep_start = 3
            keep_end = 2
            middle = layouts[keep_start:-keep_end]
            trim_to = target - keep_start - keep_end
            layouts = layouts[:keep_start] + middle[:max(trim_to, 1)] + layouts[-keep_end:]
        return layouts

    # Fallback: generic sequence
    return [0, 3, 12, 12, 12, 14, 12, 35]


def _parse_slide_count(slide_count: str) -> int:
    """Parse slide count string to a target number."""
    mapping = {
        "5-8": 7,
        "10-15": 12,
        "15-20": 17,
        "20+": 22,
    }
    return mapping.get(slide_count, 12)

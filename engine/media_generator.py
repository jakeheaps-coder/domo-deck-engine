"""
Media generator — creates brand-aware images for slides using Gemini 3 Pro.
"""

import os
from typing import Dict, Any, List, Optional
from config import BRAND, OUTPUT_DIR


BRAND_PROMPT_PREFIX = (
    "Professional business presentation graphic. "
    "Clean, modern, minimal design. "
    f"Color palette: {BRAND['blue']} (primary blue), {BRAND['orange']} (accent orange), "
    f"{BRAND['dark_text']} (dark gray), white. "
    "No purple gradients. No text on the image. "
    "Suitable for a corporate slide background or visual. "
)


def generate_slide_image(
    prompt: str,
    slide_index: int,
    job_id: str,
    aspect_ratio: str = "16:9",
) -> Optional[str]:
    """
    Generate a brand-compliant image for a slide.

    Args:
        prompt: Description of the image to generate
        slide_index: Slide number (for filename)
        job_id: Job ID (for output directory)
        aspect_ratio: Image aspect ratio

    Returns:
        Path to the generated image, or None on failure
    """
    try:
        from helpers.media_generation_helper import generate_image
    except Exception:
        return None

    # Build brand-aware prompt
    full_prompt = BRAND_PROMPT_PREFIX + prompt

    # Output path
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(job_dir / f"slide_{slide_index:02d}.png")

    try:
        paths = generate_image(
            prompt=full_prompt,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
            image_size="2K",
        )
        return paths[0] if paths else None
    except Exception as e:
        print(f"Image generation failed for slide {slide_index}: {e}")
        return None


def generate_batch_images(
    slides: List[Dict[str, Any]],
    job_id: str,
) -> Dict[int, str]:
    """
    Generate images for all slides that have image prompts.

    Args:
        slides: List of slide content dicts (must have 'image_prompt' key)
        job_id: Job ID for output directory

    Returns:
        Dict mapping slide position to image path
    """
    image_map: Dict[int, str] = {}

    for slide in slides:
        prompt = slide.get("image_prompt")
        position = slide.get("position", 0)

        if not prompt:
            continue

        path = generate_slide_image(
            prompt=prompt,
            slide_index=position,
            job_id=job_id,
        )
        if path:
            image_map[position] = path

    return image_map

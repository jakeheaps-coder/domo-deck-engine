"""Media generation helper — copied from shared toolkit."""

import os
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY.")
    return genai.Client(api_key=api_key)


def generate_image(
    prompt: str,
    output_path: str,
    aspect_ratio: str = "16:9",
    image_size: str = "2K",
) -> list[str]:
    client = _get_client()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=[types.Modality.TEXT, types.Modality.IMAGE],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
        ),
    )

    saved: list[str] = []
    img_count = 0
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image = Image.open(BytesIO(part.inline_data.data))
            if img_count == 0:
                save_path = output_path
            else:
                base, ext = os.path.splitext(output_path)
                save_path = f"{base}_{img_count}{ext}"
            image.save(save_path)
            saved.append(save_path)
            img_count += 1
    return saved

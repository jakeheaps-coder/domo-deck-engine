"""Gemini API helper — copied from shared toolkit."""

import os
import json
import requests
from typing import Dict, Any, Optional


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_content(
    prompt: str,
    system_prompt: str = "",
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", GEMINI_API_KEY))
    if not api_key:
        return "Error: GEMINI_API_KEY not configured."
    model = model or GEMINI_MODEL
    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"

    contents = []
    if system_prompt:
        contents.append({"role": "user", "parts": [{"text": f"[SYSTEM]\n{system_prompt}\n[/SYSTEM]"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and result["candidates"]:
                parts = result["candidates"][0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return "Error: Unexpected response format"
        return f"Error: API returned {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return f"Error: {str(e)}"


def generate_structured(
    prompt: str,
    system_prompt: str = "",
    model: str = None,
    temperature: float = 0.5,
) -> Dict[str, Any]:
    full_prompt = prompt + "\n\nRespond with valid JSON only, no markdown code blocks."
    result = generate_content(full_prompt, system_prompt, model, temperature)
    if result.startswith("Error:"):
        return {"error": result}
    try:
        cleaned = result.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": result}

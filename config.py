"""Central configuration for Deck Engine."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"

# Ensure output dir exists
OUTPUT_DIR.mkdir(exist_ok=True)

# Knowledge Graph API
KG_API_URL = os.environ.get("KG_API_URL", "https://knowledge-graph-api-1053548598846.us-central1.run.app")
KG_API_KEY = os.environ.get("KG_API_KEY", "")

# Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")

# Domo brand constants
BRAND = {
    "blue": "#99CCEE",
    "orange": "#FF9922",
    "dark_text": "#3F454D",
    "light_bg": "#F1F6FA",
    "border": "#DCE4EA",
    "purple": "#776CB0",
    "pink": "#C179BD",
    "mint": "#ADD4C1",
    "font": "Open Sans",
}

# Slide dimensions (widescreen 16:9)
SLIDE_WIDTH_INCHES = 13.333
SLIDE_HEIGHT_INCHES = 7.5

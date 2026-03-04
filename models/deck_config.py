"""Pydantic models for deck configuration and generation."""

from typing import Optional
from pydantic import BaseModel, Field


class DataQuery(BaseModel):
    dataset_id: str
    query: str


class ThemeConfig(BaseModel):
    primary_color: str = "#99CCEE"
    accent_color: str = "#FF9922"
    font_family: str = "Open Sans"


class SlideContent(BaseModel):
    """User-provided content for a specific slide."""
    position: int
    headline: Optional[str] = None
    subheadline: Optional[str] = None
    body: Optional[str] = None
    bullets: Optional[list[str]] = None
    speaker_notes: Optional[str] = None
    quote: Optional[str] = None
    quote_attribution: Optional[str] = None
    icon_points: Optional[list[dict]] = None  # [{"label": ..., "description": ...}]


class ContentInput(BaseModel):
    """All the ways a user can provide content. All fields optional."""
    outline: Optional[str] = None              # "Slide 1: intro. Slide 2: Q1 results..."
    talking_points: list[str] = Field(default_factory=list)  # ["Retention hit 94%", ...]
    source_text: Optional[str] = None          # Paste from a doc — AI structures it
    per_slide: list[SlideContent] = Field(default_factory=list)  # Explicit per-slide content


# ── Design Styles ───────────────────────────────────────────────────
# Maps slide types → template layout indices for visual coherence

DESIGN_STYLES = {
    "executive_blue": {
        "description": "Blue backgrounds, white text. Formal, board-level.",
        "title": 0,           # Title slide - blue
        "section": 3,          # Section title - blue
        "bullets": 12,         # Content - basic - bullets
        "one_column": 13,      # Content - basic - 1 column
        "two_column": 15,      # Content - 2 column
        "text_image": 16,      # Content - text - picture
        "large_image": 17,     # Content - large photo - text
        "quote": 10,           # Quote - blue
        "emphasis": 18,        # Content - basic - blue
        "emphasis_2col": 20,   # Content - 2 column - blue
        "icons_1": 23,         # 1 icon - black
        "icons_2": 24,         # 2 icons - black
        "icons_3": 25,         # 3 icons - black
        "icons_1_desc": 26,    # 1 icon with description
        "icons_2_desc": 27,    # 2 icons with description
        "icons_3_desc": 28,    # 3 icons with description
        "phone_mockup": 29,    # Text + phone mockup
        "screen_mockup": 30,   # Text + screen mockup
        "paragraph": 53,       # Basic paragraph slide
        "intro_image": 54,     # Introduction with image
        "agenda": 52,          # Agenda with image
        "text_landscape": 250, # Text with landscape image
        "close": 31,           # Thank you - blue
    },
    "clean_white": {
        "description": "White backgrounds, dark text. Modern, customer-facing.",
        "title": 1,            # Title Slide - white
        "section": 4,          # Section title - white
        "bullets": 12,
        "one_column": 13,
        "two_column": 15,
        "text_image": 16,
        "large_image": 17,
        "quote": 11,           # Quote - white
        "emphasis": 13,
        "emphasis_2col": 15,
        "icons_1": 23,
        "icons_2": 24,
        "icons_3": 25,
        "icons_1_desc": 26,
        "icons_2_desc": 27,
        "icons_3_desc": 28,
        "phone_mockup": 29,
        "screen_mockup": 30,
        "paragraph": 53,
        "intro_image": 54,
        "agenda": 52,
        "text_landscape": 250,
        "close": 32,           # Thank you - white
    },
    "gradient": {
        "description": "Gradient accents. Strategic, vision-forward.",
        "title": 2,            # Title Slide - blue gradient
        "section": 5,          # Section title - blue gradient
        "bullets": 12,
        "one_column": 13,
        "two_column": 15,
        "text_image": 16,
        "large_image": 17,
        "quote": 10,
        "emphasis": 18,
        "emphasis_2col": 20,
        "icons_1": 23,
        "icons_2": 24,
        "icons_3": 25,
        "icons_1_desc": 26,
        "icons_2_desc": 27,
        "icons_3_desc": 28,
        "phone_mockup": 29,
        "screen_mockup": 30,
        "paragraph": 53,
        "intro_image": 54,
        "agenda": 52,
        "text_landscape": 250,
        "close": 31,
    },
}

# Template → design style auto-mapping
TEMPLATE_STYLE_MAP = {
    "Board / Executive": "executive_blue",
    "Internal / Strategy": "gradient",
    "QBR / Business Review": "executive_blue",
    "CS All Hands": "clean_white",
}

# Default slide type sequences per template — designed for visual variety
TEMPLATE_SEQUENCES = {
    "Board / Executive": [
        "title", "section", "bullets", "two_column", "emphasis",
        "section", "icons_3", "bullets", "text_image",
        "section", "bullets", "close"
    ],
    "Internal / Strategy": [
        "title", "section", "paragraph", "icons_3_desc",
        "two_column", "section", "text_image", "bullets",
        "emphasis", "section", "icons_2", "close"
    ],
    "QBR / Business Review": [
        "title", "section", "bullets", "two_column",
        "emphasis", "icons_2", "section", "text_image",
        "bullets", "emphasis_2col", "section", "close"
    ],
    "CS All Hands": [
        "title", "section", "bullets", "icons_3",
        "paragraph", "quote", "section", "text_image",
        "icons_2_desc", "bullets", "section", "close"
    ],
}


class DeckConfig(BaseModel):
    """Full configuration for generating a presentation deck."""
    title: str = "Untitled Deck"
    template: str = "Board / Executive"
    audience: str = "Board"
    tone: str = "Executive — concise, data-forward"
    purpose: str = ""
    products: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    industry: Optional[str] = None
    key_messages: list[str] = Field(default_factory=list)
    slide_count: str = "10-15"
    design_style: Optional[str] = None  # Override: "executive_blue" | "clean_white" | "gradient"
    slide_sequence: Optional[list[str]] = None  # Override: ["title", "section", "bullets", ...]
    content: ContentInput = Field(default_factory=ContentInput)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    additional_context: str = ""
    auto_research: bool = True
    auto_media: bool = False  # Default off — user must opt in
    enable_critique: bool = True

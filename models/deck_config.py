"""Pydantic models for deck configuration and generation."""

from typing import Optional
from pydantic import BaseModel, Field


class DataQuery(BaseModel):
    """A query against a Domo dataset for data-driven slides."""
    dataset_id: str
    query: str  # SQL or metric name


class ThemeConfig(BaseModel):
    """Theme overrides within brand guidelines."""
    primary_color: str = "#99CCEE"
    accent_color: str = "#FF9922"
    background_style: str = "white"  # white | blue | gradient | dark
    font_family: str = "Open Sans"  # enforced — always Open Sans


class ManualContent(BaseModel):
    """User-provided content for a specific slide."""
    headline: Optional[str] = None
    subheadline: Optional[str] = None
    body: Optional[str] = None
    bullets: Optional[list[str]] = None
    speaker_notes: Optional[str] = None


class SlideConfig(BaseModel):
    """Configuration for a single slide."""
    position: int
    layout_id: int  # Maps to LAYOUTS from the deck builder
    layout_type: str = "bullets"  # title | section | bullets | two_column | quote | icons | image | close
    content_source: str = "auto"  # auto | manual | asset
    manual_content: Optional[ManualContent] = None
    asset_ids: Optional[list[str]] = None
    media_prompt: Optional[str] = None  # Custom prompt for AI image generation
    data_source: Optional[DataQuery] = None


# Slide layout definitions (ported from deck builder JSX)
LAYOUTS = {
    0:  {"label": "Title — Blue",       "type": "title",      "use": "Board/Executive opener"},
    1:  {"label": "Title — White",      "type": "title",      "use": "Sales/Customer opener"},
    2:  {"label": "Title — Gradient",   "type": "title",      "use": "Internal/Strategy opener"},
    3:  {"label": "Section — Blue",     "type": "section",    "use": "Chapter break (executive)"},
    4:  {"label": "Section — White",    "type": "section",    "use": "Chapter break (sales)"},
    5:  {"label": "Section — Gradient", "type": "section",    "use": "Chapter break (strategy)"},
    10: {"label": "Quote — Blue",       "type": "quote",      "use": "Key statement, exec emphasis"},
    11: {"label": "Quote — White",      "type": "quote",      "use": "Testimonial, customer voice"},
    12: {"label": "Bullets",            "type": "bullets",    "use": "Main workhorse — 4-5 bullets"},
    13: {"label": "1-Column",           "type": "one_column", "use": "Single narrative paragraph"},
    14: {"label": "2-Column",           "type": "two_column", "use": "Side-by-side comparison"},
    16: {"label": "Text + Image",       "type": "text_image", "use": "Content with supporting visual"},
    17: {"label": "Large Photo",        "type": "image",      "use": "Visual-led with caption"},
    22: {"label": "Bullets — Blue",     "type": "bullets",    "use": "Strategic emphasis slide"},
    23: {"label": "2-Col Blue",         "type": "two_column", "use": "Two-column blue emphasis"},
    27: {"label": "1 Icon",             "type": "icons",      "use": "Single feature / value prop"},
    28: {"label": "2 Icons",            "type": "icons",      "use": "Two pillars / features"},
    29: {"label": "3 Icons",            "type": "icons",      "use": "Three steps / value props"},
    35: {"label": "Close — Blue",       "type": "close",      "use": "Thank you / closing"},
    36: {"label": "Close — White",      "type": "close",      "use": "Thank you / closing (light)"},
}

# Template presets
TEMPLATE_PRESETS = {
    "Board / Executive": {
        "file": "domo_board_template.pptx",
        "default_layouts": [0, 3, 12, 14, 3, 12, 12, 12, 12, 3, 12, 35],
        "tone_default": "Executive — concise, data-forward",
        "audience_default": "Board",
        "slide_suggestion": "10-15",
        "notes": "Match CS Board template exactly. Light sidebar bar, blue accent headers (ALL CAPS), Domo logo top-left, CONFIDENTIAL footer, page numbers. One idea per slide.",
    },
    "Internal / Strategy": {
        "file": "domo_default_template.pptx",
        "default_layouts": [2, 5, 12, 12, 28, 14, 12, 12, 3, 12, 35],
        "tone_default": "Strategic — vision + rationale",
        "audience_default": "Executive",
        "slide_suggestion": "10-15",
        "notes": "Use gradient section breaks. 2-column layouts for compare/contrast. Icon slides for pillars.",
    },
    "QBR / Business Review": {
        "file": "domo_default_template.pptx",
        "default_layouts": [0, 3, 12, 14, 12, 22, 3, 12, 12, 23, 12, 35],
        "tone_default": "Analytical — evidence-heavy",
        "audience_default": "Executive",
        "slide_suggestion": "15-20",
        "notes": "Lead with scorecard. Use 2-col for period-over-period. Blue emphasis for risks/wins.",
    },
    "CS All Hands": {
        "file": "domo_default_template.pptx",
        "default_layouts": [1, 4, 12, 29, 12, 10, 12, 3, 12, 28, 12, 36],
        "tone_default": "Narrative — story-driven",
        "audience_default": "CS Team",
        "slide_suggestion": "15-20",
        "notes": "Use icon slides for initiatives. Quotes for recognition moments. White close for warmth.",
    },
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
    slides: Optional[list[SlideConfig]] = None  # None = auto-generate from template
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    uploaded_files: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    fileset_ids: list[str] = Field(default_factory=list)
    dataset_queries: list[DataQuery] = Field(default_factory=list)
    additional_context: str = ""
    auto_research: bool = True
    auto_media: bool = True

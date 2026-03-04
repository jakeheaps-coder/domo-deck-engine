# Domo AI Deck Engine — Full System Plan

## Context

The current Deck Builder (`domo-deck-builder_1.jsx`) is a prompt configurator only — it builds a text prompt for a "domo-powerpoint skill" but doesn't actually generate anything. Jake needs an end-to-end AI presentation system that:
- **Researches** content automatically (KG API, Domo data, FileSets)
- **Generates** branded .pptx files with real content, data, and custom graphics
- **Manages** reusable assets, templates, and saved designs
- **Minimizes** manual editing by getting it right the first time

## Key Decisions
- **FileSets**: Create NEW purpose-built FileSets (not reuse existing)
- **UI**: Standalone Next.js on Cloud Run + thin Domo Custom App iframe wrapper
- **Build order**: Backend engine first (MVP), then UI
- **Backend**: Flask/Python on Cloud Run (required for python-pptx, Gemini, KG API)

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│            DECK BUILDER UI                      │
│         (Next.js on Cloud Run)                  │
│   Template → Research → Slides → Generate       │
│                                                 │
│   Also accessible via Domo Custom App (iframe)  │
└──────────────────┬──────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────┐
│          DECK ENGINE API                        │
│         (Flask on Cloud Run)                    │
│                                                 │
│  Orchestrator                                   │
│    ├── Researcher (KG API + Domo FileSets)      │
│    ├── Content Writer (Gemini 3.1 Pro)          │
│    ├── Media Generator (Gemini 3 Pro Image)     │
│    ├── Slide Builder (python-pptx)              │
│    └── Validator (KG Cascade)                   │
└──────────────────┬──────────────────────────────┘
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌───────┐ ┌──────────┐
   │  KG API │ │Gemini │ │Domo      │
   │(exists) │ │  API  │ │FileSets  │
   └─────────┘ └───────┘ │+Datasets │
                          └──────────┘
```

---

## Domo FileSets Strategy

Create purpose-built FileSets in Domo for the deck engine to pull from:

| FileSet | Purpose | Contents |
|---------|---------|----------|
| **Deck Templates** | Master .pptx templates | Board template, Strategy template, Sales template, QBR template |
| **Brand Assets** | Logos, icons, approved graphics | Domo logos (blue/white/dark), product icons, approved stock photos |
| **Past Decks** | Reference library of completed decks | Best-of archive — engine can learn structure/tone from these |
| **Data Snapshots** | Pre-built data visualizations | Chart exports, scorecard images, dashboard screenshots |
| **Content Library** | Approved copy blocks, case studies | Customer stories, proof points, stat callouts, boilerplate |

These are NEW, dedicated FileSets — separate from existing ones like "Domo Knowledgebase Extract" to keep deck assets clean and purpose-built.

The engine queries these via the Domo FileSet API + `FileSetQueryTool` for semantic search across all stored content.

---

## Input Model (What the User Provides)

```
DeckConfig {
  title: string                    // "CS Board Update - 1Q FY27"
  template: string                 // "Board / Executive" | "Internal / Strategy" | etc.
  audience: string                 // "Board" | "Executive" | "Sales" | "CS Team"
  tone: string                     // "Executive" | "Narrative" | "Strategic" | "Analytical"
  purpose: string                  // Free text: what this deck is about
  products: string[]               // Domo products to feature (auto-suggested from KG)
  competitors: string[]            // Competitors to address
  industry: string                 // Target industry
  key_messages: string[]           // Up to 5 key points to hit
  slide_count: string              // "5-8" | "10-15" | "15-20" | "20+"
  slides: SlideConfig[]            // Per-slide overrides (optional)
  theme: ThemeOverrides            // Color/style within brand (optional)
  uploaded_files: File[]           // Source docs to extract content from
  asset_ids: string[]              // Saved assets to include
  fileset_ids: string[]            // Domo FileSets to pull from
  dataset_queries: DataQuery[]     // Domo dataset queries for data slides
  additional_context: string       // Free text notes
  auto_research: boolean           // Pull KG data automatically (default: true)
  auto_media: boolean              // Generate images per slide (default: true)
}
```

---

## Generation Pipeline (What Happens After "Generate")

### Step 1: Research (5-10s)
- Query KG `/api/messaging` with audience + industry context
- Query KG `/api/products/{name}/profile` for each product
- Query KG `/api/competitors/{name}` for competitive slides
- Query Domo FileSets for relevant content (semantic search via FileSetQueryTool)
- If uploaded files provided, extract text content
- Output: `ResearchPackage` with messaging, data, proof points, competitive intel

### Step 2: Content Writing (10-15s)
- Send ResearchPackage + DeckConfig to Gemini 3.1 Pro
- Gemini returns structured JSON: per-slide headline, bullets, narrative, speaker notes
- System prompt enforces: Domo voice, audience-appropriate tone, one idea per slide
- Run cascade validation on all Domo-specific claims
- Output: `SlideContent[]` — complete content for every slide

### Step 3: Media Generation (15-30s, parallel)
- For each slide that needs a custom graphic:
  - Build brand-aware prompt: "Professional business graphic. Color palette: #99CCEE, #FF9922, #3F454D. Clean, modern. No purple gradients. [slide-specific description]"
  - Call `generate_image()` at 16:9 aspect ratio, 2K resolution
  - Store image in temp directory
- Pull any user-selected assets from Domo FileSets or saved library
- Output: Image files mapped to slide positions

### Step 4: Assembly (5-10s)
- Load .pptx template from Domo FileSet (or local templates)
- For each slide in the sequence:
  - Select correct slide layout from template master
  - Populate placeholders: title, subtitle, body, bullets
  - Insert images into image placeholders
  - Apply formatting: Open Sans, Domo colors, proper spacing
  - Add speaker notes
  - Add footer: logo + page number + confidential notice
- Save .pptx to temp file
- Output: Complete .pptx file ready for download

### Step 5: Delivery
- Return download URL
- Optional: save to Domo FileSet (Past Decks library)
- Optional: email via Domo Code Engine
- Optional: upload to SharePoint via Graph API

**Total time: ~40-60 seconds** for a 15-slide deck with auto-generated images.

---

## Phase 1 — MVP: Backend Engine (Build First)

Build the generation engine as a Cloud Run API. No UI yet — test via curl/Postman and from Claude Code directly.

### Files to Create

```
~/ai_projects/domo-deck-engine/
├── app.py                         # Flask routes
├── config.py                      # Env config, constants
├── requirements.txt               # Dependencies
├── Dockerfile                     # Cloud Run container
├── .env / .env.example
│
├── engine/
│   ├── orchestrator.py            # Main pipeline coordinator
│   ├── researcher.py              # KG API + FileSet research
│   ├── content_writer.py          # Gemini slide content generation
│   ├── media_generator.py         # Brand-aware image generation
│   ├── slide_builder.py           # python-pptx assembly
│   └── validator.py               # Cascade validation
│
├── models/
│   └── deck_config.py             # Pydantic models
│
├── templates/                     # Starter .pptx templates
│   ├── domo_board_template.pptx
│   ├── domo_default_template.pptx
│   └── domo_sales_template.pptx
│
├── assets/                        # Static brand assets
│   ├── domo_logo_blue.png
│   └── domo_logo_white.png
│
└── helpers/                       # Copied from shared toolkit
    ├── kg_api_helper.py
    ├── gemini_helper.py
    └── media_generation_helper.py
```

### API Endpoints (MVP)

| Method | Endpoint | What it does |
|--------|----------|-------------|
| POST | `/api/decks/generate` | Full pipeline → returns job ID |
| GET | `/api/decks/{job_id}/status` | Poll generation progress |
| GET | `/api/decks/{job_id}/download` | Download completed .pptx |
| POST | `/api/research/preview` | Run research only, return results |
| POST | `/api/content/preview` | Generate content for one slide |
| POST | `/api/media/generate` | Generate one image |

### Existing Code to Reuse

| Source File | Reuse As | What We Take |
|-------------|----------|-------------|
| `automations/weekly_executive_report/writers/pptx_writer.py` | `engine/slide_builder.py` | `_duplicate_slide()`, `_replace_text_preserve_format()`, layout logic, Domo colors |
| `shared/domo-toolkit/helpers/kg_api_helper.py` | `helpers/kg_api_helper.py` | All KG API functions |
| `shared/domo-toolkit/helpers/media_generation_helper.py` | `helpers/media_generation_helper.py` | `generate_image()`, `edit_image()` |
| `shared/domo-toolkit/helpers/gemini_helper.py` | `helpers/gemini_helper.py` | `generate_content()`, `generate_structured()` |
| `Downloads/domo-deck-builder_1.jsx` | Data models | TEMPLATES{}, LAYOUTS[], template configs |

### Deploy

```bash
gcloud run deploy deck-engine-api \
  --source ~/ai_projects/domo-deck-engine \
  --region us-central1 \
  --memory 2Gi --cpu 2 \
  --timeout 300 \
  --project domo-marketing
```

---

## Phase 2 — Front-End: Deck Builder UI

Next.js app with 5-step wizard, deployed to Cloud Run. Plus a thin Domo Custom App (iframe wrapper) so it's accessible inside Domo.

### Steps

1. **Template** — Pick template, audience, tone, purpose (ported from existing JSX)
2. **Research** — Auto-research preview from KG + FileSets. User reviews/edits messaging, data points, proof points before generation. Can add products, competitors, industry.
3. **Slides** — Per-slide configuration. Drag to reorder. Pick layouts. Override content per slide. Assign assets. Add data queries.
4. **Media & Assets** — Browse saved assets from Domo FileSets. Upload new assets. Generate AI images per slide. Preview all media.
5. **Review & Generate** — Full slide-by-slide preview. Hit Generate. Progress bar. Download .pptx.

### Key UX Decisions
- **Open Sans font** throughout (existing JSX uses DM Sans + Syne — not brand-compliant)
- **Domo Blue (#99CCEE) primary**, Orange (#FF9922) for CTAs
- Dark theme is fine for the builder UI (matches existing design)
- Live slide thumbnails update as user configures

### Deployment: Hybrid
1. **Primary**: Next.js app on Cloud Run (`deck-builder-ui` service)
2. **Domo wrapper**: Thin Custom App (~20 lines) that iframes the Cloud Run URL
   - Passes Domo auth token via postMessage
   - Lives in Domo workspace for easy team access
   - `manifest.json` + single `index.html` with iframe

### Project Structure

```
~/ai_projects/domo-deck-builder/
├── src/
│   ├── app/
│   │   ├── page.tsx               # Dashboard: recent decks, start new
│   │   ├── builder/page.tsx       # Main 5-step wizard
│   │   ├── assets/page.tsx        # Asset library management
│   │   └── layout.tsx             # Shell with DomoHeader
│   ├── components/
│   │   ├── wizard/                # Step1-5 + WizardNav
│   │   ├── slides/                # SlidePreview, SlideEditor, SlideGrid
│   │   ├── assets/                # AssetLibrary, AssetUploader, AssetGrid
│   │   ├── research/              # ResearchPanel, ProductCard, MessagingPreview
│   │   ├── media/                 # MediaGenerator, MediaPreview
│   │   └── shared/                # DomoHeader, DomoButton, DomoCard
│   ├── hooks/                     # useDeckConfig, useAssets, useResearch, useGeneration
│   ├── lib/                       # api.ts, brand.ts, types.ts, layouts.ts
│   └── styles/globals.css
├── package.json
├── Dockerfile
└── next.config.ts

~/ai_projects/domo-deck-builder-domo-app/    # Thin iframe wrapper
├── manifest.json
├── index.html                     # <iframe src="https://deck-builder-ui-*.run.app">
└── app.js                         # Domo auth token passthrough
```

---

## Phase 3 — Asset Management + Domo FileSets

### New FileSets to Create in Domo
1. **"Deck Templates"** — Upload master .pptx templates
2. **"Brand Assets"** — Logos, icons, approved images
3. **"Past Decks"** — Archive of generated decks for reference
4. **"Content Library"** — Approved copy blocks, case studies, stat callouts
5. **"Data Snapshots"** — Exported chart images, scorecard screenshots

### Asset Library Features
- Browse all FileSets from a unified panel
- Upload new assets → routes to correct FileSet
- Tag assets (logo, icon, chart, background, photo)
- Search across all FileSets (semantic via FileSetQueryTool)
- Drag asset onto a slide in the builder
- "Saved Designs" — save a completed deck config as a reusable starting point

### API Additions

| Method | Endpoint | What it does |
|--------|----------|-------------|
| GET | `/api/assets` | List assets across FileSets (with filters) |
| POST | `/api/assets/upload` | Upload to specific FileSet |
| GET | `/api/assets/search` | Semantic search via FileSetQueryTool |
| GET | `/api/templates` | List available .pptx templates |
| POST | `/api/templates` | Upload custom template |
| GET | `/api/designs` | List saved deck configs |
| POST | `/api/designs` | Save current config as reusable design |

---

## Phase 4 — Advanced Features (Future)

- **PDF export** — LibreOffice headless in container
- **SharePoint delivery** — Save to SP folder via Graph API
- **Domo dataset integration** — Live data on chart slides (query via Code Engine)
- **Slide-level AI rewrite** — "Make this more executive", "Add data to this slide"
- **Animation presets** — Entrance/exit animations in .pptx
- **Video slides** — Veo 3.1 for motion backgrounds
- **Deck versioning** — Track revisions, diff between versions
- **Team sharing** — Share decks/designs across team via Domo

---

## Verification Plan

### Phase 1 Testing
1. `curl -X POST /api/decks/generate` with a Board template config → verify .pptx downloads
2. Open .pptx in PowerPoint → verify: correct template, Open Sans font, Domo colors, KG-sourced content, generated images placed correctly
3. Test all 4 templates produce distinct, correctly branded outputs
4. Test with uploaded source files (DOCX, PDF) → content extracted into slides
5. Test cascade validation catches incorrect Domo claims

### Phase 2 Testing
1. Walk through all 5 wizard steps in browser
2. Verify research preview shows real KG data
3. Verify slide reordering and layout changes
4. Generate + download flow completes end-to-end
5. Mobile responsive check

### Phase 3 Testing
1. Upload asset → appears in library
2. Search assets → returns relevant results
3. Drag asset onto slide → appears in preview and generated .pptx
4. Save design → reload → design restores correctly
5. FileSet queries return content from all configured FileSets

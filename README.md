# NovelApp – End‑to‑End Coherent Novel Generation

## Note from author:
> This project was one of my first attempts at learning how to integrate AI into web applications and taking a crack at prompt engineering. It's pretty basic, but it was fun to build. No license, if you find it useful in part or in full feel free to use it. It isn't perfect, it could use some tighter engineering. For a minute I considered launching it and improving it, which is why it has complete systems for pricing, but hey, I'm bored of it now.

## Overview
This repository contains a Flask application that generates long‑form fiction by moving through a structured pipeline: **metadata → outlines → arcs → chapter guides → prose → images**. It combines Flask + SQLAlchemy + Celery + Redis + Socket.IO on the backend with OpenAI models for text and image generation, and stores assets in S3‑compatible object storage.

Below is a practical, code‑accurate overview of how the system works, followed by setup instructions. The original README content is preserved at the end under **Quick Start (from original README)**.

---

## How it works (end to end)

### 0) Create a story
Users create a `Story` (title, details, tags, inspirations, writing_style, chapters_count). This yields empty `Chapter` rows and initializes the authoring flow (see `models/Story.py`, `views/story.py`).

### 1) Metadata (characters & locations)
- **Prompt builder:** `build_meta_prompt(...)` in `prompt_templates.py` wraps inputs in XML‑like scaffolding and asks for **strict JSON** with two arrays: `characters` and `locations` (each character includes `name`, `description`, and `example_dialogue`).
- **Generation:** `generate_meta_from_prompt(...)` in `openai_handler.py` calls `gpt-4o-mini`.
- **Persistence:** Results are parsed into `Character` and `Location` rows; a `GenerationLog` entry captures predicted vs. real cost + tokens.
- **Why this helps coherence:** consistent **entity memory** (names, voices, example dialogue) and **setting memory** (location descriptions) are fed into every later prompt.

### 2) Chapter summaries (book‑level outline)
- **Prompt builder:** `build_chapter_summaries_prompt(...)` requests a JSON **array** of chapters (`title`, `summary`) using the metadata above, overall arcs (if any), and target `total_chapters`.
- **Generation:** `generate_chapter_summaries_from_prompt(...)` with model `o1-mini`.
- **Persistence:** Populates `Chapter.title` and `Chapter.summary` across the book.
- **Why this helps coherence:** forces a **top‑down outline** so later steps keep consistent pacing and plot logic.

### 3) Story arcs (global)
- **Prompt builder:** `build_story_arcs_prompt(...)` converts chapter list + summaries + metadata into **high‑level arcs** for the whole book.
- **Generation:** `generate_story_arcs_from_prompt(...)` with `o1-mini`.
- **Persistence:** Saves `StoryArc` rows (`arc_text`, `arc_order`), giving you a spine that the chapter guides can reference.
- **Why this helps coherence:** injects an **across‑chapters throughline** that keeps stakes and themes progressing.

### 4) Chapter guides (beat sheets per chapter)
- **Prompt builder:** `build_chapter_guide_prompt(...)` expands each chapter into a list of **arc parts** (beats). Each part can be annotated with **characters** and **locations** used.
- **Generation:** `generate_chapter_guide_from_prompt(...)` with `o1-mini`.
- **Persistence:** `ChapterGuide` rows (`story_id`, `chapter_title`, `part_index`, `part_text`, `characters`, `locations`).
- **Why this helps coherence:** gives the prose step a **scene‑level plan**, preventing meandering chapters.

### 5) Prose drafting (one chapter at a time, markdown)
- **Prompt builder:** `build_chapter_content_prompt(...)` includes:
  - Chapter title and **current chapter summary**
  - **Previous** and **next** chapter summaries (a small sliding window for continuity)
  - Global **details/tags/inspirations/writing_style**
  - **Character** and **location** mappings (including example dialogue snippets)
  - The **chapter’s arc parts** from the guide
- **Generation:** `generate_chapter_content_from_prompt(...)` with `o1-mini`; returns Markdown chapter text.
- **Why this helps coherence:** the prose always sees what came before/after and stays faithful to the character voices and the beat sheet.

### 6) Images (optional cover / chapter art)
- **Generation:** `generate_image_from_prompt(...)` uses `dall-e-3` and stores keys in S3 (see `helpers.get_image_url`).
- **Why this helps coherence:** chapter prompts can echo the scene/characters in the guide so visuals reflect the same canon.

### Async jobs, real‑time updates & locking
- **Background work:** Celery tasks in `tasks.py` do the heavy lifting so the web thread stays responsive.
- **WebSocket events:** Flask‑Socket.IO emits updates like `notification, generation_error, meta_generated, summaries_generated, arcs_generated, chapter_guide_generated, chapter_generated, image_generated` so the UI can show progress/errors live.
- **Single in‑flight task per user:** a **Redis lock** (`generation_lock:<user_id>`) prevents clobbering when a user clicks generate multiple times (see `api/generation.py`).

---

## Prompt design strategies that improve coherence

- **Structured I/O:** Prompts ask for **strict JSON** (for metadata, summaries, guides) and use **XML‑like wrappers**. This reduces parsing errors and keeps later steps machine‑readable.
- **Entity memory:** Characters include **example_dialogue**, and locations include rich descriptions. These are merged into chapter prompts to stabilize **voice** and **setting**.
- **Hierarchical planning:** The system moves from **global → local**: summaries → arcs → per‑chapter beat sheets → prose.
- **Local continuity window:** Chapter generation includes the **previous/next** summaries to smooth transitions and avoid plot amnesia.
- **Beat‑driven drafting:** The `ChapterGuide` breaks a chapter into **parts** with explicit characters/locations, which discourages repetition and keeps scenes purposeful.

---

## Token & credit system (what you pay and why)

The app uses a **credit** abstraction for text and images, backed by per‑million token prices and action‑specific modifiers stored in the database.

### Configuration tables
- **`TokenCostConfig`** (one row):
  - Fields: cost_per_credit, cost_per_1m_input, cost_per_1m_output, o1_cost_per_credit, o1_cost_per_1m_input, o1_cost_per_1m_output, dall_e_price_per_image
  - These determine how many tokens each **credit** buys for **input** vs **output** tokens for standard text models and for the `o1-mini` family, plus the price per `dall-e-3` image.
- **`CreditConfig`** (per action):
  - Defaults (from `app.py`):  
    - `image` (image): modifier = 50
    - `meta_input` (text): modifier = 50
    - `meta_output` (text): modifier = 50
    - `summary_input` (text): modifier = 2
    - `summary_output` (text): modifier = 2
    - `arcs_input` (text): modifier = 2
    - `arcs_output` (text): modifier = 2
    - `chapter_guide_input` (text): modifier = 2
    - `chapter_guide_output` (text): modifier = 2
    - `chapter_input` (text): modifier = 2
    - `chapter_output` (text): modifier = 2

### Cost math (per request)
For each generation step the app:
1. **Estimates input tokens** using `tiktoken` on the composed prompt.
2. Uses `TokenCostConfig` to compute:
   - `input_tokens_per_credit = (credit_cost_dollar * 1_000_000) / cost_per_1m_input`
   - `output_tokens_per_credit = (credit_cost_dollar * 1_000_000) / cost_per_1m_output`
3. Converts tokens → **base credits** (rounding and minimum 1):
   - `base_credit_cost_input = max(1, round(input_tokens / input_tokens_per_credit))`
   - `base_credit_cost_output = max(1, round(predicted_output_tokens / output_tokens_per_credit))`
4. Applies `CreditConfig.modifier` for the step (e.g. `summary_input`, `chapter_output`) to get **modified** costs.
5. **Predicted cost** is shown before enqueueing work; after completion, the app recomputes **actual** cost using the **real output tokens** and charges the user (`helpers.spend_credits`).

**Predicted output tokens** used by default:
- meta: 200
- summaries: 250
- story_arcs: 250
- chapter_guide: 250
- chapter: 300

**Tracking:** Every task writes a `GenerationLog` with `predicted_cost`, `real_cost`, `input_tokens`, `output_tokens`, `model`, and status.

---

## Key components at a glance

- **Framework:** Flask (`app.py`, `views/`, `api/`)
- **DB:** SQLAlchemy models (`models/`) incl. `Story`, `Chapter`, `Character`, `Location`, `StoryArc`, `ChapterGuide`, `GenerationLog`, `TokenCostConfig`, `CreditConfig`
- **Background:** Celery (`tasks.py`) + Redis broker/result backend
- **Realtime:** Flask‑Socket.IO events to user‑scoped rooms
- **AI:** `openai_handler.py` (text via `o1-mini` family, images via `dall-e-3`)
- **Prompts:** `prompt_templates.py` (XML‑style wrappers; JSON outputs)
- **Assets:** S3‑compatible storage via `helpers.get_image_url()`
- **Payments/roles:** `Role`, `CreditPackage`, and Stripe keys in `config.py`

---

## Setup & configuration

> You’ll need: Python 3.10+, Redis, and environment variables for Stripe, OpenAI, and S3‑compatible object storage.

1) **Install dependencies**
```bash
python3 -m venv novelapp
source novelapp/bin/activate
pip install -r requirements.txt
```

2) **Configure `config.py`**  
Set secrets/keys and infra URLs (OpenAI, Stripe, Redis, S3). Example fields:
```python
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "SET_SECURE_PASSWORD_HERE"
SECRET_KEY = "FLASK_SECRET_KEY"
SQLALCHEMY_DATABASE_URI = "sqlite:///novelapp.db"
SQLALCHEMY_TRACK_MODIFICATIONS = False
JWT_SECRET_KEY = "JWT_SECRET_KEY"
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
REGISTRATION_DISABLED = False
MAINTENANCE_MODE = False
# Stripe (dev/prod blocks provided in config.py)
# OpenAI
OPENAI_API_KEY = "OPEN_API_KEY"
# S3 / compatible object storage
S3_IMAGE_BUCKET = "BUCKET_NAME"
S3_ENDPOINT = "BUCKET_URL"
S3_REGION = "BUCKET_REGION"
S3_IMAGE_ACCESS_KEY_ID = "BUCKET_ACCESS_KEY_ID"
S3_IMAGE_SECRET_KEY = "BUCKET_SECRET_KEY"
```

3) **Run the web app**
```bash
env=development python app.py
```

4) **Run the worker**
```bash
celery -A tasks.celery_app worker --loglevel=info
```

5) **Verify Redis**
```bash
redis-cli ping  # -> PONG
```

6) **Login**  
Open http://localhost:5000 and sign in with the admin credentials you set in `config.py` (defaults are seeded from `app.py` on first run).

---

## Operational notes

- The app seeds **`CreditConfig`** defaults and a minimal role set on first launch.
- User credit checks happen **before** queueing tasks; actual spend occurs **after** generation using measured tokens.
- To prevent duplicate tasks, a **Redis lock** is set per user while a generation is in progress.
- Socket.IO events (e.g., `"meta_generated"`, `"summaries_generated"`, `"chapter_generated"`) let the UI update in real time.

---

## Quick Start (from original README)

# example.com novel writing applicaiton

# SETUP

## Configure your API keys and passwords and other configuration requirements such as mailgun API in config.py
```
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "SET_SECURE_PASSWORD_HERE"
SECRET_KEY = "FLASK_SECRET_KEY"
SQLALCHEMY_DATABASE_URI = "sqlite:///novelapp.db"
SQLALCHEMY_TRACK_MODIFICATIONS = False
JWT_SECRET_KEY = "JWT_SECRET_KEY"
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
REGISTRATION_DISABLED = False
MAINTENANCE_MODE = False
MAILGUN_DOMAIN = "MG_DOMAIN"
MAILGUN_API_KEY = "MG_API_KEY"
MAILGUN_FROM_EMAIL = "MG_EMAIL"
if env == "development":
    STRIPE_SECRET_KEY = "DEV_STRIPE_SECRET_KEY"
    STRIPE_WEBHOOK_SECRET = "DEV_STRIPE_WEBHOOK_SECRET"
    STRIPE_PUBLISHABLE_KEY = "DEV_STRIPE_PUBLISHABLE_KEY"
else:
    STRIPE_SECRET_KEY="PROD_STRIPE_SECRET_KEY"
    STRIPE_WEBHOOK_SECRET="PROD_STRIPE_WEBHOOK_SECRET"
    STRIPE_PUBLISHABLE_KEY="PROD_STRIPE_PUBLISHABLE_KEY"
OPENAI_API_KEY = "OPEN_API_KEY"
S3_IMAGE_BUCKET = "BUCKET_NAME"
S3_ENDPOINT = "BUCKET_URL"
S3_REGION = "BUCKET_REGION"
S3_IMAGE_ACCESS_KEY_ID = "BUCKET_ACCESS_KEY_ID"
S3_IMAGE_SECRET_KEY = "BUCKET_SECRET_KEY"
```

## Install and run the applicaiton
```
apt install redis-server python3 python3-venv python3-pip

redis-cli ping
> pong
python3 -m venv novelapp
source novelapp/bin/activate
pip3 install -r requirements.txt
env=development python3 app.py

# in a separate terminal
source novelapp/bin/activate
celery -A tasks.celery_app worker --loglevel=info
```

navigate to http://localhost:5000 and login with creds from `app.py`


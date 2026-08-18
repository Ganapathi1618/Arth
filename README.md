# Arth

Educational PDF translator for English, Telugu and Hindi. Rebuilds the original
document in place instead of generating a new one, so tables, diagrams, page
geometry and vector rules survive translation.

All six directions are supported: en↔te, en↔hi, te↔hi.

---

## How it works

The core decision is that **we never create a new PDF**. We open the original,
cover each text block with a redaction, and write translated text back into the
exact same rectangle.

```
source.pdf
  ├─ inspect()   page count, text layer, multi-column detection
  ├─ extract()   text blocks + table cells, with bbox / size / weight / colour
  ├─ translate() masked segments, batched, provider-agnostic
  └─ rebuild()   redact original glyphs, insert translated text into same bbox
translated.pdf
```

Images, diagrams and table borders are never touched, because they are never
removed. Only glyphs are replaced.

### Why `insert_htmlbox`

Telugu and Devanagari need OpenType shaping (conjuncts, matras, reordering).
PyMuPDF's `insert_htmlbox` runs a real layout engine, so it handles shaping
*and* word wrapping inside a fixed rectangle. `insert_text` does not wrap and is
unsafe for text that expands. This was verified before any other code was
written — see "Verified findings" below.

### Text expansion

Telugu runs roughly 35% longer than English, Hindi roughly 25%. `rebuild()`
steps the font size down in 0.5px increments until the text fits its original
box. Anything that still overflows at 5px is reported back to the UI as an
`overflow_pages` warning rather than silently clipped.

### Tables

`page.find_tables()` gives cell rectangles. Each cell is extracted and
translated **individually** — without this, `get_text()` merges a whole row into
one block and translated text spills across the column rules. Cell rectangles
are never expanded during rebuild for the same reason.

### Protected segments

Equations, chemical formulae, measurements with units and numeric expressions
are masked with sentinels before translation and restored afterwards, so
`6CO₂ + 6H₂O → C₆H₁₂O₆` is never mangled. See `PROTECT` in `translator.py`.

---

## Setup

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Fonts must be present in `backend/fonts/`. From the repo root:

```bash
./scripts/fetch_fonts.sh
```

This fetches `NotoSans.ttf`, `NotoSansTelugu.ttf` and `NotoSansDevanagari.ttf`
from google/fonts. Without them, Telugu and Hindi render as empty boxes.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000

---

## Environment variables

| Variable | Where | Default | Notes |
| --- | --- | --- | --- |
| `TRANSLATION_PROVIDER` | backend | `mock` | `mock` or `claude` |
| `ANTHROPIC_API_KEY` | backend | — | Required when provider is `claude` |
| `NEXT_PUBLIC_API_URL` | frontend | `http://localhost:8000` | Backend origin |

`mock` generates target-language filler at realistic expansion ratios. It
exercises the layout and overflow logic with zero API spend — use it for all
layout work.

`claude` translates through the Claude API (`claude-opus-5`). Segments are sent
in groups of 20 rather than one per request, so the model sees the surrounding
page context — a heading and the paragraph under it agree in register, and a
table column stays consistent down its rows. The response is constrained to a
JSON schema keyed by segment id, so a translation can never be misaligned to
the wrong box. A chunk that fails three times falls open and keeps the original
text rather than blanking the page.

---

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/upload` | Validate PDF, return page count and layout warnings |
| `GET` | `/api/translate/{job_id}?source=&target=` | SSE progress stream |
| `GET` | `/api/download/{job_id}` | Translated PDF |
| `GET` | `/api/preview/{job_id}/{source\|translated}` | Inline preview |
| `GET` | `/api/health` | Liveness |

SSE stages: `extracting`, `structure`, `translating` (carries `progress`),
`rebuilding`, `finalizing`, then `done` or `error`.

Output filenames follow `{original}_{src}_to_{tgt}.pdf`, e.g.
`biology_chapter_5_en_to_te.pdf`.

---

## Verified findings

Tested against a synthetic NCERT-style page (heading hierarchy, body paragraph,
chemical equation, 4×3 bordered table, vector diagram, numbered questions,
footer).

| Element | Result |
| --- | --- |
| Telugu glyph shaping | Correct — conjuncts and matras render properly |
| Devanagari glyph shaping | Correct |
| Page size and order | Preserved |
| Heading hierarchy and weight | Preserved |
| Table borders | Preserved — vector rules untouched |
| Table cell boundaries | Preserved after per-cell extraction |
| Vector diagram | Preserved |
| Header / footer position | Preserved |
| Font auto-shrink on expansion | Working |

---

## Deployment

### Backend — Railway, Render, or Fly

A `Dockerfile` is included. The container installs dependencies and copies
`app/` and `fonts/`.

```bash
cd backend
docker build -t arth-api .
docker run -p 8000:8000 -e TRANSLATION_PROVIDER=claude -e ANTHROPIC_API_KEY=... arth-api
```

Set on the host: `TRANSLATION_PROVIDER=claude`, `ANTHROPIC_API_KEY`. The service
binds `$PORT`, which Railway and Render inject automatically.

Update `allow_origins` in `app/main.py` to the deployed frontend origin before
going live — it is currently pinned to `http://localhost:3000`.

**Note on temp storage.** Jobs write to `backend/tmp/` on local disk and are held
in an in-memory dict. This works on a single instance. Before scaling to more
than one, move job state to Redis and files to object storage, or requests will
hit an instance that doesn't have the file.

### Both services — Vercel

The repo has two services at its root, so Vercel needs a root `vercel.json`
declaring them. `services` builds each one separately and top-level `rewrites`
decide which handles a request:

```json
{
  "services": {
    "web": { "root": "frontend/", "framework": "nextjs" },
    "api": { "root": "backend/",  "framework": "fastapi", "entrypoint": "app.main:app" }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "api" } },
    { "source": "/(.*)",     "destination": { "service": "web" } }
  ]
}
```

Services are internal unless a rewrite exposes them, and both end up on one
origin — so the frontend calls `/api/...` relative and `NEXT_PUBLIC_API_URL` is
left unset in production. It is only needed for local dev, where the two run on
different ports.

The `api` service runs `scripts/fetch_fonts.sh` during install, because
`backend/fonts/*.ttf` is gitignored and PyMuPDF renders Telugu and Devanagari as
empty boxes without it.

> **This deploys, but do not treat it as production.** Jobs live in an
> in-process dict and files are written to `backend/tmp/` on local disk, so
> `/api/upload` and the `/api/translate/{job_id}` stream that follows it are not
> guaranteed to land on the same instance — a job created by one request can be
> missing from the next. A 30-page translation also streams SSE for minutes,
> which sits badly with function duration limits. Fine for a preview or a demo;
> for real traffic run the backend as a container (above) and do the Redis +
> object storage work described under "Note on temp storage".

### Before public launch

- Add rate limiting on `/api/upload`
- Move CORS off the localhost default
- Sign download URLs, or add auth
- Set up a scheduled cleanup in case the in-process reaper misses jobs

---

## Repository layout

```
backend/
  app/
    core/config.py        languages, fonts, limits, glossary
    services/
      pdf_engine.py       extract + rebuild — the core of the product
      translator.py       provider interface, Claude, mock, masking
    main.py               FastAPI routes, SSE, job lifecycle
  fonts/                  Noto Sans / Telugu / Devanagari
  Dockerfile
frontend/
  app/page.tsx            the whole flow, single page
docs/
  requirements.md         original client brief
  technical-review.md     the ten pre-build questions, answered
scripts/
  fetch_fonts.sh          font download
tests/
  make_sample.py          builds a synthetic NCERT-style page
  pipeline_test.py        extract to rebuild, renders output to PNG
```

---

## Known limitations

- **Scanned PDFs are rejected.** No OCR in this version. Upload returns 422 with
  a clear message rather than producing an empty document.
- **Multi-column pages** are detected and the user is warned before translating.
  Column order is usually correct but spacing can shift.
- **Merged table cells** may not map cleanly; `find_tables()` treats them as
  separate rectangles.
- **Text inside images** is not translated. The image is left intact rather than
  destroyed.
- **30 page / 25 MB cap.** Jobs run in-process; there is no queue yet.
- **Jobs are in-memory** and expire after one hour. A restart clears them.
  Storage is temporary by design — nothing is retained.

---

## Not built yet

Authentication, user accounts, saved document library, storage quotas and
billing are deliberately out of scope for this version. The job layer is keyed
by `job_id` with no user concept, so adding auth means attaching a `user_id` to
the job record and swapping `TMP_DIR` for object storage — the pipeline itself
does not change.

## Roadmap

1. OCR for scanned English pages (Tesseract), then Hindi, then Telugu
2. Page range selection — cuts translation cost significantly on textbooks
3. `.docx` fallback when PDF reconstruction fails, so a failed job is not a dead end
4. Background queue for documents beyond 30 pages
5. Editable glossary, replacing the hardcoded map in `core/config.py`

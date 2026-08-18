# Technical review

Answers to the ten questions raised in `docs/requirements.md` before build, plus
what changed once the code was actually written and tested.

---

## 1. Which parts are technically difficult?

Layout-preserving reconstruction, by a wide margin. Specifically:

- **Text expansion.** Telugu runs ~35% longer than English, Hindi ~25%.
  Translated text does not fit the space the original occupied.
- **Table cell boundaries.** PDF has no table object. Cells must be inferred.
- **Complex script shaping.** Telugu and Devanagari need OpenType shaping —
  conjuncts, matra reordering. Naive text insertion produces broken glyphs.
- **Multi-column detection.** Columns get merged into one reading order, which
  makes the translation nonsense rather than merely ugly.
- **Telugu OCR.** Tesseract's Telugu model is weak. Errors then compound through
  translation.

## 2. What PDF reconstruction approach?

**In-place rebuild, not regeneration.** Open the original, redact the glyphs,
write translated text back into the same rectangle.

This is the central decision. Images, vector diagrams, table rules and page
geometry survive because they are never removed — only glyphs are replaced. The
alternative (extract everything, build a fresh document) is what generic
translators already do, and it is why they produce unusable output.

Library: **PyMuPDF**, using `insert_htmlbox` rather than `insert_text`.
`insert_htmlbox` runs a real layout engine, so it handles complex-script shaping
*and* word wrapping inside a fixed rectangle. This was verified before any
application code was written.

## 3. How are tables and page layout preserved?

Table borders need no special handling — they are vector drawings and are never
touched.

Cell *contents* do. `page.get_text()` merges an entire table row into one block
spanning all columns; translated text then spills straight across the column
rules. This was observed in testing, not theorised.

Fix: `page.find_tables()` gives cell rectangles. Each cell is extracted and
translated individually, and cell rectangles are never expanded during rebuild.
Non-table blocks get a few px of extra room for taller Indic line boxes; cells
do not.

## 4. How are scanned PDFs handled?

**They are not, in this version.** Upload detects the absence of a text layer and
returns a clear message rather than producing an empty document.

The recommendation is to defer OCR rather than ship it badly. Tesseract handles
English well, Hindi acceptably, Telugu poorly. Shipping unreliable Telugu OCR
would generate support load and erode teacher trust faster than the missing
feature will.

When added, the order should be English → Hindi → Telugu, and scanned pages
should keep the original page image as a background rather than claiming layout
preservation that isn't there.

## 5. Which translation provider?

**The Claude API** (`claude-opus-5`). Segments are batched 20 at a time so the
model sees surrounding page context, and the response is constrained to a JSON
schema keyed by segment id — alignment to the original box is structural, not
something we hope holds. The glossary in `core/config.py` is injected into the
system prompt rather than applied as a post-hoc regex, so educational terms are
translated correctly in context instead of substituted afterwards.

The provider is behind an abstract interface (`Provider` in `translator.py`), so
swapping is a config change. A `MockProvider` ships alongside it — it generates
target-language filler at realistic expansion ratios, so all layout work can be
done at zero API spend and stresses overflow harder than real translation does.

## 6. What should be changed?

- Meter and cap by **pages, not documents**. A 200-page textbook and a 2-page
  worksheet have wildly different costs.
- The glossary should not be a database-backed editable feature yet. A hardcoded
  map applied post-translation covers the real cases at a fraction of the work.
- Equations should be **masked, not translated**. Sentinel substitution before
  the API call and restoration after. Any translator will mangle `6CO₂ + 6H₂O`
  if sent raw.
- Multi-column pages should be **detected and disclosed before** the user
  commits, not silently mangled.

## 7. What was removed from V1?

- OCR and scanned-PDF support
- Editable glossary UI
- Background job queue
- 200-page support (capped at 30)
- Authentication, accounts, saved library, storage quotas

## 8. What is realistically achievable, and what shipped?

Shipped and verified: text-based PDFs, heading hierarchy and weight, paragraphs,
tables with borders and cell boundaries, images, vector diagrams,
headers/footers, alignment, page size and order, Telugu/Devanagari rendering,
font auto-shrink on expansion, SSE progress, graceful errors, preview, download
with correct filenames.

Partial: multi-column pages (detected and disclosed; column order usually
correct, spacing can shift), merged table cells.

Not achievable and not attempted: pixel-perfect parity, reliable Telugu OCR,
translation of text baked into images.

## 9. What could cause output to differ significantly from the original?

- **Text expansion** — mitigated by font auto-shrink, reported via
  `overflow_pages` when it cannot be resolved.
- **Multi-column merge** — detected and disclosed pre-translation.
- **Merged table cells** — `find_tables()` treats them as separate rectangles.
- **Broken embedded font encodings** — extraction returns garbage for some
  PDFs with non-standard encodings. Not yet handled.
- **Text inside images** — untranslated by design; the image is preserved rather
  than destroyed.

## 10. Estimated development time

The pipeline in this repository was built and validated as a working MVP. The
remaining work to production, in priority order:

| Item | Estimate |
| --- | --- |
| Real NCERT PDF testing and fixes | 3–4 days |
| Page range selection | 0.5 day |
| `.docx` fallback on reconstruction failure | 1 day |
| OCR, English only | 2–3 days |
| OCR, Hindi and Telugu | 3–5 days |
| Auth, accounts, storage, quotas | 8–10 days |

Auth and accounts were explicitly out of scope in the original brief
("authentication can be skipped") and are not included in the quoted price.

---

## Test results

Tested against a synthetic NCERT-style page: heading hierarchy, body paragraph,
chemical equation, 4×3 bordered table, vector diagram, numbered questions,
footer. Reproduce with `tests/make_sample.py` and `tests/pipeline_test.py`.

| Element | Result |
| --- | --- |
| Telugu glyph shaping | Correct — conjuncts and matras render properly |
| Devanagari glyph shaping | Correct |
| Page size and order | Preserved |
| Heading hierarchy and weight | Preserved |
| Table borders | Preserved |
| Table cell boundaries | Preserved after per-cell extraction |
| Vector diagram | Preserved |
| Header / footer position | Preserved |
| Font auto-shrink on expansion | Working |
| API error paths (bad file, same language, expired job) | Correct status codes |

**Not yet tested against real NCERT material.** The synthetic page has one clean
table and one vector shape. Real textbooks have merged cells, embedded fonts
with broken encodings and two-column question papers. This is the highest-risk
remaining gap and should be closed before any teacher sees the tool.

## Providers and dependencies

| Purpose | Choice | Notes |
| --- | --- | --- |
| PDF read/write | PyMuPDF 1.28 | AGPL — fine for SaaS, review before redistribution |
| Translation | Claude API (`claude-opus-5`) | Swappable via `Provider` interface |
| API framework | FastAPI | SSE for progress |
| Frontend | Next.js 15, React 19, Tailwind 3 | |
| Fonts | Noto Sans / Telugu / Devanagari | SIL OFL |

## Security posture

Implemented: file type validation by extension and magic bytes, 25 MB and
30-page caps, API keys server-side only, per-job temp directories, jobs expire
after one hour with directory removal, download scoped to job ID, generic
user-facing errors with technical detail retained server-side.

Not implemented: rate limiting, virus scanning, authentication, signed download
URLs. All are needed before public deployment.

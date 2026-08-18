# Arth — working notes

Educational PDF translator, English / Telugu / Hindi, all six directions.
Client project. Fixed scope, fixed price. Read `README.md` for setup.

## The one rule that governs everything

**We never generate a new PDF.** We open the original, redact the glyphs, and
write translated text back into the same rectangle. Images, vector diagrams and
table rules survive because they are never removed.

Any change that moves toward "extract all text → build a fresh document" is
wrong, no matter how much simpler it looks. That approach is what every generic
translator already does badly, and it is the entire reason this product exists.

## Verified constraints — do not re-litigate these

These were tested before the app was written. Changing them will break output.

- **Use `insert_htmlbox`, never `insert_text`.** `insert_htmlbox` runs a real
  layout engine, so it does OpenType shaping for Telugu/Devanagari *and* wraps
  text inside a fixed rect. `insert_text` does neither and will produce broken
  matras and overflowing lines.
- **Table cells must be extracted individually** via `page.find_tables()`.
  `get_text()` merges a whole row into one block spanning all columns, and the
  translated text then spills across the column rules. This was a real bug,
  found and fixed. Do not collapse cell handling back into block handling.
- **Table cell rects must never be expanded during rebuild.** Non-table blocks
  get a few px of breathing room for taller Indic line boxes; cells do not, or
  they cross their borders.
- **Equations and units are masked before translation** and restored after (see
  `PROTECT` in `translator.py`). Any translator will mangle `6CO₂ + 6H₂O` if you
  send it raw.

## Text expansion

Telugu runs ~35% longer than English, Hindi ~25%. `rebuild()` steps font size
down in 0.5px increments until the text fits. Anything still overflowing at 5px
is reported to the UI as `overflow_pages` — surfaced to the user, never silently
clipped. Keep that behaviour: a visible warning is better than a mangled page.

## Development workflow

Always develop with `TRANSLATION_PROVIDER=mock`. The mock generates
target-language filler at realistic expansion ratios, so layout and overflow
logic get exercised at zero API spend — and harder than real translation will.
Only switch to `claude` when testing translation quality specifically.

To check layout changes visually:

```bash
python3 tests/make_sample.py
python3 tests/pipeline_test.py
```

Then open `tests/out_te.png`. **Always look at the rendered image** after
touching `pdf_engine.py`. Layout bugs do not show up in logs — the row-merge bug
above passed every assertion and was only visible in the render.

## Current state

Working: text-based PDFs, headings, paragraphs, tables, images, vector diagrams,
headers/footers, font auto-shrink, SSE progress, error states, preview,
download.

Not built: OCR, auth, accounts, saved library, quotas, billing, background queue.

## Scope discipline

Auth, user accounts, saved documents and storage quotas are **out of scope** for
this version and were quoted as such. The job layer is keyed by `job_id` with no
user concept. Adding auth later means attaching `user_id` to the job record and
swapping `TMP_DIR` for object storage — the pipeline itself does not change.
Do not start building account features into this codebase without a scope
conversation first.

## Priority order

1. Real NCERT PDFs — merged cells, embedded fonts with broken encodings,
   two-column question papers. This is where it will break.
2. Page range selection — cuts translation cost significantly on textbooks.
3. `.docx` fallback when reconstruction fails, so a failed job is not a dead end.
4. OCR for scanned English, then Hindi, then Telugu.

## Style

Python: type hints, dataclasses, no unnecessary abstraction layers.
TypeScript: no `any`, keep the single-page flow single-page.
Error messages are read by teachers, not developers — say what happened and what
to do, never surface a stack trace or "Internal Server Error".

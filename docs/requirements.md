# Original requirements

Client brief as supplied, preserved unedited for handover. Where the delivered
build departs from this document, the reasoning is recorded in
`docs/technical-review.md`.

---

## Target users

School teachers first.

## Core problem

Existing generic PDF translators don't handle educational documents well,
especially: Telugu/Hindi script rendering, tables, equations, images,
multi-column layouts, scanned PDFs, large documents, and preservation of the
original document structure.

This is not a generic translation website. It is a PDF translator specifically
optimised for Indian educational documents.

## Languages

V1 must support exactly three languages: English, Telugu, Hindi.

All six translation directions are required:

- English → Telugu, Telugu → English
- English → Hindi, Hindi → English
- Telugu → Hindi, Hindi → Telugu

The architecture should allow additional Indian languages later.

## Core user flow

Teacher opens website → uploads PDF → system validates PDF → shows file name,
file size and page count → teacher selects source language → teacher selects
target language → clicks Translate → system processes document → shows
processing status → generates translated PDF → teacher previews result →
downloads translated PDF.

Keep the workflow extremely simple.

## Most important requirement

We do **not** want: PDF → extract all text → generate a completely new generic
PDF.

We want: original PDF → identify document structure → translate content →
reconstruct translated PDF → preserve original structure as closely as
technically possible.

Try to preserve: page size, page order, headings, paragraphs, text positioning,
tables, table borders, rows and columns, images, diagrams, equations, headers,
footers, alignment, page breaks, general visual structure.

Pixel-perfect reproduction is not required for V1, but visual similarity and
readability are extremely important.

If exact preservation is impossible for a specific document type, fail
gracefully instead of producing a corrupted PDF.

## Educational translation quality

Translation should be optimised for educational material:

- preserve academic meaning
- use natural educational Telugu/Hindi
- avoid unnecessarily literary language
- handle school terminology correctly
- preserve important scientific and mathematical terminology
- preserve numbers, formulas and symbols

An editable educational glossary should be supported later. Examples:

- Photosynthesis → ఫోటోసింథసిస్
- Hypotenuse → కర్ణం

## Document types to support

Text-based PDFs, textbooks, question papers, worksheets, notes, table-heavy
PDFs, image-heavy PDFs, multi-column PDFs, equation-heavy PDFs, scanned PDFs,
long documents.

## OCR / scanned PDFs

Detect whether the PDF contains a usable text layer. If text exists, extract
directly. If scanned or image-based, use OCR. OCR should eventually support
English, Telugu and Hindi. Do not assume OCR is always perfect.

## Telugu and Hindi rendering

Use proper Unicode-compatible fonts — Noto Sans Telugu or another verified
Unicode Telugu font, and a suitable Unicode Devanagari font.

Prevent: broken glyphs, missing characters, detached vowel signs, incorrect
matras, square boxes, corrupted Unicode.

## Table handling

Preserve rows, columns, borders, cell alignment, table spacing and original
table position.

Because translated text may become longer: wrap text properly, adjust font size
when necessary, prevent overflow, prevent overlap, preserve borders.

## Equations, maths, science

Preserve equations, mathematical symbols, fractions, superscripts, subscripts
and scientific notation. Do not translate mathematical notation incorrectly.

## Images and diagrams

Preserve images and diagrams in their original positions wherever possible. If
an image contains text and translating it is difficult, do not destroy the
image.

## Large PDF support

Should eventually support documents of around 200 pages. For the first
prototype, do not over-engineer. Architecture should allow future background
processing: upload → create job → process in background → show progress →
generate result → download. Do not add unnecessary infrastructure unless
required.

## Progress UI

Show useful processing status: Uploading, Extracting, Detecting structure,
Translating, Rebuilding PDF, Finalizing. Don't leave the user on a frozen
screen.

## Error handling

Show understandable errors: unsupported PDF, file too large, OCR failed,
translation failed, PDF reconstruction failed, unsupported document structure,
temporary processing error.

Do not show only "Internal Server Error". Log technical errors internally.

## Download

After successful processing: Translation Complete, Preview, Download PDF.

Example filenames: `biology_chapter_5_en_to_te.pdf`,
`biology_chapter_5_en_to_hi.pdf`, `biology_chapter_5_te_to_hi.pdf`.

## Preview

Provide a basic preview — ideally original versus translated — so teachers can
quickly verify the output.

## UI

Keep V1 simple. Main flow: upload PDF → choose source language → choose target
language → Translate → processing status → preview → download.

Do **not** build in V1: ERP, social features, chat, teacher community,
complicated analytics, WhatsApp bot, mobile app, unnecessary dashboards.

## Authentication

For the private prototype, authentication can be skipped. Design the
application so authentication can be added later.

## Storage

During development, local storage is fine. For production, secure object
storage can be added. Uploaded documents should not be stored permanently by
default. Design for secure temporary file handling and cleanup.

## Security

Handle: file type validation, file size limits, safe PDF processing, API key
protection, no API keys in frontend, secure temporary files, controlled download
access, rate limiting where appropriate, cleanup of temporary files, safe
handling of uploaded documents.

## Suggested tech stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: Python, FastAPI
- PDF processing: best combination for layout preservation — PyMuPDF, pypdf,
  pdfplumber, or a technically better approach
- OCR: an appropriate OCR solution
- AI/translation: Gemini, OpenAI or another suitable provider, kept replaceable
- Database: none or minimal for prototype; PostgreSQL later if required

## Real educational testing

Use real educational PDFs, not only simple text documents. Test with: English,
Telugu and Hindi textbooks; English, Telugu and Hindi question papers;
worksheet; table-heavy PDF; image-heavy PDF; multi-column PDF; maths/physics
equations; scanned English, Telugu and Hindi PDFs; long PDF.

## MVP success criteria

A real teacher should be able to upload a real educational PDF, select a
language direction, translate, receive a readable translated PDF with acceptable
layout preservation, and download the result.

The most important validation question: *would the teacher prefer this over the
translator they currently use?*

## Development milestones

1. Project setup, PDF upload, PDF validation
2. PDF text extraction, basic translation
3. PDF reconstruction, basic layout preservation
4. Telugu/Hindi fonts, tables, equations, images, page structure
5. OCR / scanned PDF support
6. Testing with real educational documents
7. Teacher feedback and bug fixing

## Developer deliverables

Working web application, frontend source, backend source, GitHub repository,
README, local setup instructions, environment variable documentation,
deployment instructions, dependency list, API/provider list, testing results,
known limitations.

Another developer should be able to take over the project from the repository.

## Main goal

Build a high-quality English/Telugu/Hindi educational PDF translator that
teachers would genuinely prefer over the tools they currently use.

from __future__ import annotations

import asyncio
import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import LANGUAGES, MAX_FILE_MB, MAX_PAGES, TMP_DIR
from app.services import pdf_engine
from app.services.translator import get_provider

app = FastAPI(title="Arth")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: dict[str, dict] = {}
TTL_SECONDS = 3600

STAGES = ["uploading", "extracting", "structure", "translating", "rebuilding", "finalizing"]


def _reap() -> None:
    now = time.time()
    for jid in [j for j, v in JOBS.items() if now - v["created"] > TTL_SECONDS]:
        shutil.rmtree(TMP_DIR / jid, ignore_errors=True)
        JOBS.pop(jid, None)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    _reap()
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    jid = uuid.uuid4().hex[:12]
    job_dir = TMP_DIR / jid
    job_dir.mkdir(parents=True)
    src = job_dir / "source.pdf"

    size = 0
    with src.open("wb") as fh:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_FILE_MB * 1024 * 1024:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise HTTPException(413, f"File is larger than {MAX_FILE_MB} MB.")
            fh.write(chunk)

    if src.read_bytes()[:5] != b"%PDF-":
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, "That file isn't a valid PDF.")

    try:
        info = pdf_engine.inspect(str(src))
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, "This PDF couldn't be opened. It may be encrypted or damaged.")

    if info.pages > MAX_PAGES:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(413, f"This PDF has {info.pages} pages. The limit is {MAX_PAGES}.")

    if not info.has_text_layer:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            422, "This looks like a scanned PDF. Scanned documents aren't supported yet."
        )

    JOBS[jid] = {
        "created": time.time(),
        "dir": job_dir,
        "name": Path(file.filename).stem,
        "stage": None,
        "error": None,
    }

    return {
        "job_id": jid,
        "filename": file.filename,
        "size_mb": round(size / 1024 / 1024, 2),
        "pages": info.pages,
        "multi_column_pages": [p + 1 for p in info.multi_column_pages],
    }


async def _run(jid: str, src_lang: str, tgt_lang: str, queue: asyncio.Queue) -> None:
    job = JOBS[jid]
    src = job["dir"] / "source.pdf"
    out = job["dir"] / "translated.pdf"

    async def emit(stage: str, **kw):
        await queue.put({"stage": stage, **kw})

    try:
        await emit("extracting")
        blocks = await asyncio.to_thread(pdf_engine.extract, str(src))
        if not blocks:
            raise ValueError("No readable text found in this PDF.")

        await emit("structure", blocks=len(blocks))

        provider = get_provider()
        texts = [b.text for b in blocks]
        done = 0
        chunk = 20
        results: list[str] = []
        for i in range(0, len(texts), chunk):
            part = await provider.translate_batch(texts[i : i + chunk], src_lang, tgt_lang)
            results.extend(part)
            done += len(part)
            await emit("translating", progress=round(done / len(texts), 3))

        for b, t in zip(blocks, results):
            b.translated = t

        await emit("rebuilding")
        stats = await asyncio.to_thread(pdf_engine.rebuild, str(src), str(out), blocks, tgt_lang)

        await emit("finalizing")
        name = f"{job['name']}_{src_lang}_to_{tgt_lang}.pdf"
        job["download_name"] = name
        await queue.put(
            {
                "stage": "done",
                "download_url": f"/api/download/{jid}",
                "filename": name,
                "overflow_pages": [p + 1 for p in stats["overflow_pages"]],
            }
        )
    except Exception as exc:  # noqa: BLE001
        job["error"] = repr(exc)
        await queue.put({"stage": "error", "message": _friendly(exc)})
    finally:
        await queue.put(None)


def _friendly(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return str(exc)
    return "Something went wrong while processing this document. Try again in a moment."


@app.get("/api/translate/{jid}")
async def translate(jid: str, source: str, target: str):
    if jid not in JOBS:
        raise HTTPException(404, "This job has expired. Upload the file again.")
    if source not in LANGUAGES or target not in LANGUAGES:
        raise HTTPException(400, "Unsupported language.")
    if source == target:
        raise HTTPException(400, "Source and target languages are the same.")

    queue: asyncio.Queue = asyncio.Queue()

    async def stream():
        task = asyncio.create_task(_run(jid, source, target, queue))
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/download/{jid}")
async def download(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "This file has expired.")
    path = job["dir"] / "translated.pdf"
    if not path.exists():
        raise HTTPException(404, "No translated file for this job.")
    return FileResponse(path, media_type="application/pdf", filename=job["download_name"])


@app.get("/api/preview/{jid}/{which}")
async def preview(jid: str, which: str):
    job = JOBS.get(jid)
    if not job or which not in {"source", "translated"}:
        raise HTTPException(404, "Not found.")
    path = job["dir"] / f"{which}.pdf"
    if not path.exists():
        raise HTTPException(404, "Not found.")
    return FileResponse(path, media_type="application/pdf")


@app.get("/api/health")
async def health():
    return {"ok": True, "languages": list(LANGUAGES)}

"use client";

import { useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const LANGS = [
  { code: "en", label: "English" },
  { code: "te", label: "తెలుగు (Telugu)" },
  { code: "hi", label: "हिंदी (Hindi)" },
];

const STAGES: Record<string, string> = {
  extracting: "Extracting text",
  structure: "Detecting structure",
  translating: "Translating content",
  rebuilding: "Rebuilding PDF",
  finalizing: "Finalizing",
};
const ORDER = Object.keys(STAGES);

type Meta = {
  job_id: string;
  filename: string;
  size_mb: number;
  pages: number;
  multi_column_pages: number[];
};

type Result = { download_url: string; filename: string; overflow_pages: number[] };

export default function Page() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [src, setSrc] = useState("en");
  const [tgt, setTgt] = useState("te");
  const [stage, setStage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function reset() {
    setMeta(null);
    setStage(null);
    setResult(null);
    setError(null);
    setProgress(0);
    setBusy(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onFile(file: File) {
    setError(null);
    setBusy(true);
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch(`${API}/api/upload`, { method: "POST", body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Upload failed.");
      setMeta(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  function translate() {
    if (!meta) return;
    setError(null);
    setBusy(true);
    setStage("extracting");

    const es = new EventSource(
      `${API}/api/translate/${meta.job_id}?source=${src}&target=${tgt}`
    );

    es.onmessage = (ev) => {
      const d = JSON.parse(ev.data);
      if (d.stage === "done") {
        setResult(d);
        setStage(null);
        setBusy(false);
        es.close();
        return;
      }
      if (d.stage === "error") {
        setError(d.message);
        setStage(null);
        setBusy(false);
        es.close();
        return;
      }
      setStage(d.stage);
      if (typeof d.progress === "number") setProgress(d.progress);
    };

    es.onerror = () => {
      setError("Lost connection to the server. Try again.");
      setStage(null);
      setBusy(false);
      es.close();
    };
  }

  const targets = LANGS.filter((l) => l.code !== src);

  return (
    <main className="mx-auto max-w-3xl px-5 py-14">
      <header className="mb-10">
        <h1 className="text-2xl font-medium tracking-tight">Arth</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Translate educational PDFs between English, Telugu and Hindi — layout kept intact.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {!meta && (
        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) onFile(f);
          }}
          className="flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-neutral-300 bg-neutral-50 px-6 py-16 text-center transition hover:border-neutral-400"
        >
          <p className="text-base font-medium">Drop your PDF here</p>
          <p className="mt-1 text-sm text-neutral-500">or browse from your device</p>
          <p className="mt-4 text-xs text-neutral-400">PDF only · up to 30 pages · max 25 MB</p>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            disabled={busy}
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
          />
        </label>
      )}

      {meta && !stage && !result && (
        <section className="rounded-xl border border-neutral-200 p-5">
          <div className="mb-5 flex items-center justify-between gap-3 rounded-lg bg-neutral-50 px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{meta.filename}</p>
              <p className="mt-0.5 text-sm text-neutral-500">
                {meta.size_mb} MB · {meta.pages} {meta.pages === 1 ? "page" : "pages"}
              </p>
            </div>
            <button onClick={reset} className="text-sm text-neutral-500 hover:text-neutral-900">
              Remove
            </button>
          </div>

          <div className="mb-5 grid grid-cols-[1fr_auto_1fr] items-end gap-3">
            <div>
              <label className="mb-1.5 block text-sm text-neutral-600">Translate from</label>
              <select
                value={src}
                onChange={(e) => {
                  setSrc(e.target.value);
                  if (e.target.value === tgt)
                    setTgt(LANGS.find((l) => l.code !== e.target.value)!.code);
                }}
                className="h-9 w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm"
              >
                {LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
            <span className="pb-2 text-neutral-400">→</span>
            <div>
              <label className="mb-1.5 block text-sm text-neutral-600">Translate to</label>
              <select
                value={tgt}
                onChange={(e) => setTgt(e.target.value)}
                className="h-9 w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm"
              >
                {targets.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {meta.multi_column_pages.length > 0 && (
            <p className="mb-5 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {meta.multi_column_pages.length === 1
                ? `Page ${meta.multi_column_pages[0]} uses`
                : `Pages ${meta.multi_column_pages.join(", ")} use`}{" "}
              a multi-column layout. Spacing may shift slightly in the output.
            </p>
          )}

          <button
            onClick={translate}
            disabled={busy}
            className="w-full rounded-lg bg-neutral-900 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Translate document
          </button>
        </section>
      )}

      {stage && (
        <section className="rounded-xl border border-neutral-200 p-6">
          <p className="text-base font-medium">Translating your document</p>
          <p className="mt-1 text-sm text-neutral-500">
            {stage === "translating"
              ? `${Math.round(progress * 100)}% of text translated`
              : STAGES[stage]}
          </p>

          <div className="my-5 h-1.5 overflow-hidden rounded-full bg-neutral-100">
            <div
              className="h-full rounded-full bg-neutral-900 transition-all"
              style={{
                width: `${Math.round(
                  ((ORDER.indexOf(stage) + (stage === "translating" ? progress : 1)) /
                    ORDER.length) *
                    100
                )}%`,
              }}
            />
          </div>

          <ul className="space-y-2.5">
            {ORDER.map((key, i) => {
              const at = ORDER.indexOf(stage);
              const state = i < at ? "done" : i === at ? "active" : "todo";
              return (
                <li
                  key={key}
                  className={`text-sm ${
                    state === "active"
                      ? "font-medium text-neutral-900"
                      : state === "done"
                      ? "text-neutral-500"
                      : "text-neutral-300"
                  }`}
                >
                  {state === "done" ? "✓ " : "· "}
                  {STAGES[key]}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {result && meta && (
        <section className="rounded-xl border border-neutral-200 p-5">
          <p className="mb-4 text-base font-medium">Translation complete</p>

          {result.overflow_pages.length > 0 && (
            <p className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Text on page{result.overflow_pages.length > 1 ? "s" : ""}{" "}
              {result.overflow_pages.join(", ")} was reduced to fit the original spacing. Check
              those pages before printing.
            </p>
          )}

          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            {(["source", "translated"] as const).map((which) => (
              <div key={which}>
                <p className="mb-1.5 text-sm text-neutral-500">
                  {which === "source" ? "Original" : "Translated"}
                </p>
                <iframe
                  title={which}
                  src={`${API}/api/preview/${meta.job_id}/${which}#toolbar=0`}
                  className="h-72 w-full rounded-lg border border-neutral-200"
                />
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <code className="text-sm text-neutral-500">{result.filename}</code>
            <div className="flex gap-2">
              <button
                onClick={reset}
                className="rounded-lg border border-neutral-300 px-4 py-2 text-sm"
              >
                Translate another
              </button>
              <a
                href={`${API}${result.download_url}`}
                className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white"
              >
                Download
              </a>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

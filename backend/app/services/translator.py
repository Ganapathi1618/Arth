"""Translation providers. Swap by changing TRANSLATION_PROVIDER env var."""
from __future__ import annotations

import asyncio
import json
import os
import re
from abc import ABC, abstractmethod

import anthropic

from app.core.config import GLOSSARY, LANGUAGES

# Sentinels wrapping protected segments. Private-use codepoints, so they can
# never collide with document text.
OPEN = ""
CLOSE = ""

# Segments we must never send to a translator: equations, numbers with units,
# chemical formulae, question numbering. Replaced with sentinels, restored after.
PROTECT = re.compile(
    r"("
    r"\$[^$]+\$"
    r"|\\\([^)]*\\\)"
    r"|[A-Za-z]?\d+[A-Za-z]?[₀-₉]+"
    r"|\b\d+(?:\.\d+)?\s*(?:cm|mm|km|kg|g|ml|l|°C|°F|%|m/s|N|J|W|V|A)\b"
    r"|\b\d+(?:\.\d+)?\s*[×x/+\-=]\s*\d+(?:\.\d+)?"
    r")"
)


def mask(text: str) -> tuple[str, list[str]]:
    tokens: list[str] = []

    def repl(m: re.Match) -> str:
        tokens.append(m.group(0))
        return f"{OPEN}{len(tokens) - 1}{CLOSE}"

    return PROTECT.sub(repl, text), tokens


def unmask(text: str, tokens: list[str]) -> str:
    for i, tok in enumerate(tokens):
        text = text.replace(f"{OPEN}{i}{CLOSE}", tok)
    return text


class Provider(ABC):
    @abstractmethod
    async def translate_batch(self, texts: list[str], src: str, tgt: str) -> list[str]: ...


class ClaudeProvider(Provider):
    """Claude API. Segments are sent in groups rather than one per request, so
    the model sees the surrounding page context — a heading and the paragraph
    under it should agree in register, and a table column should stay
    consistent down its rows."""

    MODEL = "claude-opus-5"
    CHUNK = 20  # segments per request
    CONCURRENCY = 4

    SCHEMA = {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "text": {"type": "string"},
                        },
                        "required": ["id", "text"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["translations"],
            "additionalProperties": False,
        },
    }

    def __init__(self) -> None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env, or set "
                "TRANSLATION_PROVIDER=mock to work on layout without an API key."
            )
        self.client = anthropic.AsyncAnthropic()

    def _system(self, src: str, tgt: str) -> str:
        glossary = GLOSSARY.get(tgt, {})
        terms = "\n".join(f"- {en} -> {native}" for en, native in glossary.items())
        return (
            f"You translate school textbook material from {LANGUAGES[src]['name']} "
            f"into {LANGUAGES[tgt]['name']}.\n\n"
            "Rules:\n"
            "- Segments are fragments lifted out of a page layout: headings, table "
            "cells, captions, list items. Do not merge, split, reorder or explain "
            "them, and never add text that was not in the source.\n"
            "- Keep terminology consistent across the whole batch.\n"
            "- Preserve leading and trailing whitespace, bullet characters and "
            "question numbering exactly as given.\n"
            "- This is written for students, so keep the register plain and the "
            "sentences short. When two phrasings are equally accurate, choose the "
            "shorter one — the translation has to fit the original box on the page.\n"
            f"- Text wrapped in {OPEN} and {CLOSE} is a placeholder for an equation "
            "or a measurement. Copy each placeholder through verbatim, with the "
            "same digits inside it. Never translate, renumber or drop one.\n"
            "- If a segment has nothing to translate — a bare number, a symbol, a "
            "stray character — return it unchanged.\n"
            + (f"\nUse these terms exactly:\n{terms}\n" if terms else "")
        )

    async def _chunk(self, items: list[tuple[int, str]], src: str, tgt: str) -> dict[int, str]:
        """Translate one group of (index, masked text) pairs."""
        payload = json.dumps(
            [{"id": i, "text": t} for i, t in items], ensure_ascii=False
        )
        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=16000,
            system=self._system(src, tgt),
            output_config={"effort": "low", "format": self.SCHEMA},
            messages=[
                {
                    "role": "user",
                    "content": "Translate each segment. Return one entry per id.\n\n" + payload,
                }
            ],
        )
        text = next(b.text for b in response.content if b.type == "text")
        rows = json.loads(text)["translations"]
        ids = {i for i, _ in items}
        return {r["id"]: r["text"] for r in rows if r["id"] in ids}

    async def translate_batch(self, texts: list[str], src: str, tgt: str) -> list[str]:
        masked: list[tuple[str, list[str]]] = [mask(t) for t in texts]

        # Blank segments never reach the API.
        pending = [(i, m) for i, (m, _) in enumerate(masked) if m.strip()]
        chunks = [pending[i : i + self.CHUNK] for i in range(0, len(pending), self.CHUNK)]

        sem = asyncio.Semaphore(self.CONCURRENCY)

        async def guarded(chunk: list[tuple[int, str]]) -> dict[int, str]:
            async with sem:
                for attempt in range(3):
                    try:
                        return await self._chunk(chunk, src, tgt)
                    except (
                        anthropic.APIStatusError,
                        anthropic.APIConnectionError,
                        json.JSONDecodeError,
                        KeyError,
                        TypeError,
                        StopIteration,
                    ):
                        if attempt == 2:
                            return {}  # fail open: keep the original text
                        await asyncio.sleep(1.5 * (attempt + 1))
                return {}

        results: dict[int, str] = {}
        for part in await asyncio.gather(*(guarded(c) for c in chunks)):
            results.update(part)

        out: list[str] = []
        for i, (_, tokens) in enumerate(masked):
            translated = results.get(i)
            out.append(texts[i] if translated is None else unmask(translated, tokens))
        return out


class MockProvider(Provider):
    """Dev provider. Simulates target-language text expansion so layout
    logic is exercised honestly without burning API credits."""

    SAMPLE = {
        "te": "ఈ వాక్యం తెలుగులో అనువదించబడింది మరియు పొడవుగా ఉంటుంది",
        "hi": "यह वाक्य हिंदी में अनुवादित किया गया है और लंबा है",
        "en": "This sentence has been translated into English for testing",
    }

    async def translate_batch(self, texts: list[str], src: str, tgt: str) -> list[str]:
        out = []
        for t in texts:
            masked, tokens = mask(t)
            ratio = LANGUAGES[tgt]["expansion"]
            n = max(1, int(len(masked.split()) * ratio / 8))
            out.append(unmask(" ".join([self.SAMPLE[tgt]] * n), tokens))
        return out


def get_provider() -> Provider:
    name = os.getenv("TRANSLATION_PROVIDER", "mock").lower()
    if name == "claude":
        return ClaudeProvider()
    return MockProvider()

#!/usr/bin/env bash
# Downloads the Unicode fonts required for Telugu and Devanagari rendering.
# Fonts are gitignored because of their size. Runs from any working directory,
# so the Vercel build can call it from backend/ as well.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/backend/fonts"
mkdir -p "$DIR"
BASE="https://github.com/google/fonts/raw/main/ofl"

fetch() {
  local name="$1" url="$2" out="$DIR/$1"

  # --fail so an HTTP error is an error. Without it curl writes the error body
  # into the .ttf and the build "succeeds" with fonts that render empty boxes.
  curl -fsSL -o "$out" "$url"

  # A real Noto TTF is well over 100 KB and starts with a sfnt version tag.
  # Anything smaller is an error page that slipped through a redirect.
  local size
  size=$(wc -c < "$out")
  if [ "$size" -lt 50000 ]; then
    echo "error: $name downloaded as $size bytes, which is not a font." >&2
    echo "       $url" >&2
    rm -f "$out"
    exit 1
  fi
}

fetch NotoSans.ttf            "$BASE/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf"
fetch NotoSansTelugu.ttf      "$BASE/notosanstelugu/NotoSansTelugu%5Bwdth%2Cwght%5D.ttf"
fetch NotoSansDevanagari.ttf  "$BASE/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"

echo "Fonts installed:"
ls -la "$DIR"

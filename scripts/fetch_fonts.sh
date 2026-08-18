#!/usr/bin/env bash
# Downloads the Unicode fonts required for Telugu and Devanagari rendering.
# Run from the repo root. Fonts are gitignored because of their size.
set -euo pipefail

DIR="backend/fonts"
mkdir -p "$DIR"
BASE="https://github.com/google/fonts/raw/main/ofl"

curl -sL -o "$DIR/NotoSans.ttf" \
  "$BASE/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf"
curl -sL -o "$DIR/NotoSansTelugu.ttf" \
  "$BASE/notosanstelugu/NotoSansTelugu%5Bwdth%2Cwght%5D.ttf"
curl -sL -o "$DIR/NotoSansDevanagari.ttf" \
  "$BASE/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"

echo "Fonts installed:"
ls -la "$DIR"

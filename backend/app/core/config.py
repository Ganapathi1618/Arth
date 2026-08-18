from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
FONT_DIR = BASE_DIR / "fonts"
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

MAX_FILE_MB = 25
MAX_PAGES = 30

LANGUAGES = {
    "en": {"name": "English", "font": "NotoSans.ttf", "expansion": 1.0},
    "te": {"name": "Telugu", "font": "NotoSansTelugu.ttf", "expansion": 1.35},
    "hi": {"name": "Hindi", "font": "NotoSansDevanagari.ttf", "expansion": 1.25},
}

# Educational terms that must not drift. Injected into the translation prompt.
GLOSSARY = {
    "te": {
        "photosynthesis": "కిరణజన్య సంయోగక్రియ",
        "hypotenuse": "కర్ణం",
        "denominator": "హారం",
        "numerator": "లవం",
        "velocity": "వేగం",
        "cell": "కణం",
        "atom": "పరమాణువు",
    },
    "hi": {
        "photosynthesis": "प्रकाश संश्लेषण",
        "hypotenuse": "कर्ण",
        "denominator": "हर",
        "numerator": "अंश",
        "velocity": "वेग",
        "cell": "कोशिका",
        "atom": "परमाणु",
    },
    "en": {},
}


def font_path(lang: str) -> Path:
    return FONT_DIR / LANGUAGES[lang]["font"]

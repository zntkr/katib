import sys
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_catalog: dict = {}
_fallback: dict = {}
_current_lang: str = "en"


def _translations_dir() -> Path:
    try:
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    except AttributeError:
        base = Path(__file__).parent.parent
    return base / "translations"


def _load_catalog(lang: str) -> dict:
    path = _translations_dir() / f"{lang}.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning("i18n: could not load '%s': %s", lang, e)
        return {}


def _resolve(catalog: dict, key: str) -> str | None:
    node = catalog
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def set_language(lang: str) -> None:
    global _catalog, _fallback, _current_lang
    _fallback = _load_catalog("en")
    _catalog = _load_catalog(lang) if lang != "en" else _fallback
    _current_lang = lang


def t(key: str) -> str:
    result = _resolve(_catalog, key)
    if result is not None:
        return result
    fallback = _resolve(_fallback, key)
    if fallback is not None:
        if _current_lang != "en":
            logger.warning("i18n: missing key '%s' in '%s'", key, _current_lang)
        return fallback
    logger.warning("i18n: key '%s' not found", key)
    return key


def try_t(key: str) -> str:
    """Like t() but returns key as-is without warning if not found.
    Use for strings that may be either translation keys or plain text."""
    result = _resolve(_catalog, key)
    if result is not None:
        return result
    fallback = _resolve(_fallback, key)
    if fallback is not None:
        if _current_lang != "en":
            logger.warning("i18n: missing key '%s' in '%s'", key, _current_lang)
        return fallback
    return key


def available_languages() -> list[tuple[str, str]]:
    _NAMES = {
        "en": "English", "tr": "Türkçe", "es": "Español", "fr": "Français",
        "de": "Deutsch", "ar": "العربية", "zh": "中文", "ja": "日本語",
        "ko": "한국어", "ru": "Русский", "pt": "Português", "it": "Italiano",
        "hi": "हिन्दी", "id": "Bahasa Indonesia", "el": "Ελληνικά",
        "fa": "فارسی", "ur": "اردو",
    }
    try:
        return [
            (_NAMES.get(p.stem, p.stem), p.stem)
            for p in sorted(_translations_dir().glob("*.json"))
        ]
    except Exception:
        return [("English", "en")]

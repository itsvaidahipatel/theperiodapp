"""
Minimal i18n helpers for backend-generated user-facing strings.

Design goals:
- Backward compatible: endpoints still return the same fields (`insights`, `confidence.reason`)
- Forward compatible: also return stable keys + params for client-side localization

# TODO: If pluralization, ICU messages, or locale-specific grammar grow beyond simple
# ``str.format`` placeholders, integrate a dedicated stack (e.g. Babel gettext, Project
# Fluent, or similar) and migrate catalogs while keeping stable logical keys.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from locales import LOCALE_STRINGS

logger = logging.getLogger("periodcycle_ai.i18n")


def _normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return "en"
    lang = str(lang).lower().strip()
    if lang.startswith("hi"):
        return "hi"
    if lang.startswith("gu"):
        return "gu"
    return "en"


def t(key: str, lang: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
    """Translate a key and format with params. Falls back to English, then to the raw key."""
    l = _normalize_lang(lang)
    locale_table = LOCALE_STRINGS.get(l) or LOCALE_STRINGS["en"]
    template = locale_table.get(key)
    if template is None:
        template = LOCALE_STRINGS["en"].get(key)
    if template is None:
        logger.warning("Missing i18n key (not defined in English catalog): %s", key)
        template = key
    if not params:
        return template
    try:
        return template.format(**params)
    except Exception:
        # If formatting fails, return template to avoid 500s
        return template

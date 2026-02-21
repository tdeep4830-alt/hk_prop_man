"""Internationalisation (i18n) string loader and translator."""

import json
from pathlib import Path

_I18N_DIR = Path(__file__).parent / "i18n"
STRINGS: dict[str, dict] = {}

for _lang_file in _I18N_DIR.glob("*.json"):
    _lang_code = _lang_file.stem  # "en", "zh_hk"
    STRINGS[_lang_code] = json.loads(_lang_file.read_text(encoding="utf-8"))

SUPPORTED_LANGS = set(STRINGS.keys())


def t(key: str, lang: str = "zh_hk", **fmt_args: object) -> str:
    """Resolve a dot-separated i18n key (e.g. 'error.internal').

    Supports str.format() placeholders: t("auth.quota_exceeded", lang, limit=10)
    """
    parts = key.split(".")
    node: dict | str = STRINGS.get(lang, STRINGS.get("zh_hk", {}))
    for p in parts:
        if isinstance(node, dict):
            node = node.get(p, key)
        else:
            return key
    if isinstance(node, str):
        return node.format(**fmt_args) if fmt_args else node
    return key

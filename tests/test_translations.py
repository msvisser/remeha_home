"""Test that every translation has the same texts as the English one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TRANSLATIONS = (
    Path(__file__).parent.parent / "custom_components" / "remeha_home" / "translations"
)


def _load(path: Path) -> dict:
    """Return the parsed JSON of a translation file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _keys(data: dict, prefix: str = "") -> set[str]:
    """Return the paths of all texts, such as config.step.auth.description."""
    keys = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _keys(value, path)
        else:
            keys.add(path)
    return keys


@pytest.mark.parametrize(
    "path",
    sorted(path for path in TRANSLATIONS.glob("*.json") if path.name != "en.json"),
    ids=lambda path: path.stem,
)
def test_translation_has_all_texts(path: Path) -> None:
    """Have exactly the texts of en.json, so nothing new stays untranslated."""
    english = _keys(_load(TRANSLATIONS / "en.json"))
    translation = _keys(_load(path))

    assert not english - translation, (
        f"{path.name} misses {sorted(english - translation)}"
    )
    assert not translation - english, (
        f"{path.name} has texts that en.json doesn't have: {sorted(translation - english)}"
    )

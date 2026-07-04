"""JSON-based content loader for lessons, quizzes, and practice tasks.

New content lives in cert_study_app/content/{track}/{type}.json.
Returns raw dicts — callers convert to dataclass types.
"""
from __future__ import annotations

import json
from pathlib import Path

CONTENT_DIR = Path(__file__).parent


def _load(track_id: str, filename: str) -> list[dict]:
    path = CONTENT_DIR / track_id / filename
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_lesson_dicts(track_id: str) -> list[dict]:
    return _load(track_id, "lessons.json")


def load_quiz_dicts(track_id: str) -> list[dict]:
    return _load(track_id, "quizzes.json")


def load_practice_dicts(track_id: str) -> list[dict]:
    return _load(track_id, "practices.json")

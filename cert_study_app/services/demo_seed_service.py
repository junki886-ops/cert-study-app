from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import func

from cert_study_app.models import Question


DEMO_SOURCE = "Demo Certification Sample"
DEMO_DATA_DIR = Path(__file__).resolve().parent.parent / "demo_data"
FULL_SEED_DATA_PATH = DEMO_DATA_DIR / "questions_seed.json"
DEMO_DATA_PATH = DEMO_DATA_DIR / "demo_questions.json"


def _seed_data_path() -> Path:
    if FULL_SEED_DATA_PATH.exists():
        return FULL_SEED_DATA_PATH
    return DEMO_DATA_PATH


def _json_text(value, fallback):
    if value in (None, ""):
        return fallback
    try:
        return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    except Exception:
        return fallback


def seed_demo_questions_if_empty(db) -> int:
    if os.getenv("CERT_STUDY_SEED_DEMO", "1") == "0":
        return 0

    existing = db.query(func.count(Question.id)).scalar() or 0
    if existing:
        return 0

    with _seed_data_path().open("r", encoding="utf-8") as file:
        rows = json.load(file)

    inserted = 0
    for row in rows:
        question = Question(
            stem=row["stem"],
            answer=_json_text(row.get("answer"), None),
            explanation=row.get("explanation"),
            question_type=row.get("question_type", "MCQ"),
            question_number=row.get("question_number"),
            group_id=row.get("group_id"),
            parent_stem=row.get("parent_stem"),
            parent_image_paths=_json_text(row.get("parent_image_paths"), "[]"),
            page=row.get("page"),
            category=row.get("category"),
            subcategory=row.get("subcategory"),
            source=row.get("source") or DEMO_SOURCE,
            image_path=row.get("image_path"),
            raw_text=row.get("raw_text") or row.get("stem"),
            structured_data_json=json.dumps(row, ensure_ascii=False),
            parse_status=row.get("parse_status") or "approved",
            quality_score=row.get("quality_score") or 100,
            quality_status=row.get("quality_status") or "seed",
            quality_issues=_json_text(row.get("quality_issues"), "[]"),
            chunk_key=row.get("chunk_key"),
            chunk_index=row.get("chunk_index"),
            parser_version=row.get("parser_version") or "seed-v1",
            code=row.get("code"),
            pairs=_json_text(row.get("pairs"), None),
            sequence=_json_text(row.get("sequence"), None),
        )
        question.set_options(row.get("options") or [])
        question.set_concept_tags(row.get("concept_tags") or [])
        db.add(question)
        inserted += 1

    db.commit()
    return inserted

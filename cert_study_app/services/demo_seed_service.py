from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path

from sqlalchemy import func

from cert_study_app.models import Question


DEMO_SOURCE = "Demo Certification Sample"
DEMO_DATA_DIR = Path(__file__).resolve().parent.parent / "demo_data"
FULL_SEED_DATA_PATH = DEMO_DATA_DIR / "questions_seed.json"
DEMO_DATA_PATH = DEMO_DATA_DIR / "demo_questions.json"
SEED_VERSION = "seed-v2"
SEED_QUALITY_STATUS = "seed"
SEED_SOURCES = {DEMO_SOURCE, "AZ-104 imported seed"}


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


def _seed_hash(row: dict) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _apply_seed_row(question: Question, row: dict) -> None:
    row_with_meta = dict(row)
    row_with_meta["_seed_version"] = SEED_VERSION
    row_with_meta["_seed_hash"] = _seed_hash(row)
    question.stem = row["stem"]
    question.answer = _json_text(row.get("answer"), None)
    question.explanation = row.get("explanation")
    question.question_type = row.get("question_type", "MCQ")
    question.question_number = row.get("question_number")
    question.group_id = row.get("group_id")
    question.parent_stem = row.get("parent_stem")
    question.parent_image_paths = _json_text(row.get("parent_image_paths"), "[]")
    question.page = row.get("page")
    question.category = row.get("category")
    question.subcategory = row.get("subcategory")
    question.source = row.get("source") or DEMO_SOURCE
    question.image_path = row.get("image_path")
    question.raw_text = row.get("raw_text") or row.get("stem")
    question.structured_data_json = json.dumps(row_with_meta, ensure_ascii=False)
    question.parse_status = row.get("parse_status") or "approved"
    question.quality_score = row.get("quality_score") or 100
    question.quality_status = row.get("quality_status") or SEED_QUALITY_STATUS
    question.quality_issues = _json_text(row.get("quality_issues"), "[]")
    question.chunk_key = row.get("chunk_key")
    question.chunk_index = row.get("chunk_index")
    question.parser_version = row.get("parser_version") or SEED_VERSION
    question.code = row.get("code")
    question.pairs = _json_text(row.get("pairs"), None)
    question.sequence = _json_text(row.get("sequence"), None)
    question.set_options(row.get("options") or [])
    question.set_concept_tags(row.get("concept_tags") or [])


def _refresh_seed_questions(db, rows: list[dict]) -> int:
    if os.getenv("CERT_STUDY_REFRESH_SEED", "1") == "0":
        return 0

    overwrite_reviewed = os.getenv("CERT_STUDY_OVERWRITE_REVIEWED_SEED", "0") == "1"
    changed = 0
    for row in rows:
        question_number = row.get("question_number")
        if not question_number:
            continue

        source = row.get("source") or DEMO_SOURCE
        question = (
            db.query(Question)
            .filter(Question.question_number == question_number)
            .filter(Question.source == source)
            .order_by(Question.id.asc())
            .first()
        )
        if not question:
            question = (
                db.query(Question)
                .filter(Question.question_number == question_number)
                .filter(Question.quality_status == SEED_QUALITY_STATUS)
                .order_by(Question.id.asc())
                .first()
            )
        if not question:
            question = Question()
            db.add(question)
        elif (
            not overwrite_reviewed
            and question.quality_status != SEED_QUALITY_STATUS
            and question.source not in SEED_SOURCES
        ):
            continue

        _apply_seed_row(question, row)
        changed += 1

    if changed:
        db.commit()
    return changed


def seed_demo_questions_if_empty(db) -> int:
    if os.getenv("CERT_STUDY_SEED_DEMO", "1") == "0":
        return 0

    with _seed_data_path().open("r", encoding="utf-8") as file:
        rows = json.load(file)

    existing = db.query(func.count(Question.id)).scalar() or 0
    if existing:
        return _refresh_seed_questions(db, rows)

    inserted = 0
    for row in rows:
        question = Question()
        _apply_seed_row(question, row)
        db.add(question)
        inserted += 1

    db.commit()
    return inserted

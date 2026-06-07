from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import func

from cert_study_app.models import Question


DEMO_SOURCE = "Demo Certification Sample"
DEMO_DATA_PATH = Path(__file__).resolve().parent.parent / "demo_data" / "demo_questions.json"


def seed_demo_questions_if_empty(db) -> int:
    if os.getenv("CERT_STUDY_SEED_DEMO", "1") == "0":
        return 0

    existing = db.query(func.count(Question.id)).scalar() or 0
    if existing:
        return 0

    with DEMO_DATA_PATH.open("r", encoding="utf-8") as file:
        rows = json.load(file)

    inserted = 0
    for row in rows:
        question = Question(
            stem=row["stem"],
            answer=row.get("answer"),
            explanation=row.get("explanation"),
            question_type=row.get("question_type", "MCQ"),
            question_number=row.get("question_number"),
            category=row.get("category"),
            subcategory=row.get("subcategory"),
            source=row.get("source") or DEMO_SOURCE,
            raw_text=row.get("stem"),
            parse_status="approved",
            quality_score=100,
            quality_status="demo",
            parser_version="demo-seed-v1",
        )
        question.set_options(row.get("options") or [])
        question.set_concept_tags(row.get("concept_tags") or [])
        db.add(question)
        inserted += 1

    db.commit()
    return inserted

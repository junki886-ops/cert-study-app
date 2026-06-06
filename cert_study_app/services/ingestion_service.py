import json
import re

from cert_study_app.db import SessionLocal, init_db
from cert_study_app.models import Question
from cert_study_app.services.text_cleanup_service import clean_inline_text, clean_question_text


def split_embedded_option_text(value: str) -> list[tuple[str, str]]:
    text = clean_inline_text(value)
    matches = list(re.finditer(r"(?<![A-Za-z0-9])([A-Z])[\.\)]\s+", text))
    if len(matches) <= 1:
        return []
    parts = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        label = match.group(1).upper()
        body = text[match.end() : end].strip()
        parts.append((label, body))
    return parts


def normalize_question(item: dict) -> dict:
    stem = clean_question_text(item.get("stem") or item.get("question") or item.get("q_text") or "")
    explanation = clean_question_text(item.get("explanation", ""))

    answer_raw = item.get("answer", "")
    answer = (
        json.dumps(answer_raw, ensure_ascii=False)
        if isinstance(answer_raw, list)
        else str(answer_raw).strip()
    )

    raw_options = item.get("options", {})
    if isinstance(raw_options, list):
        options = {}
        for i, opt in enumerate(raw_options):
            value = clean_inline_text(opt)
            match = re.match(r"^([A-Za-z])[\.\)]\s*(.+)$", value)
            if match:
                options[match.group(1).upper()] = match.group(2).strip()
            else:
                options[chr(65 + i)] = value
    elif isinstance(raw_options, dict):
        options = {}
        for key, value in raw_options.items():
            key = str(key).upper()
            embedded = split_embedded_option_text(f"{key}. {value}")
            if embedded:
                for embedded_key, embedded_value in embedded:
                    options[embedded_key] = clean_inline_text(embedded_value)
            else:
                options[key] = clean_inline_text(value)
    else:
        options = {}

    sequence = (
        json.dumps(item.get("sequence"), ensure_ascii=False)
        if isinstance(item.get("sequence"), list)
        else None
    )
    pairs = (
        json.dumps(item.get("pairs"), ensure_ascii=False)
        if isinstance(item.get("pairs"), dict)
        else None
    )

    return {
        "stem": stem,
        "explanation": explanation,
        "answer": answer,
        "options": options,
        "category": item.get("category") or item.get("topic") or None,
        "subcategory": item.get("subcategory") or item.get("subtopic") or None,
        "page": item.get("page"),
        "question_number": item.get("number") or item.get("question_number"),
        "group_id": item.get("group_id") or None,
        "parent_stem": clean_question_text(item.get("parent_stem") or item.get("passage") or "") or None,
        "parent_image_paths": json.dumps(item.get("parent_image_paths") or [], ensure_ascii=False),
        "question_type": item.get("question_type", "MCQ"),
        "code": item.get("code", ""),
        "sequence": sequence,
        "pairs": pairs,
        "image_path": item.get("image_path") or item.get("image") or None,
        "raw_text": clean_question_text(item.get("raw_text") or item.get("ocr_text") or stem),
        "structured_data_json": json.dumps(item, ensure_ascii=False),
        "parse_status": item.get("parse_status") or _initial_parse_status(stem, options, answer),
        "quality_score": _optional_int(item.get("quality_score")),
        "quality_status": item.get("quality_status") or None,
        "quality_issues": json.dumps(item.get("quality_issues") or [], ensure_ascii=False),
        "chunk_key": item.get("chunk_key") or None,
        "chunk_index": _optional_int(item.get("chunk_index")),
        "parser_version": item.get("parser_version") or item.get("parser") or None,
    }


def _initial_parse_status(stem: str, options: dict, answer: str) -> str:
    if not stem or len(stem) < 30:
        return "needs_review"
    if not options or not answer or answer in {"[]", "{}"}:
        return "needs_review"
    return "draft"


def _optional_int(value) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except Exception:
        return None


def ingest_questions(json_path: str, source_name: str = "imported") -> int:
    init_db(verbose=False)
    db = SessionLocal()
    count = 0

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "questions" in data:
            data = data["questions"]

        for raw in data:
            if not isinstance(raw, dict):
                continue

            normalized = normalize_question(raw)
            question = Question(
                page=normalized["page"],
                question_number=normalized["question_number"],
                group_id=normalized["group_id"],
                parent_stem=normalized["parent_stem"],
                parent_image_paths=normalized["parent_image_paths"],
                stem=normalized["stem"],
                explanation=normalized["explanation"],
                answer=normalized["answer"],
                question_type=normalized["question_type"],
                category=normalized["category"],
                subcategory=normalized["subcategory"],
                source=source_name,
                image_path=normalized["image_path"],
                raw_text=normalized["raw_text"],
                structured_data_json=normalized["structured_data_json"],
                parse_status=normalized["parse_status"],
                quality_score=normalized["quality_score"],
                quality_status=normalized["quality_status"],
                quality_issues=normalized["quality_issues"],
                chunk_key=normalized["chunk_key"],
                chunk_index=normalized["chunk_index"],
                parser_version=normalized["parser_version"],
                code=normalized["code"],
                sequence=normalized["sequence"],
                pairs=normalized["pairs"],
            )
            question.set_options(normalized["options"])
            db.add(question)
            count += 1

        db.commit()
        print(f"[INFO] {count} questions ingested ({source_name})")
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

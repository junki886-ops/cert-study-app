from __future__ import annotations

from collections import Counter
from typing import Optional

from sqlalchemy import func

from cert_study_app.models import Question


TYPE_ALIASES = {
    "single_choice": "mcq",
    "single select": "mcq",
    "single-select": "mcq",
    "multiple choice": "mcq",
    "mcq": "mcq",
    "multi": "multi_select",
    "multiple_response": "multi_select",
    "multiple-response": "multi_select",
    "multiple select": "multi_select",
    "multi_select": "multi_select",
    "yes/no": "yes_no",
    "yes no": "yes_no",
    "yes_no": "yes_no",
    "true_false": "yes_no",
    "true/false": "yes_no",
    "true/false (in-context)": "yes_no",
    "hotspot (true/false)": "yes_no",
    "hotspot true/false": "yes_no",
    "hotspot": "hotspot",
    "hotspot (drag and drop)": "matching",
    "drag and drop": "matching",
    "drag-and-drop": "matching",
    "matching": "matching",
    "ordering": "ordering",
    "order": "ordering",
    "sequence": "ordering",
    "table": "table_choice",
    "table_choice": "table_choice",
    "table choice": "table_choice",
    "case_study": "case_study",
    "case study": "case_study",
}


TYPE_METADATA = {
    "mcq": {
        "label": "단일 선택",
        "parser": "text_options",
        "ui": "radio",
        "needs_image": False,
        "validation": ["본문", "보기 2개 이상", "정답 1개"],
    },
    "multi_select": {
        "label": "복수 선택",
        "parser": "text_options_multi",
        "ui": "checkboxes",
        "needs_image": False,
        "validation": ["본문", "보기 4개 이상", "정답 2개 이상"],
    },
    "yes_no": {
        "label": "Yes/No 진술형",
        "parser": "visual_statements",
        "ui": "yes_no_matrix",
        "needs_image": True,
        "validation": ["진술 행", "행별 Yes/No 정답"],
    },
    "hotspot": {
        "label": "핫스팟/상자형",
        "parser": "visual_answer_areas",
        "ui": "row_select",
        "needs_image": True,
        "validation": ["답변 영역", "행별 선택지", "행별 정답"],
    },
    "table_choice": {
        "label": "표/드롭다운형",
        "parser": "visual_answer_areas",
        "ui": "row_select",
        "needs_image": True,
        "validation": ["표 행", "행별 선택지", "행별 정답"],
    },
    "matching": {
        "label": "드래그드롭/매칭",
        "parser": "visual_matching",
        "ui": "row_select",
        "needs_image": True,
        "validation": ["대상 항목", "선택 항목", "매칭 정답"],
    },
    "ordering": {
        "label": "순서 배열",
        "parser": "visual_ordering",
        "ui": "ordered_select",
        "needs_image": True,
        "validation": ["작업 목록", "정답 순서"],
    },
    "case_study": {
        "label": "공통 지문 객관식",
        "parser": "text_with_parent",
        "ui": "radio_or_checkboxes",
        "needs_image": False,
        "validation": ["공통 지문", "본문", "보기", "정답"],
    },
    "unparsed": {
        "label": "미분류",
        "parser": "ask_user",
        "ui": "none",
        "needs_image": True,
        "validation": ["유형 정의 필요"],
    },
}


STATUS_LABELS = {
    "approved": "풀이 가능",
    "needs_visual": "이미지 분석 대기",
    "needs_review": "질문 필요",
    "needs_reparse": "재파싱 필요",
    "draft": "처리 대기",
    "rejected": "제외",
    "none": "미정",
}


def type_metadata(question_type: Optional[str], answer_mode: Optional[str] = None) -> dict:
    key = normalize_question_type(question_type)
    metadata = dict(TYPE_METADATA.get(key, TYPE_METADATA["unparsed"]))
    metadata["type"] = key
    metadata["answer_mode"] = answer_mode or "single_choice"
    if answer_mode == "yes_no_matrix":
        metadata.update(TYPE_METADATA["yes_no"])
        metadata["type"] = key
        metadata["answer_mode"] = answer_mode
    elif answer_mode == "per_row_choice":
        metadata["parser"] = "visual_answer_areas"
        metadata["ui"] = "row_select"
        metadata["needs_image"] = True
        metadata["answer_mode"] = answer_mode
    elif answer_mode == "multi_select":
        metadata["ui"] = "checkboxes"
        metadata["answer_mode"] = answer_mode
    return metadata


def normalize_question_type(question_type: Optional[str]) -> str:
    raw = str(question_type or "").strip().lower()
    if not raw:
        return "unparsed"
    compact = raw.replace("-", " ").replace("_", " ")
    compact = " ".join(compact.split())
    if raw in TYPE_ALIASES:
        return TYPE_ALIASES[raw]
    if compact in TYPE_ALIASES:
        return TYPE_ALIASES[compact]
    if "true/false" in raw or "yes/no" in raw or "yes no" in compact:
        return "yes_no"
    if "drag" in raw or "matching" in raw:
        return "matching"
    if "hotspot" in raw:
        return "hotspot"
    if "table" in raw:
        return "table_choice"
    if "order" in raw or "sequence" in raw:
        return "ordering"
    if "multi" in raw:
        return "multi_select"
    if "case" in raw:
        return "case_study"
    if "mcq" in raw or "choice" in raw:
        return "mcq"
    return raw if raw in TYPE_METADATA else "unparsed"


def is_visual_question_type(question_type: Optional[str]) -> bool:
    return normalize_question_type(question_type) in {"yes_no", "hotspot", "table_choice", "matching", "ordering"}


def is_ordered_answer_type(question_type: Optional[str]) -> bool:
    return normalize_question_type(question_type) in {"ordering", "table_choice", "hotspot", "matching", "yes_no"}


def status_label(status: Optional[str]) -> str:
    return STATUS_LABELS.get(status or "none", status or "미정")


def automation_summary(db, source: Optional[str] = None) -> dict:
    query = db.query(Question)
    if source:
        query = query.filter(Question.source == source)

    status_counts = {
        status or "none": count
        for status, count in query.with_entities(Question.parse_status, func.count(Question.id))
        .group_by(Question.parse_status)
        .all()
    }
    type_counts = Counter()
    for question_type, count in query.with_entities(Question.question_type, func.count(Question.id)).group_by(Question.question_type):
        type_counts[(question_type or "unparsed").lower()] += count

    total = sum(status_counts.values())
    playable = status_counts.get("approved", 0)
    return {
        "total": total,
        "playable": playable,
        "status_counts": status_counts,
        "type_counts": dict(type_counts),
        "question_needed": status_counts.get("needs_review", 0) + status_counts.get("draft", 0) + status_counts.get("needs_reparse", 0),
        "reparse_needed": status_counts.get("needs_reparse", 0),
        "image_needed": status_counts.get("needs_visual", 0),
    }

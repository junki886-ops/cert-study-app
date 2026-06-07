import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from cert_study_app.models import Question
from cert_study_app.services.quiz_service import (
    choice_labels,
    extract_answer_from_stem,
    extract_options_from_stem,
    normalize_options,
    yes_no_labels,
)
from cert_study_app.services.text_cleanup_service import clean_question_text
from cert_study_app.services.question_type_metadata_service import (
    is_visual_question_type,
    normalize_question_type,
    type_metadata,
)
from cert_study_app.services.question_concept_service import apply_question_concept


AUTO_APPROVE_THRESHOLD = 85


def _answer_labels(answer: str) -> set[str]:
    raw = str(answer or "").strip()
    if not raw or raw in {"[]", "{}", "None"}:
        return set()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            raw = ",".join(str(item) for item in parsed)
    except Exception:
        pass
    return set(choice_labels(raw))


def _option_labels(options: list[str]) -> set[str]:
    labels = set()
    for index, option in enumerate(options):
        text = str(option).strip()
        match = re.match(r"^([A-Ha-h]|[1-8])[\.\)]?\s+", text)
        if match:
            label = match.group(1).upper()
            if label.isdigit():
                label = chr(ord("A") + int(label) - 1)
            labels.add(label)
        else:
            labels.add(chr(ord("A") + index))
    return labels


def _clean_options(options: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for option in options:
        text = re.sub(r"\s+", " ", str(option)).strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _looks_like_yes_no_hotspot(question_type: str, stem: str, answer: str, explanation: str, options: list[str]) -> bool:
    if normalize_question_type(question_type) not in {"hotspot", "table_choice", "yes_no"}:
        return False
    text = " ".join([stem or "", answer or "", explanation or "", " ".join(str(option) for option in options or [])])
    return bool(
        re.search(
            r"다음\s*각\s*(진술|설명|항목)|각\s*(진술|설명|항목).*예|예를\s*선택|아니오를\s*선택|아니요를\s*선택",
            text,
        )
    )


def _visual_analysis(question: Question) -> dict:
    try:
        return json.loads(question.visual_analysis_json) if question.visual_analysis_json else {}
    except Exception:
        return {}


def _looks_like_box_dropdown(question_type: str, stem: str) -> bool:
    if normalize_question_type(question_type) not in {"hotspot", "table_choice", "matching"}:
        return False
    return bool(re.search(r"(답변\s*영역|드롭다운|적절한\s*옵션|답변하려면)", stem or ""))


def _detect_answer_mode(question_type: str, stem: str, answer: str, explanation: str, options: list[str]) -> str:
    normalized_type = normalize_question_type(question_type)
    if normalized_type == "yes_no" or _looks_like_yes_no_hotspot(question_type, stem, answer, explanation, options):
        return "yes_no_matrix"
    labels = choice_labels(answer or "")
    if len(labels) > 1:
        text = stem or ""
        looks_like_standard_multi = bool(
            re.search(
                r"(어떤\s*(두|세|네)\s*가지|각\s*정답|각\s*올바른\s*선택|choose\s+two|choose\s+three|select\s+two|select\s+three)",
                text,
                re.I,
            )
        )
        if (
            not looks_like_standard_multi
            and normalized_type in {"hotspot", "table_choice", "matching"}
            and re.search(r"(각\s*리소스|각\s*항목|각\s*행|답변\s*영역|드롭다운|적절한\s*옵션|(?:상자|Box)\s*1)", text, re.I)
        ):
            return "per_row_choice"
        return "multi_select"
    return "single_choice"


def analyze_question(question: Question) -> dict:
    source_text = clean_question_text(question.raw_text or question.stem or "")
    stem = clean_question_text(question.stem or "")
    options = _clean_options(normalize_options(question.get_options()))
    recovered_options = False
    if not options:
        options = _clean_options(extract_options_from_stem(source_text))
        recovered_options = bool(options)

    answer = (question.answer or "").strip()
    recovered_answer = False
    if not _answer_labels(answer) and not yes_no_labels(answer):
        answer = extract_answer_from_stem(source_text)
        recovered_answer = bool(answer)

    issues = []
    score = 0

    if len(stem) >= 30:
        score += 20
    else:
        issues.append("문제 본문이 너무 짧거나 비어 있습니다.")

    image_ok = bool(question.image_path and Path(question.image_path).exists())
    if image_ok:
        score += 15
    else:
        issues.append("문제 단위 원문 이미지가 없습니다.")

    if len(options) >= 2:
        score += 25
    else:
        issues.append("보기를 2개 이상 안정적으로 찾지 못했습니다.")

    answer_labels = _answer_labels(answer)
    has_answer_text = bool(answer and answer not in {"[]", "{}", "None"})
    option_labels = _option_labels(options)
    if answer_labels or yes_no_labels(answer) or has_answer_text:
        score += 20
    else:
        issues.append("정답을 찾지 못했습니다.")

    question_type = normalize_question_type(question.question_type)
    if question_type in {"unparsed", "unknown", ""} and re.search(r"(드래그|끌어|drag|drop)", stem, re.I):
        question_type = "matching"
    answer_mode = _detect_answer_mode(question_type, stem, answer, question.explanation or "", options)
    yn_labels = yes_no_labels(answer) or yes_no_labels(question.explanation or "")
    visual = _visual_analysis(question)
    has_answer_areas = bool(visual.get("answer_areas"))
    has_statements = bool(visual.get("statements"))
    needs_answer_areas = _looks_like_box_dropdown(question_type, stem)
    needs_statements = answer_mode == "yes_no_matrix" or question_type == "yes_no"
    if has_answer_areas:
        answer_mode = "per_row_choice"
    if has_statements:
        answer_mode = "yes_no_matrix"
        needs_statements = True
    if has_statements and not yn_labels:
        statement_answers = [
            statement.get("selected_answer")
            for statement in visual.get("statements", [])
            if isinstance(statement, dict) and statement.get("selected_answer")
        ]
        yn_labels = yes_no_labels(",".join(str(item) for item in statement_answers))

    answer_matches_options = bool(answer_labels and option_labels and answer_labels.issubset(option_labels))
    if answer_mode == "yes_no_matrix":
        pass
    elif answer_matches_options:
        score += 15
    elif answer_labels and options:
        issues.append("정답 표기가 보기 번호와 맞지 않습니다.")

    if answer_mode == "yes_no_matrix":
        if not has_statements:
            issues.append("진술형 Yes/No 문제로 보이지만 statements 구조가 없습니다. qwen 이미지 분석이 필요합니다.")
        if yn_labels:
            score += 10
            if len(yn_labels) < 2:
                issues.append("핫스팟 Yes/No 유형이지만 진술별 정답 개수가 부족합니다.")
        else:
            issues.append("핫스팟 Yes/No 유형으로 보이지만 예/아니오 정답 시퀀스를 찾지 못했습니다.")
        if not image_ok:
            issues.append("핫스팟 Yes/No 진술을 확인할 원문 이미지가 없습니다.")
        if not has_statements and len(options) == 2 and {str(option).strip().lower() for option in options} <= {"yes", "no", "예", "아니오", "아니요"}:
            issues.append("보기는 Yes/No만 있고 진술 행은 이미지/OCR에서 별도 확인이 필요합니다.")

    if answer_mode == "multi_select" and len(_answer_labels(answer)) < 2:
        issues.append("복수 선택 유형으로 보이지만 정답을 2개 이상 찾지 못했습니다.")

    if answer_mode == "per_row_choice" and not has_answer_areas and len(choice_labels(answer or "")) < 2:
        issues.append("행별 선택 유형으로 보이지만 항목별 정답을 충분히 찾지 못했습니다.")

    if needs_answer_areas and not has_answer_areas:
        issues.append("상자/드롭다운형 문제로 보이지만 answer_areas 구조가 없습니다. qwen 이미지 분석이 필요합니다.")

    if question_type and question_type not in {"unparsed", "unknown"}:
        score += 5
    else:
        issues.append("문제 유형을 확정하지 못했습니다.")

    playable_input_ready = (
        len(options) >= 2
        or (answer_mode == "yes_no_matrix" and bool(yn_labels) and (has_statements or not needs_statements))
        or (needs_answer_areas and has_answer_areas)
    )
    if (is_visual_question_type(question_type) or answer_mode == "yes_no_matrix") and image_ok and not playable_input_ready:
        issues.append("풀이 화면에서 사용할 보기/상자/진술 구조가 없습니다. 주관식 입력으로 처리하면 안 됩니다.")

    visual_playable = (
        (is_visual_question_type(question_type) or answer_mode == "yes_no_matrix")
        and image_ok
        and has_answer_text
        and len(stem) >= 20
        and playable_input_ready
    )
    if visual_playable and len(options) < 2:
        issues = [issue for issue in issues if "보기" not in issue]

    needs_visual_analysis = (
        image_ok
        and len(stem) >= 20
        and (
            is_visual_question_type(question_type)
            or answer_mode in {"yes_no_matrix", "per_row_choice"}
        )
        and not playable_input_ready
    )

    can_auto_approve = (
        score >= AUTO_APPROVE_THRESHOLD
        and len(options) >= 2
        and bool(answer_labels)
        and answer_matches_options
        and len(stem) >= 30
    )

    structured = {
        "stem": stem,
        "options": options,
        "answer": answer,
        "explanation": question.explanation or "",
        "question_type": question_type or "unparsed",
        "question_type_metadata": type_metadata(question_type or "unparsed", answer_mode),
        "page": question.page,
        "image_path": question.image_path,
        "auto_review": {
            "score": score,
            "issues": issues,
            "recovered_options": recovered_options,
            "recovered_answer": recovered_answer,
            "can_auto_approve": can_auto_approve,
            "visual_playable": visual_playable,
            "needs_visual_analysis": needs_visual_analysis,
            "answer_mode": answer_mode,
            "yes_no_count": len(yn_labels),
            "playable_input_ready": playable_input_ready,
            "has_answer_areas": has_answer_areas,
            "has_statements": has_statements,
        },
    }

    return {
        "score": score,
        "issues": issues,
        "options": options,
        "answer": answer,
        "status": (
            "approved"
            if can_auto_approve or visual_playable
            else ("needs_visual" if needs_visual_analysis else "needs_review")
        ),
        "structured": structured,
        "can_auto_approve": can_auto_approve,
        "visual_playable": visual_playable,
        "needs_visual_analysis": needs_visual_analysis,
    }


def apply_auto_review(question: Question, approve: bool = True) -> dict:
    result = analyze_question(question)

    if result["options"] and not normalize_options(question.get_options()):
        question.set_options(result["options"])
    if result["answer"] and not _answer_labels(question.answer or ""):
        question.answer = result["answer"]

    question.review_score = result["score"]
    question.review_issues = json.dumps(result["issues"], ensure_ascii=False)
    question.structured_data_json = json.dumps(result["structured"], ensure_ascii=False)
    question.auto_reviewed_at = datetime.utcnow()
    concept = apply_question_concept(question, overwrite=False)
    result["structured"]["concept_metadata"] = concept
    question.structured_data_json = json.dumps(result["structured"], ensure_ascii=False)

    if approve and result["can_auto_approve"]:
        question.parse_status = "approved"
        question.reviewed_at = datetime.utcnow()
    elif approve and result["visual_playable"]:
        question.parse_status = "approved"
        question.reviewed_at = datetime.utcnow()
    elif approve and result.get("needs_visual_analysis"):
        question.parse_status = "needs_visual"
    elif question.parse_status not in {"approved", "rejected"}:
        question.parse_status = "needs_review"

    return result


def run_auto_review(db, source: Optional[str] = None, limit: int = 300, approve: bool = True) -> dict:
    query = db.query(Question).filter(Question.parse_status.in_(["needs_review", "needs_visual", "draft", None]))
    if source:
        query = query.filter(Question.source == source)

    questions = query.order_by(Question.id.asc()).limit(limit).all()
    summary = {
        "checked": 0,
        "approved": 0,
        "needs_review": 0,
        "needs_visual": 0,
        "recovered_options": 0,
        "recovered_answer": 0,
        "yes_no_matrix": 0,
        "multi_select": 0,
        "per_row_choice": 0,
        "concept_classified": 0,
        "concept_uncategorized": 0,
    }

    for question in questions:
        before_options = normalize_options(question.get_options())
        before_answer = _answer_labels(question.answer or "")
        result = apply_auto_review(question, approve=approve)
        summary["checked"] += 1
        if question.parse_status == "approved":
            summary["approved"] += 1
        elif question.parse_status == "needs_visual":
            summary["needs_visual"] += 1
        else:
            summary["needs_review"] += 1
        if not before_options and result["options"]:
            summary["recovered_options"] += 1
        if not before_answer and result["answer"]:
            summary["recovered_answer"] += 1
        answer_mode = result.get("structured", {}).get("auto_review", {}).get("answer_mode")
        if answer_mode in {"yes_no_matrix", "multi_select", "per_row_choice"}:
            summary[answer_mode] += 1
        concept = result.get("structured", {}).get("concept_metadata") or {}
        if concept.get("category") == "uncategorized":
            summary["concept_uncategorized"] += 1
        elif concept.get("category"):
            summary["concept_classified"] += 1

    db.commit()
    return summary

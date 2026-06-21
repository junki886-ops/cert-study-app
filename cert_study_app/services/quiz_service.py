from cert_study_app.config import DEFAULT_USER
from cert_study_app.models import Question
from cert_study_app.repositories.question_repository import QuestionRepository
from cert_study_app.services.question_concept_service import concept_label
from cert_study_app.services.answer_normalizer import (
    choice_labels,
    evaluate_answer,
    extract_answer_from_stem,
    extract_options_from_stem,
    normalize_options,
    option_label,
    option_labels_from_texts,
    option_text,
    structured_answer_values,
    yes_no_labels,
)
from cert_study_app.services.question_type_metadata_service import is_ordered_answer_type, normalize_question_type
from typing import Optional
import json
import re


def visual_analysis(question) -> dict:
    try:
        return json.loads(question.visual_analysis_json) if question.visual_analysis_json else {}
    except Exception:
        return {}


def clean_explanation(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw or "").strip()
    text = re.sub(r"^(explanation|해설)\s*:?\s*", "", text, flags=re.I)
    return text


def effective_answer(question) -> str:
    answer = question.answer or ""
    question_type = normalize_question_type(question.question_type)
    options = normalize_options(question.get_options()) or extract_options_from_stem(question.stem)
    structured_values = structured_answer_values(answer)
    if structured_values:
        structured_yn = yes_no_labels(",".join(structured_values))
        return ",".join(structured_yn or structured_values)

    is_structured_visual = question_type in {"hotspot", "table_choice", "matching", "ordering", "yes_no"}
    if is_structured_visual:
        answer_labels = yes_no_labels(answer)
        if answer_labels and question_type == "yes_no":
            return ",".join(answer_labels)
        analysis = visual_analysis(question)
        statements = analysis.get("statements")
        if isinstance(statements, list):
            statement_answers = [
                statement.get("selected_answer")
                for statement in statements
                if isinstance(statement, dict) and statement.get("selected_answer")
            ]
            labels = yes_no_labels(",".join(str(answer) for answer in statement_answers))
            if labels:
                return ",".join(labels)
        labels = option_labels_from_texts(options, analysis.get("answer"))
        if labels:
            return ",".join(labels)
        areas = analysis.get("answer_areas")
        if isinstance(areas, list):
            selected = [
                area.get("selected_answer")
                for area in areas
                if isinstance(area, dict) and area.get("selected_answer")
            ]
            labels = option_labels_from_texts(options, selected, allow_duplicates=True)
            if labels:
                return ",".join(labels)
    if is_structured_visual and not yes_no_labels(answer):
        explanation_labels = yes_no_labels(question.explanation or "")
        if explanation_labels:
            return ",".join(explanation_labels)
    return answer


def build_tutor_explanation(question, chosen: str, answer: str) -> str:
    options = normalize_options(question.get_options()) or extract_options_from_stem(question.stem)
    ordered = is_ordered_answer_type(question.question_type)
    answer_yn = yes_no_labels(answer)
    chosen_yn = yes_no_labels(chosen)
    answer_labels = choice_labels(answer)
    chosen_labels = choice_labels(chosen)
    answer_label = ", ".join(answer_yn or answer_labels) if (answer_yn or answer_labels) else option_label(answer)
    chosen_label = ", ".join(chosen_yn or chosen_labels) if (chosen_yn or chosen_labels) else option_label(chosen)
    raw_explanation = clean_explanation(question.explanation)
    answer_option_lines = [option_text(options, label) for label in answer_labels]
    answer_option_lines = [line for line in answer_option_lines if line]
    chosen_option_lines = [option_text(options, label) for label in chosen_labels]
    chosen_option_lines = [line for line in chosen_option_lines if line]
    correct = evaluate_answer(chosen, answer, ordered=ordered).correct

    lines = [f"#### 정답", f"**{answer_label}**"]
    for answer_option in answer_option_lines:
        lines.append(f"- 정답 보기: {answer_option}")
    if chosen_label and not correct:
        chosen_line = f"- 내가 고른 보기: {chosen_label}"
        lines.append(chosen_line)
        for chosen_option in chosen_option_lines:
            lines.append(f"  - {chosen_option}")

    lines.append("")
    lines.append("#### 정답 근거")
    if raw_explanation:
        lines.append(raw_explanation)
    else:
        lines.append("원문 해설이 비어 있어요. 공통 지문과 문제 원문 이미지에서 조건, 제한 사항, 요구 동작을 먼저 확인한 뒤 정답 보기와 직접 대응시키면 됩니다.")

    lines.append("")
    lines.append("#### 오답 포인트")
    if chosen_label and not correct:
        lines.append("내가 고른 보기가 문제의 조건을 모두 만족하는지 다시 확인해 보세요. 객관식 문제는 비슷한 서비스명이나 일부 조건만 맞는 보기가 자주 섞입니다.")
    else:
        lines.append("정답을 맞혔더라도 다른 보기가 왜 제외되는지 한 번만 확인하면 같은 유형에서 실수가 줄어듭니다.")

    lines.append("")
    lines.append("#### 암기 포인트")
    lines.append("문제의 핵심 조건을 먼저 표시하고, 보기마다 해당 조건을 만족/불만족으로 지워 나가면 빠르게 풀 수 있습니다.")
    return "\n".join(lines)


def question_payload(question, total: int) -> dict:
    options = normalize_options(question.get_options())
    if not options:
        options = extract_options_from_stem(question.stem)
    answer = effective_answer(question)
    if not answer or answer in {"[]", "{}", "None"}:
        answer = extract_answer_from_stem(question.stem)
    try:
        parent_image_paths = json.loads(question.parent_image_paths) if question.parent_image_paths else []
    except Exception:
        parent_image_paths = []
    return {
        "id": question.id,
        "number": question.question_number or question.id,
        "question": question.stem,
        "parent_stem": question.parent_stem,
        "parent_image_paths": parent_image_paths,
        "group_id": question.group_id,
        "options": options,
        "answer": answer,
        "explanation": question.explanation,
        "source": question.source,
        "category": question.category,
        "subcategory": question.subcategory,
        "concept_tags": question.get_concept_tags(),
        "concept_label": concept_label(question.category, question.subcategory),
        "question_type": question.question_type,
        "page": question.page,
        "image_path": question.image_path,
        "visual_analysis_json": question.visual_analysis_json,
        "quality_score": question.quality_score,
        "quality_status": question.quality_status,
        "quality_issues": question.quality_issues,
        "chunk_key": question.chunk_key,
        "chunk_index": question.chunk_index,
        "parser_version": question.parser_version,
        "total": total,
    }


class QuizService:
    def __init__(self, db):
        self.repo = QuestionRepository(db)

    def list_exams(self):
        exams = []
        for source, count, first_id, last_id in self.repo.source_summaries():
            name = source or "미분류"
            exams.append(
                {
                    "name": name,
                    "source": source,
                    "count": count,
                    "first_question_id": first_id,
                    "last_question_id": last_id,
                }
            )
        return exams

    def get_question(self, question_id: Optional[int] = None, source: Optional[str] = None):
        question = self.repo.get(question_id) if question_id else self.repo.first(source)
        if question and source and question.source != source:
            question = self.repo.first(source)
        if not question:
            return None
        return question_payload(question, self.repo.count(source))

    def get_question_by_number(self, number: int, source: Optional[str] = None):
        question = self.repo.by_number(number, source)
        if not question:
            return None
        return question_payload(question, self.repo.count(source))

    def question_status_by_number(self, number: int, source: Optional[str] = None):
        question = self.repo.by_number_any_status(number, source)
        if not question:
            return None
        return {
            "id": question.id,
            "number": question.question_number or question.id,
            "status": question.parse_status,
            "quality_status": question.quality_status,
            "quality_score": question.quality_score,
            "question_type": question.question_type,
            "source": question.source,
        }

    def get_random_question(self, source: Optional[str] = None, exclude_id: Optional[int] = None):
        question = self.repo.random(source, exclude_id)
        if not question:
            return None
        return question_payload(question, self.repo.count(source))

    def get_random_unit_question(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        exclude_id: Optional[int] = None,
    ):
        question = self.repo.random_for_unit(source, category, subcategory, exclude_id)
        if not question:
            return None
        return question_payload(question, self.repo.count(source))

    def max_question_number(self, source: Optional[str] = None) -> int:
        return self.repo.max_question_number(source)

    def get_weak_question(
        self,
        question_id: Optional[int] = None,
        source: Optional[str] = None,
        category: Optional[str] = None,
        question_type: Optional[str] = None,
        subcategory: Optional[str] = None,
    ):
        if question_id:
            question = self.repo.get(question_id)
            if question and source and question.source != source:
                question = None
            if question and (question.category or "") != (category or ""):
                question = None
            if question and subcategory and question.subcategory != subcategory:
                question = None
            if question and question_type and question.question_type != question_type:
                question = None
        else:
            question = None

        if not question:
            if category:
                question = self.repo.first_for_unit(source, category, subcategory)
            else:
                question = self.repo.first_for_type(source, category, question_type)
        if not question:
            return None
        return question_payload(question, self.repo.count(source))

    def answer(self, question_id: int, chosen: str, user_id: str = DEFAULT_USER):
        question = self.repo.get(question_id)
        if not question:
            return None
        answer = effective_answer(question)
        if not answer or answer in {"[]", "{}", "None"}:
            answer = extract_answer_from_stem(question.stem)
        evaluation = evaluate_answer(chosen, answer, ordered=is_ordered_answer_type(question.question_type))
        correct = evaluation.correct
        self.repo.add_attempt(
            user_id=user_id,
            question_id=question.id,
            chosen=str(chosen),
            correct=bool(correct),
            note_type="wrong" if not correct else None,
        )
        return {
            "correct": bool(correct),
            "answer": answer,
            "explanation": build_tutor_explanation(question, chosen, answer),
            "raw_explanation": question.explanation,
        }

    def next_question(self, current_id: int, source: Optional[str] = None):
        question = self.repo.next_after(current_id, source)
        if not question:
            return {"end": True}
        return question_payload(question, self.repo.count(source))

    def previous_question(self, current_id: int, source: Optional[str] = None):
        question = self.repo.previous_before(current_id, source)
        if not question:
            return {"start": True}
        return question_payload(question, self.repo.count(source))

    def next_weak_question(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        question_type: Optional[str] = None,
        subcategory: Optional[str] = None,
    ):
        if category:
            question = self.repo.next_for_unit(current_id, source, category, subcategory)
        else:
            question = self.repo.next_for_type(current_id, source, category, question_type)
        if not question:
            return {"end": True}
        return question_payload(question, self.repo.count(source))

    def previous_weak_question(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        question_type: Optional[str] = None,
        subcategory: Optional[str] = None,
    ):
        if category:
            question = self.repo.previous_for_unit(current_id, source, category, subcategory)
        else:
            question = self.repo.previous_for_type(current_id, source, category, question_type)
        if not question:
            return {"start": True}
        return question_payload(question, self.repo.count(source))

    def similar_type_from_question(self, question_id: int):
        question = self.repo.get(question_id)
        if not question:
            return None
        if question.category:
            count = self.repo._scope(question.source).filter(Question.category == question.category).count()
            return {
                "source": question.source,
                "category": question.category,
                "subcategory": question.subcategory or None,
                "question_type": None,
                "count": count,
                "label": f"{concept_label(question.category, question.subcategory)} ({count}문항)",
            }
        count = self.repo.questions_like(question).count()
        return {
            "source": question.source,
            "category": question.category or None,
            "question_type": question.question_type or None,
            "count": count,
            "label": f"{question.question_type or '전체 유형'} 유형 ({count}문항)",
        }

    def get_unit_question(
        self,
        question_id: Optional[int] = None,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        question_type: Optional[str] = None,
    ):
        if category:
            question = self.repo.get(question_id) if question_id else None
            if question and question.source == source and question.category == category:
                return question_payload(question, self.repo.count(source))
            question = self.repo.first_for_unit(source, category, subcategory)
        else:
            return self.get_weak_question(question_id, source=source, question_type=question_type)
        if not question:
            return None
        return question_payload(question, self.repo.count(source))

    def next_unit_question(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        question_type: Optional[str] = None,
    ):
        if category:
            question = self.repo.next_for_unit(current_id, source, category, subcategory)
            if not question:
                return {"end": True}
            return question_payload(question, self.repo.count(source))
        return self.next_weak_question(current_id, source=source, question_type=question_type)

    def previous_unit_question(
        self,
        current_id: int,
        source: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        question_type: Optional[str] = None,
    ):
        if category:
            question = self.repo.previous_for_unit(current_id, source, category, subcategory)
            if not question:
                return {"start": True}
            return question_payload(question, self.repo.count(source))
        return self.previous_weak_question(current_id, source=source, question_type=question_type)

    def add_review(self, question_id: int, user_id: str = DEFAULT_USER):
        self.repo.add_attempt(user_id=user_id, question_id=question_id, chosen=None, correct=False, note_type="review")
        return {"message": "복습 목록에 추가됨"}

    def remove_review(self, question_id: int, user_id: str = DEFAULT_USER):
        self.repo.remove_attempts(user_id=user_id, question_id=question_id, note_type="review")
        return {"message": "복습에서 제거됨"}

    def remove_wrong(self, question_id: int, user_id: str = DEFAULT_USER):
        self.repo.remove_attempts(user_id=user_id, question_id=question_id, note_type="wrong")
        return {"message": "오답에서 제거됨"}

    def wrong_review(self, user_id: str = DEFAULT_USER, source: Optional[str] = None):
        rows = self.repo.wrong_and_review(user_id, source)
        seen = set()
        items = []
        for attempt, question in rows:
            if question.id in seen:
                continue
            seen.add(question.id)
            items.append(
                {
                    "question_id": question.id,
                    "stem": question.stem,
                    "options": question.get_options(),
                    "answer": question.answer,
                    "explanation": question.explanation,
                    "chosen": attempt.chosen,
                    "source": question.source,
                    "category": question.category,
                    "image_path": question.image_path,
                }
            )
        return {"count": len(items), "items": items}

    def weak_types(self, user_id: str = DEFAULT_USER, source: Optional[str] = None):
        items = []
        for exam, category, subcategory, wrong_count in self.repo.weak_type_summaries(user_id, source):
            items.append(
                {
                    "source": exam,
                    "category": category or "",
                    "subcategory": subcategory or "",
                    "question_type": "",
                    "wrong_count": wrong_count,
                    "label": f"{concept_label(category, subcategory)} ({wrong_count}회)",
                }
            )
        return items

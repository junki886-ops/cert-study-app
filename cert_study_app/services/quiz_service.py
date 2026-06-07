from cert_study_app.config import DEFAULT_USER
from cert_study_app.models import Question
from cert_study_app.repositories.question_repository import QuestionRepository
from cert_study_app.services.text_cleanup_service import clean_inline_text
from cert_study_app.services.question_concept_service import concept_label
from typing import Optional
import json
import re


def normalize_options(raw):
    if not raw:
        return []
    try:
        if isinstance(raw, dict):
            keyed = []
            for k, v in sorted(raw.items(), key=lambda kv: kv[0]):
                value = clean_inline_text(v)
                if re.match(r"^[A-Za-z1-9][\.\)]\s+", value):
                    keyed.append(value)
                else:
                    keyed.append(f"{k}. {value}")
            return split_embedded_options(keyed)
        if isinstance(raw, list):
            return split_embedded_options(raw)
    except Exception:
        pass
    return []


def split_embedded_options(options: list[str]) -> list[str]:
    split = []
    expected = "A"
    for option in options:
        text = clean_inline_text(option)
        if not text:
            continue
        parts = list(re.finditer(r"(?<![A-Za-z0-9])([A-Z])[\.\)]\s+", text))
        if len(parts) <= 1:
            split.append(text)
            continue
        for index, match in enumerate(parts):
            end = parts[index + 1].start() if index + 1 < len(parts) else len(text)
            part = text[match.start() : end].strip()
            label = match.group(1).upper()
            if label >= expected:
                split.append(part)
                expected = chr(ord(label) + 1)
    return split


def extract_options_from_stem(stem: str) -> list[str]:
    lines = [line.strip() for line in (stem or "").splitlines() if line.strip()]
    options = []
    current_key = None
    current_parts = []
    expected = "A"

    def flush():
        if current_key and current_parts:
            text = " ".join(current_parts).strip()
            if text:
                options.append(f"{current_key}. {text}")

    for line in lines:
        if re.match(r"^(answer|정답|explanation|reference)\b", line, re.I):
            flush()
            current_key = None
            current_parts = []
            break

        marker = None
        body = ""
        exact = re.match(r"^([A-Z])[\.\)]?$", line, re.I)
        inline = re.match(r"^([A-Z])[\.\)]?\s+(.+)$", line, re.I)
        if exact:
            marker = exact.group(1).upper()
        elif inline:
            marker = inline.group(1).upper()
            body = inline.group(2).strip()

        if marker and marker >= expected:
            flush()
            current_key = marker
            current_parts = [body] if body else []
            expected = chr(ord(marker) + 1)
        elif current_key:
            current_parts.append(line)

    flush()
    return options if len(options) >= 2 else []


def extract_answer_from_stem(stem: str) -> str:
    match = re.search(r"(?:Answer|정답)\s*:?\s*([A-Z1-9])", stem or "", re.I)
    if not match:
        return ""
    value = match.group(1).upper()
    if value.isdigit():
        return chr(ord("A") + int(value) - 1)
    return value


def option_label(value: str) -> str:
    value = str(value or "").strip().upper()
    if value.isdigit():
        return chr(ord("A") + int(value) - 1)
    match = re.match(r"^([A-Z])(?:[\s\.,\)]|$)", value)
    return match.group(1) if match else value


def choice_labels(value: str) -> list[str]:
    text = str(value or "").strip().upper()
    if not text:
        return []
    if re.fullmatch(r"[A-Z]{2,26}", text):
        return list(text)
    tokens = re.findall(r"\b[A-Z]\b|\b[1-9]\b", text)
    return [option_label(token) for token in tokens]


def normalize_choice_answer(value: str, ordered: bool = False) -> str:
    yn = yes_no_labels(value)
    if yn:
        return ",".join(yn)
    labels = choice_labels(value)
    if not labels:
        return option_label(value)
    if ordered:
        return ",".join(labels)
    return ",".join(sorted(set(labels)))


def yes_no_labels(value: str) -> list[str]:
    if isinstance(value, (list, dict)):
        raw_value = value
    else:
        raw_value = None
        try:
            raw_value = json.loads(value) if isinstance(value, str) else None
        except Exception:
            raw_value = None

    if isinstance(raw_value, list):
        values = [
            item.get("value") or item.get("answer") or item.get("selected_answer")
            for item in raw_value
            if isinstance(item, dict)
        ]
        labels = yes_no_labels(",".join(str(item) for item in values if item))
        if labels:
            return labels
    elif isinstance(raw_value, dict):
        labels = yes_no_labels(",".join(str(item) for item in raw_value.values()))
        if labels:
            return labels

    text = str(value or "").strip().lower()
    if not text:
        return []
    if re.fullmatch(r"[yn](?:\s*,\s*[yn])+", text, re.I):
        return [token.upper() for token in re.findall(r"[yn]", text, re.I)]
    tokens = re.findall(r"(?<![가-힣])예(?![가-힣])|아니오|아니요|\byes\b|\bno\b", text, re.I)
    labels = []
    for token in tokens:
        lowered = token.lower()
        labels.append("Y" if token == "예" or lowered == "yes" else "N")
    return labels if len(labels) >= 2 else []


def structured_answer_values(value) -> list[str]:
    if isinstance(value, (list, dict)):
        raw_value = value
    else:
        try:
            raw_value = json.loads(value) if isinstance(value, str) else None
        except Exception:
            raw_value = None

    if isinstance(raw_value, list):
        values = [
            item.get("value") or item.get("answer") or item.get("selected_answer")
            for item in raw_value
            if isinstance(item, dict)
        ]
    elif isinstance(raw_value, dict):
        values = list(raw_value.values())
    else:
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def option_text(options: list[str], label: str) -> str:
    label = option_label(label)
    for index, option in enumerate(options, 1):
        text = str(option).strip()
        keys = {str(index), chr(ord("A") + index - 1)}
        match = re.match(r"^([A-Z1-9])[\.\)]\s+(.+)$", text, re.I)
        if match:
            keys.add(option_label(match.group(1)))
            if match.group(1).isdigit():
                keys.add(match.group(1))
        if label in keys:
            return text
    return ""


def _option_body(option: str) -> str:
    text = str(option or "").strip()
    match = re.match(r"^([A-Z1-9])[\.\)]\s+(.+)$", text, re.I)
    return (match.group(2) if match and match.group(2) else text).strip()


def option_labels_from_texts(options: list[str], values, allow_duplicates: bool = False) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    labels = []
    for value in values:
        target = re.sub(r"\s+", " ", str(value or "").strip()).lower()
        if not target:
            continue
        for index, option in enumerate(options, 1):
            body = re.sub(r"\s+", " ", _option_body(option)).lower()
            if body and (target == body or target in body or body in target):
                label = chr(ord("A") + index - 1)
                if allow_duplicates or label not in labels:
                    labels.append(label)
                break
    return labels


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
    question_type = (question.question_type or "").lower()
    options = normalize_options(question.get_options()) or extract_options_from_stem(question.stem)
    structured_values = structured_answer_values(answer)
    if structured_values:
        structured_yn = yes_no_labels(",".join(structured_values))
        return ",".join(structured_yn or structured_values)

    is_structured_visual = any(
        keyword in question_type
        for keyword in ["hotspot", "table_choice", "matching", "ordering", "yes_no", "true/false"]
    ) and "in-context" not in question_type
    if is_structured_visual:
        answer_labels = yes_no_labels(answer)
        if answer_labels and "true/false" in question_type:
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
    ordered = (question.question_type or "").lower() in {"ordering", "table_choice", "hotspot"}
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
    correct = normalize_choice_answer(chosen, ordered=ordered) == normalize_choice_answer(answer, ordered=ordered)

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
        ordered = (question.question_type or "").lower() in {"ordering", "table_choice", "hotspot"}
        correct = normalize_choice_answer(chosen, ordered=ordered) == normalize_choice_answer(answer, ordered=ordered)
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

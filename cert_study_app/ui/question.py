import json
import re
from pathlib import Path

import streamlit as st

from cert_study_app.config import DEFAULT_USER
from cert_study_app.db import SessionLocal
from cert_study_app.services.concept_note_service import ConceptNoteService
from cert_study_app.services.question_type_metadata_service import normalize_question_type
from cert_study_app.services.quiz_service import yes_no_labels

from cert_study_app.ui.common import DEFAULT_FAST_MODEL


PARENT_STEM_HEADINGS: frozenset[str] = frozenset({
    "개요",
    "일반 개요",
    "기존 환경",
    "환경",
    "요구사항",
    "요구 사항",
    "계획된 변경",
    "기술 요구 사항",
    "사용자 요구 사항",
    "인증 요구 사항",
    "부서 요구 사항",
    "네트워크 인프라",
    "Active Directory 환경",
    "라이센스 문제",
    "문제 설명",
})


def render_question_image(question):
    image_path = question.get("image_path")
    if image_path and Path(image_path).exists():
        key = f"show_image_v2_{question.get('id')}"
        visual_types = {"hotspot", "table_choice", "ordering", "matching"}
        label = "문제 그림 보기" if (question.get("question_type") or "").lower() in visual_types else "원문 이미지 보기"
        show_image = st.toggle(label, key=key, value=False)
        if show_image:
            st.image(image_path, use_container_width=True)


def display_question_text(text: str) -> str:
    return re.sub(r"^\s*\d{1,3}\s*[.)]\s*", "", text or "", count=1).strip()


def display_parent_text(text: str) -> str:
    lines = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        topic_match = re.match(r"^\s*\d{1,3}\s*[.)]\s*(주제\s+\d+\s*,?\s*.+)$", line)
        if topic_match:
            line = topic_match.group(1).strip()
        if re.search(r"\d{1,3}\s*[~～-]\s*\d{1,3}\s*번\s*문제\)?", line):
            continue
        if re.fullmatch(r"\(?\s*\d{1,3}\s*[~～-]\s*\d{1,3}\s*\)?", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def group_start_number(group_id: str):
    match = re.match(r"q(\d{1,3})(?:-|$)", group_id or "")
    return int(match.group(1)) if match else None


def is_first_group_question(question) -> bool:
    start = group_start_number(question.get("group_id") or "")
    return bool(start and int(question.get("number") or 0) == start)


def split_parent_sections(text: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in display_parent_text(text).splitlines() if line.strip()]
    sections = []
    title = "요약"
    body = []
    for line in lines:
        normalized = line.rstrip(":")
        is_heading = normalized in PARENT_STEM_HEADINGS or (
            len(normalized) <= 24 and any(keyword in normalized for keyword in ["요구", "환경", "개요", "문제"])
        )
        if is_heading and body:
            sections.append((title, "\n".join(body).strip()))
            title = normalized
            body = []
        elif is_heading:
            title = normalized
        else:
            body.append(line)
    if body:
        sections.append((title, "\n".join(body).strip()))
    return [(title, body) for title, body in sections if body] or [("전체", display_question_text(text))]


def format_parent_stem(text: str) -> str:
    rendered = []
    for raw_line in display_parent_text(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = line.rstrip(":")
        is_heading = normalized in PARENT_STEM_HEADINGS or (
            len(normalized) <= 24 and any(keyword in normalized for keyword in ["요구", "환경", "개요", "문제"])
        )
        if is_heading:
            rendered.append(f"\n**{normalized}**")
        elif line.startswith(("•", "✑", "-", "①", "②", "③", "④")):
            rendered.append(f"- {line.lstrip('•✑- ').strip()}")
        else:
            rendered.append(line)
    return "\n\n".join(rendered).strip()


def render_question_header(question, context_label=None):
    number = question.get("number") or question.get("id")
    meta = [f"문제 {number}번"]
    if context_label:
        meta.append(context_label)
    elif question.get("concept_label") and question.get("category"):
        meta.append(question["concept_label"])
    if question.get("source"):
        meta.append(question["source"])
    if question.get("page"):
        meta.append(f"p.{question['page']}")
    st.markdown(f"### {meta[0]}")
    if len(meta) > 1:
        st.caption(" · ".join(meta[1:]))
    if question.get("concept_tags"):
        st.caption("개념 태그: " + ", ".join(question["concept_tags"]))


def render_parent_stem(question):
    parent_stem = question.get("parent_stem")
    parent_image_paths = question.get("parent_image_paths") or []
    has_parent_stem = bool(display_parent_text(parent_stem).strip())
    if has_parent_stem:
        if st.toggle("공통 지문 보기", key=f"show_parent_v2_{question.get('id')}", value=is_first_group_question(question)):
            st.markdown(format_parent_stem(parent_stem))
    if has_parent_stem and parent_image_paths:
        if st.toggle("공통 지문 원문 페이지 보기", key=f"show_parent_images_v2_{question.get('id')}", value=False):
            for index, image_path in enumerate(parent_image_paths, 1):
                if Path(image_path).exists():
                    st.caption(f"공통 지문 원문 {index}/{len(parent_image_paths)}")
                    st.image(image_path, use_container_width=True)


def render_answer_result(result):
    if result["correct"]:
        st.success("정답입니다.")
    else:
        st.error(f"오답입니다. 정답: {result['answer']}")
    if result.get("explanation"):
        st.markdown('<div class="answer-explanation">', unsafe_allow_html=True)
        st.markdown(result["explanation"])
        st.markdown("</div>", unsafe_allow_html=True)


def render_concept_candidates(question):
    import os
    key = f"concept_candidates_{question['id']}"
    st.markdown("#### 개념 정리")
    if st.button("개념 후보 보기", use_container_width=True, key=f"generate_concepts_{question['id']}"):
        db = SessionLocal()
        try:
            service = ConceptNoteService(db)
            with st.spinner("qwen이 저장할 만한 개념 후보를 찾는 중입니다."):
                st.session_state[key] = service.generate_candidates(
                    question["id"],
                    model=DEFAULT_FAST_MODEL,
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                )
        except Exception as exc:
            st.error(f"개념 후보 생성 실패: {exc}")
        finally:
            db.close()

    candidates = st.session_state.get(key) or []
    if not candidates:
        st.caption("필요한 개념만 저장할 수 있도록 후보를 먼저 확인합니다.")
        return

    for index, candidate in enumerate(candidates, 1):
        with st.container(border=True):
            name = st.text_input("개념명", value=candidate.get("concept_name", ""), key=f"concept_name_{question['id']}_{index}")
            summary = st.text_area("핵심 요약", value=candidate.get("summary", ""), height=80, key=f"concept_summary_{question['id']}_{index}")
            exam_point = st.text_area("시험 포인트", value=candidate.get("exam_point", ""), height=80, key=f"concept_exam_{question['id']}_{index}")
            trap_point = st.text_area("헷갈릴 포인트", value=candidate.get("trap_point", ""), height=80, key=f"concept_trap_{question['id']}_{index}")
            keywords = st.text_input(
                "키워드",
                value=", ".join(candidate.get("keywords") or []),
                key=f"concept_keywords_{question['id']}_{index}",
            )
            if st.button("이 개념 저장", use_container_width=True, key=f"save_concept_{question['id']}_{index}"):
                payload = {
                    "concept_name": name,
                    "summary": summary,
                    "exam_point": exam_point,
                    "trap_point": trap_point,
                    "keywords": [item.strip() for item in keywords.split(",") if item.strip()],
                }
                db = SessionLocal()
                try:
                    ConceptNoteService(db).save_candidate(payload, question["id"], DEFAULT_USER)
                    st.success("개념을 저장했습니다.")
                finally:
                    db.close()


def visual_analysis_data(question) -> dict:
    raw = ""
    if isinstance(question, dict):
        raw = question.get("visual_analysis_json") or ""
    else:
        raw = getattr(question, "visual_analysis_json", "") or ""
    try:
        analysis = json.loads(raw or "{}")
    except Exception:
        return {}
    return analysis if isinstance(analysis, dict) else {}


def visual_answer_areas(question) -> list[dict]:
    analysis = visual_analysis_data(question)
    areas = analysis.get("answer_areas") if isinstance(analysis, dict) else None
    if isinstance(areas, list):
        return [area for area in areas if isinstance(area, dict)]
    return []


def visual_source_content(question) -> str:
    analysis = visual_analysis_data(question)
    value = analysis.get("source_content") or analysis.get("source") or analysis.get("evidence")
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value or "").strip()


def visual_answer_areas_to_text(areas: list[dict]) -> str:
    lines = []
    for area in areas:
        label = str(area.get("label") or area.get("text") or "").strip()
        selected = str(area.get("selected_answer") or area.get("answer") or "").strip()
        options = area.get("options") or []
        if isinstance(options, str):
            options_text = options.strip()
        elif isinstance(options, list):
            options_text = ", ".join(str(option).strip() for option in options if str(option).strip())
        else:
            options_text = ""
        if label or options_text or selected:
            lines.append(f"{label} | {options_text} | {selected}")
    return "\n".join(lines)


def parse_visual_answer_areas_text(text: str) -> list[dict]:
    areas = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        label = parts[0] if len(parts) >= 1 else ""
        options_text = parts[1] if len(parts) >= 2 else ""
        selected = parts[2] if len(parts) >= 3 else ""
        options = [item.strip() for item in re.split(r"\s*,\s*", options_text) if item.strip()]
        area = {"label": label, "options": options, "selected_answer": selected}
        if label or options or selected:
            areas.append(area)
    return areas


def visual_selected_answers(areas: list[dict]) -> str:
    answers = []
    for area in areas:
        label = str(area.get("label") or "").strip()
        selected = str(area.get("selected_answer") or area.get("answer") or "").strip()
        if selected:
            answers.append(f"{label}: {selected}" if label else selected)
    return "\n".join(answers)


def remove_duplicate_visual_labels(question_text: str, labels: list[str]) -> str:
    lines = []
    normalized_labels = {re.sub(r"\s+", " ", label).strip().lower() for label in labels if label}
    for raw_line in (question_text or "").splitlines():
        normalized_line = re.sub(r"\s+", " ", raw_line).strip().lower()
        if normalized_line in normalized_labels:
            continue
        lines.append(raw_line)
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def visual_statements(question) -> list[dict]:
    try:
        analysis = json.loads(question.get("visual_analysis_json") or "{}")
    except Exception:
        return []
    statements = analysis.get("statements") if isinstance(analysis, dict) else None
    if isinstance(statements, list):
        return [statement for statement in statements if isinstance(statement, dict)]
    return []


def render_question_body(question):
    render_parent_stem(question)
    question_text = display_question_text(question.get("question") or "")
    source_content = visual_source_content(question)
    answer_area_labels = [
        str(area.get("label") or "").strip()
        for area in visual_answer_areas(question)
        if str(area.get("label") or "").strip()
    ]
    if answer_area_labels:
        question_text = remove_duplicate_visual_labels(question_text, answer_area_labels)
    if question_text:
        st.markdown(question_text.replace("\n", "  \n"))
    if source_content:
        st.markdown("#### 문제 근거")
        st.code(source_content)


def option_display_and_value(option, index):
    raw = str(option).strip()
    match = re.match(r"^([A-Za-z]|\d+)\s*[\.\)]\s*(.+)$", raw, re.S)
    if match:
        value = match.group(1).strip()
        text = match.group(2).strip()
        return f"{value}. {text}", value
    else:
        value = str(index)
        text = raw
    return text, value


def answer_labels(value: str) -> list[str]:
    text = str(value or "").strip().upper()
    if not text:
        return []
    if re.fullmatch(r"[A-Z]{2,26}", text):
        return list(text)
    tokens = re.findall(r"\b[A-Z]\b|\b[1-9]\b", text)
    labels = []
    for token in tokens:
        if token.isdigit():
            labels.append(chr(ord("A") + int(token) - 1))
        else:
            labels.append(token)
    return labels


def is_multi_answer(question) -> bool:
    labels = answer_labels(question.get("answer") or "")
    if len(set(labels)) > 1:
        return True
    text = question.get("question") or ""
    return bool(
        re.search(
            r"(두\s*가지|세\s*가지|네\s*가지|모두\s*선택|복수|각각\s*선택|choose\s+two|choose\s+three|select\s+two|select\s+three)",
            text,
            re.I,
        )
    )


def is_per_row_choice(question) -> bool:
    question_type = normalize_question_type(question.get("question_type"))
    if question_type not in {"table_choice", "hotspot", "matching"}:
        return False
    if visual_answer_areas(question):
        return True
    labels = answer_labels(question.get("answer") or "")
    text = "\n".join(
        [
            question.get("question") or "",
            question.get("explanation") or "",
            question.get("answer") or "",
        ]
    )
    if re.search(r"(어떤\s*(두|세|네)\s*가지|각\s*정답|각\s*올바른\s*선택|choose\s+two|choose\s+three|select\s+two|select\s+three)", text, re.I):
        return False
    if len(labels) <= 1 and not re.search(r"(?:상자|Box)\s*1", text, re.I):
        return False
    return bool(re.search(r"(각\s*리소스|각\s*항목|각\s*행|답변\s*영역|드롭다운|적절한\s*옵션|(?:상자|Box)\s*1)", text, re.I))


def detected_box_labels(question) -> list[str]:
    areas = visual_answer_areas(question)
    if areas:
        labels = []
        for index, area in enumerate(areas, 1):
            label = str(area.get("label") or "").strip()
            labels.append(label or f"상자 {index}")
        return labels

    text = "\n".join(
        [
            question.get("question") or "",
            question.get("explanation") or "",
            question.get("answer") or "",
        ]
    )
    labels = []
    for match in re.finditer(r"(?:상자|Box)\s*([0-9]+)", text, re.I):
        label = f"상자 {int(match.group(1))}"
        if label not in labels:
            labels.append(label)
    return labels


def box_choice_labels(question, count: int) -> list[str]:
    labels = detected_box_labels(question)
    if len(labels) >= count:
        return labels[:count]
    labels = [f"상자 {index + 1}" for index in range(count)]
    return labels


def yes_no_answer_labels(value: str) -> list[str]:
    return yes_no_labels(value)


def is_yes_no_hotspot(question) -> bool:
    question_type = normalize_question_type(question.get("question_type"))
    if question_type not in {"yes_no", "hotspot", "table_choice"}:
        return False
    if question_type == "yes_no":
        return True
    text = " ".join(
        [
            question.get("question") or "",
            question.get("answer") or "",
            question.get("explanation") or "",
            " ".join(str(option) for option in question.get("options") or []),
        ]
    )
    return bool(
        re.search(r"다음\s*각\s*(진술|설명|항목)|각\s*(진술|설명|항목).*예|예를\s*선택|아니오를\s*선택|아니요를\s*선택", text)
    )


def statement_option_rows(options: list[str], expected_count: int) -> list[str]:
    rows = []
    for option in options or []:
        text = str(option or "").strip()
        if not text:
            continue
        cleaned = re.sub(r"^\s*(?:[0-9]+|[A-Z])[-.)]\s*", "", text).strip()
        if re.fullmatch(r"예|아니오|아니요|yes|no", cleaned, re.I):
            continue
        rows.append(cleaned)
    if expected_count and len(rows) >= expected_count:
        return rows[:expected_count]
    return rows


def grouped_option_rows(options: list[str]) -> list[dict]:
    grouped = {}
    order = []
    for option in options or []:
        text = str(option or "").strip()
        match = re.match(r"^\s*(\d+)-([A-Z])[\.)]?\s*(.+)$", text, re.I)
        if not match:
            continue
        group_key = match.group(1)
        body = match.group(3).strip()
        row_label = f"항목 {group_key}"
        value = body
        if ":" in body:
            row_label, value = [part.strip() for part in body.split(":", 1)]
        if group_key not in grouped:
            grouped[group_key] = {"label": row_label, "options": []}
            order.append(group_key)
        grouped[group_key]["options"].append(value)
    rows = [grouped[key] for key in order]
    return rows if len(rows) >= 2 and all(row["options"] for row in rows) else []


def yes_no_lines(question_text: str) -> list[str]:
    lines = []
    for raw_line in (question_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\d{1,3}\s*[.)]", line):
            continue
        if any(skip in line for skip in ["참고:", "답변하려면", "올바른 선택", "무엇을", "이것이 목표"]):
            continue
        if re.search(r"(=|예|아니오|수 있습니다|해야 합니다|지원|허용|가능)", line):
            cleaned = re.sub(r"^\s*[•✑①②③④⑤\-\d.)]+\s*", "", line).strip()
            if len(cleaned) >= 8:
                lines.append(cleaned)
    return lines[-4:]


def render_grouped_option_selects(question, key_prefix, rows):
    selections = []
    all_yes_no = all(
        all(str(option).strip().lower() in {"yes", "no", "예", "아니오", "아니요"} for option in row["options"])
        for row in rows
    )
    st.markdown("#### 항목별 답안")
    for index, row in enumerate(rows, 1):
        options = [str(option).strip() for option in row["options"] if str(option).strip()]
        selected = st.selectbox(
            row["label"] or f"항목 {index}",
            ["선택 안 함"] + options,
            key=f"{key_prefix}_grouped_options_{question['id']}_{index}",
        )
        if selected != "선택 안 함":
            if all_yes_no:
                selections.append("Y" if selected.lower() in {"yes", "예"} else "N")
            else:
                selections.append(selected)
    return ",".join(selections) if len(selections) == len(rows) else None


def render_yes_no_matrix(question, key_prefix, rows, caption="진술별 답안"):
    selections = []
    st.markdown(f"#### {caption}")
    for index, row in enumerate(rows, 1):
        selected = st.radio(
            row,
            ["예", "아니오"],
            index=None,
            horizontal=True,
            key=f"{key_prefix}_yn_matrix_{question['id']}_{index}",
        )
        if selected:
            selections.append("Y" if selected == "예" else "N")
    return ",".join(selections) if len(selections) == len(rows) else None


def render_answer_input(question, key_prefix):
    options = question["options"]
    question_type = normalize_question_type(question.get("question_type"))
    statement_rows = [
        str(statement.get("text") or "").strip()
        for statement in visual_statements(question)
        if str(statement.get("text") or "").strip()
    ]
    if statement_rows:
        return render_yes_no_matrix(question, f"{key_prefix}_statements", statement_rows)

    grouped_rows = grouped_option_rows(options)
    if grouped_rows:
        return render_grouped_option_selects(question, key_prefix, grouped_rows)

    if is_yes_no_hotspot(question):
        answer_count = len(yes_no_answer_labels(question.get("answer") or "")) or len(
            yes_no_answer_labels(question.get("explanation") or "")
        )
        row_count = max(3, answer_count, len(statement_rows))
        rows = statement_option_rows(options, row_count) or yes_no_lines(question.get("question") or "")
        if statement_rows:
            rows = statement_rows
        if len(rows) < row_count:
            rows = [f"진술 {index + 1}" for index in range(row_count)]
        return render_yes_no_matrix(question, f"{key_prefix}_hotspot", rows[:row_count])

    if not options:
        answer = str(question.get("answer") or "").upper()
        if question_type in {"yes_no", "table_choice", "hotspot"} and re.search(r"(예|아니오|아니요|YES|NO|Y|N)", answer, re.I):
            rows = yes_no_lines(question.get("question") or "") or ["진술 1", "진술 2", "진술 3"]
            return render_yes_no_matrix(question, key_prefix, rows)

        st.warning("이 문제는 보기가 아직 구조화되지 않아 풀이에서 제외해야 합니다. 문제 검수에서 보기/상자/진술을 먼저 정리해 주세요.")
        return None

    display_to_value = {}
    display_options = []
    for index, option in enumerate(options, 1):
        display, value = option_display_and_value(option, index)
        display_options.append(display)
        display_to_value[display] = value

    if is_per_row_choice(question):
        areas = visual_answer_areas(question)
        detected_box_count = len(detected_box_labels(question))
        expected_count = max(2, len(answer_labels(question.get("answer") or "")), min(detected_box_count, 8))
        selections = []
        row_labels = box_choice_labels(question, expected_count)
        st.markdown("#### 상자별 답안")
        for index, row_label in enumerate(row_labels):
            row_options = areas[index].get("options") if index < len(areas) else None
            current_display_options = display_options
            current_display_to_value = display_to_value
            if isinstance(row_options, list) and row_options:
                current_display_options = []
                current_display_to_value = {}
                for row_option_index, row_option in enumerate(row_options, 1):
                    display, _ = option_display_and_value(row_option, row_option_index)
                    matched_value = None
                    row_text = re.sub(r"\s+", " ", str(row_option).strip()).lower()
                    for global_display, global_value in display_to_value.items():
                        global_text = re.sub(r"\s+", " ", str(global_display).strip()).lower()
                        if row_text == global_text or row_text in global_text or global_text in row_text:
                            matched_value = global_value
                            break
                    current_display_options.append(display)
                    current_display_to_value[display] = matched_value or str(row_option_index)
            selected = st.selectbox(
                row_label,
                ["선택 안 함"] + current_display_options,
                key=f"{key_prefix}_row_choice_{question['id']}_{index}",
            )
            if selected != "선택 안 함":
                selections.append(current_display_to_value[selected])
        return ",".join(selections) if len(selections) == expected_count else None

    if is_multi_answer(question):
        st.markdown("#### 정답 선택")
        values = []
        for index, display in enumerate(display_options, 1):
            checked = st.checkbox(
                display,
                key=f"{key_prefix}_multi_choice_{question['id']}_{index}",
            )
            if checked:
                values.append(display_to_value[display])
        return ",".join(values) if values else None

    selected = st.radio(
        "정답 선택",
        display_options,
        index=None,
        label_visibility="collapsed",
        key=f"{key_prefix}_choice_{question['id']}",
    )
    return display_to_value.get(selected) if selected else None

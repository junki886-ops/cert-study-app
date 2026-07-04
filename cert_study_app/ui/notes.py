import os
import re
from pathlib import Path

import streamlit as st

from cert_study_app.config import DEFAULT_USER
from cert_study_app.db import SessionLocal
from cert_study_app.services.concept_note_service import ConceptNoteService
from cert_study_app.services.learning_progress_service import (
    mark_learning_step,
    record_activity,
    save_wrong_notes,
    study_units,
    save_preferred_track,
)
from cert_study_app.services.study_assistant_service import StudyAssistantService
from cert_study_app.services.vector_service import QuestionVectorStore

from cert_study_app.ui.common import (
    DEFAULT_DEEP_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_FAST_MODEL,
    DEFAULT_MAIN_MODEL,
    EMBEDDING_MODEL_OPTIONS,
    get_service,
    go_to,
    track_for_question_source,
)


def options_to_text(options) -> str:
    if isinstance(options, dict):
        lines = []
        for key, value in options.items():
            value = str(value).strip()
            if re.match(r"^[A-Ea-e1-5][\.\)]\s+", value):
                lines.append(value)
            else:
                lines.append(f"{key}. {value}")
        return "\n".join(lines)
    if isinstance(options, list):
        return "\n".join(str(option) for option in options)
    return ""


def parse_options_text(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def render_notes(source=None):
    concept_notes = st.session_state.get("lab_wrong_notes", [])
    db, service = get_service()
    try:
        payload = service.wrong_review(DEFAULT_USER, source)
    finally:
        db.close()

    db_count = payload["count"]
    concept_count = len(concept_notes)
    total = db_count + concept_count
    st.subheader(f"오답/복습 {total}개")

    tab_labels = [
        f"AZ-104 덤프 오답 ({db_count})",
        f"개념 학습 오답 · 이론/CLI ({concept_count})",
    ]
    tab_cert, tab_concept = st.tabs(tab_labels)

    with tab_cert:
        if not payload["items"]:
            st.info("자격증 문제 오답이 없습니다.")
        db2, service2 = get_service()
        try:
            for item in payload["items"]:
                title_parts = [f"#{item['question_id']}"]
                if item.get("source"):
                    title_parts.append(item["source"])
                title_parts.append(item["stem"][:80])
                with st.expander(" · ".join(title_parts)):
                    st.write(item["stem"])
                    st.write("정답:", item["answer"])
                    if item.get("image_path") and Path(item["image_path"]).exists():
                        st.image(item["image_path"], use_container_width=True)
                    if item.get("chosen"):
                        st.write("내 답:", item["chosen"])
                    if item.get("explanation"):
                        st.write(item["explanation"])
                    if item.get("category"):
                        st.caption(f"세부개념: {item.get('concept_label')}")
                    col_done, col_go = st.columns(2)
                    if col_done.button("복습 완료", use_container_width=True, key=f"review_done_{item['question_id']}"):
                        src_track = track_for_question_source(item.get("source"))
                        mark_learning_step(src_track, "review")
                        record_activity(src_track, "review", 1)
                        st.success(f"복습을 기록했습니다. 오늘 활동 {study_units():.1f}단위")
                    if col_go.button("이 문제 풀기", use_container_width=True, key=f"go_quiz_{item['question_id']}"):
                        st.session_state.question_id = item["question_id"]
                        st.session_state.exam_source = item.get("source")
                        st.session_state.selected = None
                        st.session_state.last_result = None
                        go_to("자격증 문제")
                    concept_col, focus_col = st.columns(2)
                    if concept_col.button(
                        "같은 개념 풀기",
                        use_container_width=True,
                        key=f"go_same_concept_{item['question_id']}",
                        disabled=not item.get("category"),
                    ):
                        st.session_state.similar_type = {
                            "source": item.get("source"),
                            "category": item.get("category"),
                            "subcategory": item.get("subcategory"),
                            "question_type": None,
                            "label": item.get("concept_label") or "같은 개념",
                        }
                        st.session_state.exam_source = item.get("source")
                        st.session_state.question_id = None
                        st.session_state.selected = None
                        st.session_state.last_result = None
                        go_to("같은 단원 학습")
                    if focus_col.button("Focus 개념 보기", use_container_width=True, key=f"go_focus_{item['question_id']}"):
                        track_id = track_for_question_source(item.get("source"))
                        st.session_state.lab_track = track_id
                        save_preferred_track(track_id)
                        go_to("이론 학습")
        finally:
            db2.close()

    with tab_concept:
        if not concept_notes:
            st.info("개념 퀴즈 오답이 없습니다. 개념 공부에서 문제를 풀면 틀린 항목이 여기에 쌓입니다.")
        else:
            if st.button("전체 초기화", key="clear_concept_wrong"):
                st.session_state.lab_wrong_notes = []
                save_wrong_notes([])
                st.rerun()
            for idx, note in enumerate(concept_notes):
                track_label = {"linux": "Linux", "azure": "Azure", "tool_docs": "Docs"}.get(note.get("track"), note.get("track", ""))
                header = f"[{track_label}] {note['question'][:70]}"
                with st.expander(header):
                    st.write(note["question"])
                    col_ans, col_mine = st.columns(2)
                    col_ans.markdown(f"**정답** {note['correct_answer']}")
                    col_mine.markdown(f"**내 답** {note['user_answer']}")
                    if note.get("explanation"):
                        st.info(note["explanation"])
                    if st.button("복습 완료 — 목록에서 제거", key=f"concept_done_{idx}_{note['id']}"):
                        st.session_state.lab_wrong_notes = [
                            n for n in st.session_state.lab_wrong_notes if n["id"] != note["id"]
                        ]
                        save_wrong_notes(st.session_state.lab_wrong_notes)
                        mark_learning_step(note.get("track", "linux"), "review")
                        record_activity(note.get("track", "linux"), "review", 1)
                        st.rerun()


def render_quiz_assistant(current_question, source=None):
    ask_with_question = st.checkbox("현재 문제 포함", value=True)
    question = st.text_area(
        "궁금한 내용",
        placeholder="예: 이 문제에서 시험장 함정 포인트가 뭐야?",
        height=110,
    )
    with st.expander("LLM 설정"):
        model_options = [
            {
                "mode": "fast",
                "label": f"빠른 검색 ({DEFAULT_FAST_MODEL})",
                "model": DEFAULT_FAST_MODEL,
                "k": 2,
                "max_context_chars": 1600,
            },
            {
                "mode": "normal",
                "label": f"일반 검색 ({DEFAULT_MAIN_MODEL})",
                "model": DEFAULT_MAIN_MODEL,
                "k": 4,
                "max_context_chars": 3200,
            },
        ]
        if DEFAULT_DEEP_MODEL:
            model_options.append(
                {
                    "mode": "deep",
                    "label": f"심층 검색 ({DEFAULT_DEEP_MODEL})",
                    "model": DEFAULT_DEEP_MODEL,
                    "k": 6,
                    "max_context_chars": 4800,
                }
            )
        model_label = st.selectbox(
            "검색 모드",
            [option["label"] for option in model_options],
            index=0,
            help="속도가 중요하면 빠른 검색을 사용하세요. 심층 검색은 OLLAMA_DEEP_MODEL을 설정하면 나타납니다.",
        )
        selected_model_option = next(option for option in model_options if option["label"] == model_label)
        llm_model = selected_model_option["model"]
        ollama_base_url = st.text_input(
            "Ollama URL",
            value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        embedding_model = st.selectbox(
            "임베딩 모델",
            EMBEDDING_MODEL_OPTIONS,
            index=EMBEDDING_MODEL_OPTIONS.index(DEFAULT_EMBEDDING_MODEL)
            if DEFAULT_EMBEDDING_MODEL in EMBEDDING_MODEL_OPTIONS
            else 0,
            help="질의응답 검색에 사용할 벡터 임베딩 모델입니다. 색인할 때 사용한 모델과 같아야 검색됩니다.",
        )
        k = st.slider("검색 문서 수", min_value=1, max_value=8, value=int(selected_model_option["k"]))

    db = SessionLocal()
    try:
        service = StudyAssistantService(
            db,
            vector_store=QuestionVectorStore(embedding_model=embedding_model),
        )
    except Exception as exc:
        st.error(f"AI 검색 서비스 초기화 실패: {exc}")
        st.caption("임베딩 모델 로드나 ChromaDB 초기화 오류입니다. 잠시 후 다시 시도하거나 임베딩 모델 설정을 확인하세요.")
        db.close()
        return
    try:
        if st.button("질문하기", type="primary", use_container_width=True):
            if not question.strip():
                st.warning("질문을 입력해 주세요.")
                return
            prompt = question.strip()
            if ask_with_question and current_question:
                options_text = "\n".join(str(option) for option in current_question.get("options") or [])
                concept_bits = [
                    current_question.get("concept_label") or "",
                    ", ".join(current_question.get("concept_tags") or []),
                ]
                concept_text = " / ".join(bit for bit in concept_bits if bit)
                prompt = (
                    "현재 문제를 1순위로 보고 답변해줘. 검색된 유사 문제는 보조 참고로만 사용해줘.\n\n"
                    f"현재 문제 번호: {current_question.get('number')}\n"
                    f"현재 문제 유형: {current_question.get('question_type') or ''}\n"
                    f"현재 문제 개념: {concept_text or '미분류'}\n\n"
                    "현재 문제 본문:\n"
                    f"{current_question.get('question') or ''}\n\n"
                    "현재 문제 보기:\n"
                    f"{options_text or '보기 없음'}\n\n"
                    f"내 질문:\n{prompt}"
                )
            try:
                with st.spinner("관련 문제를 검색하는 중입니다."):
                    result = service.ask_stream(
                        question=prompt,
                        model=llm_model,
                        base_url=ollama_base_url,
                        k=k,
                        source=source,
                        max_context_chars=int(selected_model_option["max_context_chars"]),
                    )
                if result.get("cached"):
                    st.caption("캐시된 답변")
                    st.markdown(result["answer"])
                else:
                    answer_placeholder = st.empty()
                    answer_chunks = []
                    for chunk in result["stream"]:
                        answer_chunks.append(chunk)
                        answer_placeholder.markdown("".join(answer_chunks))

                with st.expander("검색된 근거"):
                    for search_result in result["sources"]:
                        metadata = search_result["metadata"]
                        source_type = metadata.get("source_type") or "question"
                        title = metadata.get("title") or ""
                        url = metadata.get("url") or ""
                        st.caption(
                            f"type={source_type} · id={search_result['id']} · "
                            f"score={search_result['score']} · source={metadata.get('source', '')}"
                        )
                        if title:
                            st.markdown(f"**{title}**")
                        if url:
                            st.caption(url)
                        st.write(search_result["text"])
            except Exception as exc:
                st.error(f"AI 질문 처리 중 오류가 발생했습니다: {exc}")
                st.caption(f"Ollama URL({ollama_base_url})이 실행 중인지, 모델({llm_model})이 설치되어 있는지 확인하세요.")
    finally:
        db.close()


def render_concept_notes(source=None):
    st.subheader("개념 정리")
    db = SessionLocal()
    try:
        service = ConceptNoteService(db)
        query = st.text_input("개념 검색", placeholder="예: Load Balancer, NSG, Recovery Services Vault")
        notes = service.list_notes(source=source, query=query, limit=100)
        if not notes:
            st.info("아직 저장된 개념이 없습니다. 문제를 풀고 채점 후 '개념 후보 보기'에서 필요한 개념만 저장해 보세요.")
            return

        labels = [f"{note.concept_name} · #{note.id}" for note in notes]
        selected = st.selectbox("개념", range(len(notes)), format_func=lambda idx: labels[idx])
        note = notes[selected]

        st.markdown(f"### {note.concept_name}")
        if note.summary:
            st.markdown("#### 핵심 요약")
            st.write(note.summary)
        if note.exam_point:
            st.markdown("#### 시험 포인트")
            st.write(note.exam_point)
        if note.trap_point:
            st.markdown("#### 헷갈릴 포인트")
            st.write(note.trap_point)
        keywords = note.keyword_list()
        if keywords:
            st.caption(" · ".join(keywords))

        st.divider()
        st.markdown("#### 관련 문제")
        related = service.related_questions(note, limit=20)
        if not related:
            st.caption("아직 연결된 관련 문제를 찾지 못했습니다.")
            return
        for question in related:
            with st.container(border=True):
                number = question.question_number or question.id
                st.markdown(f"**문제 {number}번**")
                st.write((question.stem or "")[:240])
                if st.button("이 문제 풀기", key=f"concept_related_{note.id}_{question.id}", use_container_width=True):
                    st.session_state.exam_source = question.source
                    st.session_state.question_id = question.id
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    go_to("문제 풀이")
    finally:
        db.close()

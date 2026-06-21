import os
import re
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import func

from cert_study_app.config import DEFAULT_USER, ensure_runtime_dirs
from cert_study_app.db import SessionLocal, init_db
from cert_study_app.models import Attempt, Question
from cert_study_app.services.airflow_service import AirflowService, AirflowTriggerError
from cert_study_app.services.azure_docs_service import AzureDocsService
from cert_study_app.services.concept_note_service import ConceptNoteService
from cert_study_app.services.demo_seed_service import seed_demo_questions_if_empty
from cert_study_app.services.ingestion_job_service import IngestionJobService
from cert_study_app.services.learning_lab_service import (
    PRACTICE_TASKS,
    active_tracks,
    certification_for_track,
    evaluate_lab_quiz,
    evaluate_practice,
    lessons_for_track,
    normalize_track_id,
    quizzes_for_track,
    roadmap_for_track,
    track_by_id,
    track_progress,
)
from cert_study_app.services.learning_progress_service import (
    completed_steps,
    mark_learning_step,
    next_day_recommendation,
    preferred_track,
    record_activity,
    save_preferred_track,
    streak_days,
    study_units,
    weekly_summary,
)
from cert_study_app.services.parse_quality_service import default_quality_report_path
from cert_study_app.services.question_type_metadata_service import (
    automation_summary,
    normalize_question_type,
    status_label,
    type_metadata,
)
from cert_study_app.services.question_concept_service import (
    CATEGORY_LABELS,
    SUBCATEGORY_LABELS,
    classify_question_batch,
    concept_label,
)
from cert_study_app.services.quiz_service import QuizService, yes_no_labels
from cert_study_app.services.study_assistant_service import StudyAssistantService
from cert_study_app.services.vector_service import QuestionVectorStore


st.set_page_config(page_title="Cert Study Lab", page_icon=":books:", layout="wide")

DEFAULT_VISUAL_MODEL = os.getenv("OLLAMA_VISUAL_MODEL", "qwen3-vl:8b-instruct-q4_K_M")
DEFAULT_MAIN_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
DEFAULT_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "qwen3.5:9b")
DEFAULT_DEEP_MODEL = os.getenv("OLLAMA_DEEP_MODEL", "").strip()
DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_MODEL_OPTIONS = [
    "BAAI/bge-m3",
    "intfloat/multilingual-e5-large",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "sentence-transformers/all-MiniLM-L6-v2",
]


def inject_pwa_assets():
    components.html(
        """
        <script>
        (function () {
          const doc = window.parent.document;

          function ensureLink(rel, href, attrs) {
            if (doc.querySelector(`link[rel="${rel}"][href="${href}"]`)) {
              return;
            }
            const link = doc.createElement("link");
            link.rel = rel;
            link.href = href;
            Object.entries(attrs || {}).forEach(([key, value]) => link.setAttribute(key, value));
            doc.head.appendChild(link);
          }

          function ensureMeta(name, content) {
            let meta = doc.querySelector(`meta[name="${name}"]`);
            if (!meta) {
              meta = doc.createElement("meta");
              meta.name = name;
              doc.head.appendChild(meta);
            }
            meta.content = content;
          }

          ensureLink("manifest", "/app/static/manifest.webmanifest");
          ensureLink("icon", "/app/static/icons/icon-192.png", { type: "image/png", sizes: "192x192" });
          ensureLink("apple-touch-icon", "/app/static/icons/icon-192.png", { sizes: "192x192" });
          ensureMeta("theme-color", "#2563eb");
          ensureMeta("apple-mobile-web-app-capable", "yes");
          ensureMeta("apple-mobile-web-app-title", "Cert Study");
          ensureMeta("mobile-web-app-capable", "yes");

          if ("serviceWorker" in window.parent.navigator) {
            window.parent.navigator.serviceWorker
              .register("/app/static/service-worker.js")
              .catch(function () {});
          }
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def get_service():
    db = SessionLocal()
    return db, QuizService(db)


def init_state():
    st.session_state.setdefault("question_id", None)
    st.session_state.setdefault("selected", None)
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("exam_source", None)
    st.session_state.setdefault("page", "홈")
    st.session_state.setdefault("weak_type", None)
    st.session_state.setdefault("similar_type", None)
    st.session_state.setdefault("review_question_id", None)
    st.session_state.setdefault("quiz_order_mode", "순서대로")
    st.session_state.setdefault("lab_track", normalize_track_id(preferred_track()))
    st.session_state.setdefault("today_session_done", set())
    st.session_state.setdefault("lab_lesson_index", 0)
    st.session_state.setdefault("lab_quiz_index", 0)
    st.session_state.setdefault("lab_practice_index", 0)
    st.session_state.setdefault("lab_completed_lessons", set())
    st.session_state.setdefault("lab_completed_quizzes", set())
    st.session_state.setdefault("lab_completed_practices", set())
    st.session_state.setdefault("lab_wrong_notes", [])
    st.session_state.setdefault("quiz_skill_category", "전체")
    st.session_state.setdefault("quiz_skill_subcategory", "전체")


def apply_mobile_styles():
    st.markdown(
        """
        <style>
        :root {
            --cert-primary: #2563eb;
            --cert-border: rgba(15, 23, 42, 0.12);
            --cert-soft: rgba(37, 99, 235, 0.08);
        }
        .block-container {
            padding-top: 0.75rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 760px;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.5rem;
        }
        div[data-testid="stButton"] > button {
            min-height: 44px;
            border-radius: 8px;
            white-space: normal;
            line-height: 1.25;
        }
        div[data-testid="stRadio"] label,
        div[data-testid="stCheckbox"] label {
            min-height: 40px;
            align-items: flex-start;
        }
        div[role="radiogroup"] > label {
            border: 1px solid var(--cert-border);
            border-radius: 8px;
            padding: 0.55rem 0.7rem;
            margin-bottom: 0.35rem;
        }
        div[role="radiogroup"] > label:has(input:checked) {
            border-color: var(--cert-primary);
            background: var(--cert-soft);
        }
        .cert-quick-actions {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
            margin: 0.35rem 0 0.75rem;
        }
        .cert-section-title {
            margin: 1.2rem 0 0.35rem;
            font-size: 0.95rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.72);
        }
        div[role="radiogroup"] {
            gap: 0.35rem;
        }
        .answer-explanation {
            border: 1px solid rgba(49, 51, 63, 0.16);
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-top: 0.75rem;
            background: rgba(250, 250, 250, 0.75);
        }
        .answer-explanation p {
            margin: 0.35rem 0;
            line-height: 1.65;
        }
        .answer-explanation ul {
            margin-top: 0.25rem;
            padding-left: 1.2rem;
        }
        .answer-explanation strong {
            display: block;
            margin-top: 0.8rem;
        }
        @media (max-width: 640px) {
            .block-container {
                padding-left: 0.7rem;
                padding-right: 0.7rem;
            }
            h1 {
                font-size: 1.6rem;
            }
            h2, h3 {
                font-size: 1.15rem;
            }
            .stRadio label, .stSelectbox label, .stTextArea label, .stTextInput label {
                font-size: 0.95rem;
            }
            div[data-testid="stMetric"] {
                padding: 0.25rem 0;
            }
            div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }
            div[data-testid="column"] {
                min-width: 100%;
            }
            div[data-testid="column"] div[data-testid="stMetric"] {
                border-bottom: 1px solid var(--cert-border);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value.strip())
    return slug.strip("._-") or "exam"


def get_exams():
    db, service = get_service()
    try:
        return service.list_exams()
    finally:
        db.close()


def render_exam_selector(exams):
    sources = [exam["source"] for exam in exams]
    labels = ["전체 문제"] + [
        f"{exam['name']} ({exam['count']}문항)" for exam in exams
    ]

    current = st.session_state.exam_source
    index = sources.index(current) + 1 if current in sources else 0
    selected_label = st.selectbox("시험", labels, index=index)
    selected_source = None if selected_label == "전체 문제" else sources[labels.index(selected_label) - 1]

    if selected_source != st.session_state.exam_source:
        st.session_state.exam_source = selected_source
        st.session_state.question_id = None
        st.session_state.selected = None
        st.session_state.last_result = None

    selected_exam = next((exam for exam in exams if exam["source"] == selected_source), None)
    return selected_exam, selected_source


def go_to(page: str):
    st.session_state.page = page
    st.rerun()


def track_for_question_source(source):
    normalized = (source or "").strip().lower()
    if normalized.startswith("az-104") or "azure" in normalized:
        return "azure"
    if "linux" in normalized or "lfcs" in normalized:
        return "linux"
    return normalize_track_id(st.session_state.get("lab_track", "linux"))


def render_home(exams):
    st.subheader("시작하기")
    total_questions = sum(exam["count"] for exam in exams)
    st.caption(f"등록된 시험 {len(exams)}개 · 전체 문항 {total_questions}개")

    st.markdown('<div class="cert-section-title">어디서 이어서 공부할까요?</div>', unsafe_allow_html=True)
    if st.button("이어서 공부", type="primary", use_container_width=True):
        go_to("이어서 공부")
    col1, col2 = st.columns(2)
    if col1.button("집중 학습", use_container_width=True):
        go_to("Focus Mode")
    if col2.button("시험 대비", use_container_width=True):
        go_to("Exam Mode")
    if st.button("대시보드", use_container_width=True):
        go_to("대시보드")

    with st.expander("학습 메뉴", expanded=False):
        col1, col2 = st.columns(2)
        if col1.button("로드맵", use_container_width=True):
            go_to("로드맵")
        if col2.button("이론 학습", use_container_width=True):
            go_to("이론 학습")
        col3, col4 = st.columns(2)
        if col3.button("확인 퀴즈", use_container_width=True):
            go_to("확인 퀴즈")
        if col4.button("자격증 문제", use_container_width=True):
            go_to("자격증 문제")
        col5, col6 = st.columns(2)
        if col5.button("실습하기", use_container_width=True):
            go_to("실습하기")
        if col6.button("진도율", use_container_width=True):
            go_to("진도율")

    with st.expander("복습/개념", expanded=False):
        col1, col2 = st.columns(2)
        if col1.button("취약 개념 학습", use_container_width=True):
            go_to("취약 개념 학습")
        if col2.button("개념 정리", use_container_width=True):
            go_to("개념 정리")

    with st.expander("업로드/관리", expanded=False):
        if st.button("콘텐츠 관리", use_container_width=True):
            go_to("콘텐츠 관리")
        if st.button("PDF 업로드", use_container_width=True):
            go_to("PDF 업로드")
        if st.button("처리 현황", use_container_width=True):
            go_to("처리 현황")
        if st.button("시험 현황", use_container_width=True):
            go_to("시험 현황")
        if st.button("AI 색인", use_container_width=True):
            go_to("AI 색인")


def render_back_home():
    if st.button("처음으로", use_container_width=True):
        go_to("홈")


def render_exam_overview(exams, selected_exam):
    st.subheader("시험 현황")
    total_questions = sum(exam["count"] for exam in exams)
    col1, col2, col3 = st.columns(3)
    col1.metric("시험", f"{len(exams)}개")
    col2.metric("전체 문항", f"{total_questions}개")
    col3.metric("선택 문항", f"{selected_exam['count']}개" if selected_exam else f"{total_questions}개")

    if not exams:
        st.info("아직 등록된 시험 문제가 없습니다. 업로드에서 시험명을 지정하고 PDF를 적재해 주세요.")
        return

    st.dataframe(
        [
            {
                "시험": exam["name"],
                "문항 수": exam["count"],
                "첫 문항": exam["first_question_id"],
                "마지막 문항": exam["last_question_id"],
            }
            for exam in exams
        ],
        hide_index=True,
        use_container_width=True,
    )


def selected_lab_track() -> str:
    tracks = active_tracks()
    labels = [f"{track['name']} · {certification_for_track(track['id'])['name']}" for track in tracks]
    ids = [track["id"] for track in tracks]
    current = normalize_track_id(st.session_state.get("lab_track", "linux"))
    index = ids.index(current) if current in ids else 0
    selected_label = st.selectbox("Track", labels, index=index)
    track_id = ids[labels.index(selected_label)]
    if track_id != st.session_state.get("lab_track"):
        save_preferred_track(track_id)
    st.session_state.lab_track = track_id
    return track_id


def render_dashboard(exams):
    st.subheader("대시보드")
    st.caption("진도와 추천 복습은 여기에서만 확인합니다.")
    render_today_plan(exams)
    render_weak_recommendations()


def render_today_plan(exams):
    total_questions = sum(exam["count"] for exam in exams)
    track_id = selected_lab_track()
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    lessons = lessons_for_track(track_id)
    quizzes = quizzes_for_track(track_id)
    practices = [task for task in PRACTICE_TASKS if task.track == track_id and task.status == "approved"]
    persisted_steps = completed_steps(track_id)
    progress = track_progress(
        track_id,
        set(st.session_state.lab_completed_lessons),
        set(st.session_state.lab_completed_quizzes),
        set(st.session_state.lab_completed_practices),
    )
    week = weekly_summary()
    streak = streak_days()
    with st.container(border=True):
        st.markdown("### 이어서 공부")
        st.caption(f"{track['name']} 중심 · 목표 자격증: {certification['name']}")
        col1, col2, col3 = st.columns(3)
        col1.metric("이론 카드", f"{min(3, len(lessons))}개")
        col2.metric("확인 퀴즈", f"{min(5, len(quizzes))}문제")
        if track_id == "tool_docs":
            third_label = "Docs 복습"
            third_value = "1개"
        else:
            third_label = "오답 복습"
            third_value = "1개"
        col3.metric(third_label, third_value)
        wrong_count = len([item for item in st.session_state.lab_wrong_notes if item.get("track") == track_id])
        st.caption(f"오답 복습 {wrong_count}개 · 등록된 자격증 문제 {total_questions}개")
        st.progress(progress["percent"] / 100 if progress["total"] else 0, text=f"{track['name']} 진행률 {progress['completed']}/{progress['total']}")
        daily_step_count = len(persisted_steps & {"lesson", "quiz", "review"})
        st.progress(daily_step_count / 3, text=f"기본 흐름 {daily_step_count}/3")
        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("연속 학습", f"{streak}일")
        metric2.metric("오늘 누적", f"{study_units():.1f}단위")
        metric3.metric("이번 주 누적", f"{week['study_units']:.1f}단위")
        st.caption(next_day_recommendation(track_id))


def render_weak_recommendations():
    db = SessionLocal()
    try:
        rows = (
            db.query(Question.category, Question.subcategory, func.count(Attempt.id))
            .join(Question, Attempt.question_id == Question.id)
            .filter(Attempt.user_id == DEFAULT_USER, Attempt.note_type == "wrong")
            .group_by(Question.category, Question.subcategory)
            .order_by(func.count(Attempt.id).desc())
            .limit(3)
            .all()
        )
        if not rows:
            return
        with st.container(border=True):
            st.markdown("### 오늘 추천 복습")
            for category, subcategory, count in rows:
                st.caption(f"{concept_label(category, subcategory)} · 오답 {count}회")
            if st.button("오답 추천으로 복습", use_container_width=True):
                go_to("오답노트")
    finally:
        db.close()


def render_continue_study():
    st.subheader("이어서 공부")
    track_id = selected_lab_track()
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    lessons = lessons_for_track(track_id)
    quizzes = quizzes_for_track(track_id)
    session_done = completed_steps(track_id)
    session_steps = [
        ("lesson", "이론 이어보기", f"카드 {min(1, len(lessons))}개부터 시작하고, 원하면 계속 다음 카드로 넘어갑니다.", "이론 이어보기", "이론 학습"),
        ("quiz", "확인 퀴즈", f"{min(3, len(quizzes))}개로 시작한 뒤 계속 풀 수 있습니다.", "확인 퀴즈 풀기", "확인 퀴즈"),
        ("review", "오답 복습", "오답 1개부터 보고, 더 복습하면 누적 학습량으로 기록됩니다.", "오답 복습으로 이동", "오답노트"),
    ]

    st.caption(f"{track['name']} Track · {certification['name']} · 원하는 만큼 이어서 공부합니다.")
    done_count = len(session_done & {step[0] for step in session_steps})
    st.progress(done_count / len(session_steps), text=f"기본 흐름 {done_count}/{len(session_steps)} · 오늘 누적 {study_units():.1f}단위")

    for index, (step_id, title, description, action_label, target_page) in enumerate(session_steps, 1):
        with st.container(border=True):
            done = step_id in session_done
            st.markdown(f"### {index}. {'완료 · ' if done else ''}{title}")
            st.write(description)
            col1, col2 = st.columns([1, 1])
            if col1.button(action_label, type="primary" if not done else "secondary", use_container_width=True, key=f"today_go_{step_id}"):
                go_to(target_page)
            if col2.button("완료 체크", use_container_width=True, key=f"today_done_{step_id}", disabled=done):
                st.session_state.today_session_done = mark_learning_step(track_id, step_id)
                st.rerun()

    if done_count == len(session_steps):
        st.success("기본 흐름을 지나왔습니다. 더 공부하면 오늘 누적 학습량에 계속 더해집니다.")


def render_focus_mode():
    st.subheader("집중 학습")
    track_id = selected_lab_track()
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    st.caption(f"{track['name']} Track · {certification['name']} · 오늘 하고 싶은 공부만 골라서 길게 이어갑니다.")

    col1, col2 = st.columns(2)
    if col1.button("이론만 보기", type="primary", use_container_width=True):
        go_to("이론 학습")
    if col2.button("퀴즈만 풀기", use_container_width=True):
        go_to("확인 퀴즈")
    col3, col4 = st.columns(2)
    if col3.button("오답만 복습", use_container_width=True):
        go_to("오답노트")
    if col4.button("로드맵 보기", use_container_width=True):
        go_to("로드맵")

    if track_id == "linux":
        if st.button("Linux 실습 집중", use_container_width=True):
            go_to("실습하기")
    elif track_id == "tool_docs":
        st.info("Tool Docs는 공식 문서 요약 카드와 확인 퀴즈를 반복하는 방식으로 운영합니다.")
    else:
        st.info("시험 문제풀이에 몰입하려면 `시험 대비`를 사용하세요.")


def render_exam_study_mode():
    st.subheader("시험 대비")
    st.caption("이어서 공부 흐름과 분리된 자격증 집중 모드입니다. 문제풀이, 세부개념 반복, 모의시험을 여기에서 봅니다.")
    col1, col2 = st.columns(2)
    if col1.button("AZ-104 문제풀이", type="primary", use_container_width=True):
        st.session_state.exam_source = "AZ-104"
        go_to("자격증 문제")
    if col2.button("시험 모드 설정", use_container_width=True):
        go_to("시험 모드")
    col3, col4 = st.columns(2)
    if col3.button("세부개념 반복", use_container_width=True):
        st.session_state.exam_source = "AZ-104"
        go_to("자격증 문제")
    if col4.button("오답 복습", use_container_width=True):
        go_to("오답노트")


def render_roadmap():
    st.subheader("로드맵")
    track_id = selected_lab_track()
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    st.caption(f"{track['name']} Track · {certification['name']} 대비")
    steps = roadmap_for_track(track_id)
    if not steps:
        st.info("아직 준비 중인 Track입니다.")
        return
    for index, step in enumerate(steps, 1):
        with st.container(border=True):
            st.markdown(f"**{index}. {step.title}**")
            st.caption(step.level)
            st.write(step.description)


def render_quiz_skill_filter(db, source):
    if source not in {None, "AZ-104"}:
        return None, None

    rows = (
        db.query(Question.category, Question.subcategory, func.count(Question.id))
        .filter(Question.source == "AZ-104", Question.category.isnot(None))
        .group_by(Question.category, Question.subcategory)
        .order_by(Question.category.asc(), Question.subcategory.asc())
        .all()
    )
    if not rows:
        st.caption("아직 AZ-104 영역 분류가 없습니다. 처리 현황에서 AZ-104 영역 분류를 먼저 실행해 주세요.")
        return None, None

    categories = []
    for category, _subcategory, _count in rows:
        if category and category not in categories:
            categories.append(category)
    category_labels = ["전체"] + [concept_label(category) for category in categories]
    current_category = st.session_state.get("quiz_skill_category", "전체")
    current_index = categories.index(current_category) + 1 if current_category in categories else 0
    selected_category_label = st.selectbox("AZ-104 대분류", category_labels, index=current_index)
    selected_category = None if selected_category_label == "전체" else categories[category_labels.index(selected_category_label) - 1]

    selected_subcategory = None
    if selected_category:
        sub_rows = [(subcategory, count) for category, subcategory, count in rows if category == selected_category and subcategory]
        subcategory_values = [subcategory for subcategory, _count in sub_rows]
        subcategory_labels = ["전체"] + [f"{concept_label(selected_category, subcategory)} ({count}문항)" for subcategory, count in sub_rows]
        current_subcategory = st.session_state.get("quiz_skill_subcategory", "전체")
        sub_index = subcategory_values.index(current_subcategory) + 1 if current_subcategory in subcategory_values else 0
        selected_subcategory_label = st.selectbox("세부 개념", subcategory_labels, index=sub_index)
        selected_subcategory = None if selected_subcategory_label == "전체" else subcategory_values[subcategory_labels.index(selected_subcategory_label) - 1]

    selected_category_state = selected_category or "전체"
    selected_subcategory_state = selected_subcategory or "전체"
    if selected_category_state != st.session_state.get("quiz_skill_category"):
        st.session_state.quiz_skill_category = selected_category_state
        st.session_state.quiz_skill_subcategory = "전체"
        st.session_state.question_id = None
        st.session_state.selected = None
        st.session_state.last_result = None
        st.rerun()
    if selected_subcategory_state != st.session_state.get("quiz_skill_subcategory"):
        st.session_state.quiz_skill_subcategory = selected_subcategory_state
        st.session_state.question_id = None
        st.session_state.selected = None
        st.session_state.last_result = None
        st.rerun()

    return selected_category, selected_subcategory


def render_theory_learning():
    st.subheader("이론 학습")
    track_id = selected_lab_track()
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    st.caption(f"{track['name']} Track · {certification['name']} 대비")
    lessons = lessons_for_track(track_id)
    if not lessons:
        st.info("아직 승인된 이론 카드가 없습니다.")
        return

    index = min(st.session_state.lab_lesson_index, len(lessons) - 1)
    lesson = lessons[index]
    with st.container(border=True):
        st.caption(f"{lesson.track} · {lesson.certification} · {lesson.status}")
        st.markdown(f"### {lesson.title}")
        st.markdown("**핵심 이해**")
        st.write(lesson.summary)
        if lesson.details:
            for detail in lesson.details:
                st.markdown(f"- {detail}")
        st.markdown("**예시**")
        st.code(lesson.example)
        st.markdown("**헷갈릴 포인트**")
        st.write(lesson.common_mistake)
        st.caption("키워드: " + ", ".join(lesson.keywords))
        st.caption(f"Source ID: {lesson.source_id}")

    if st.button("학습 완료", type="primary", use_container_width=True):
        st.session_state.lab_completed_lessons.add(lesson.id)
        record_activity(track_id, "lesson", 1)
        st.success(f"이론 카드를 완료했습니다. 오늘 누적 {study_units():.1f}단위")

    prev_col, next_col = st.columns(2)
    if prev_col.button("이전 카드", use_container_width=True, disabled=index == 0):
        st.session_state.lab_lesson_index = max(0, index - 1)
        st.rerun()
    if next_col.button("다음 카드", use_container_width=True, disabled=index >= len(lessons) - 1):
        st.session_state.lab_lesson_index = min(len(lessons) - 1, index + 1)
        st.rerun()


def render_learning_quiz():
    st.subheader("확인 퀴즈")
    track_id = selected_lab_track()
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    st.caption(f"{track['name']} Track · {certification['name']} 대비")
    quizzes = quizzes_for_track(track_id)
    if not quizzes:
        st.info("아직 준비된 확인 퀴즈가 없습니다.")
        return

    index = min(st.session_state.lab_quiz_index, len(quizzes) - 1)
    quiz = quizzes[index]
    with st.container(border=True):
        st.caption(f"{quiz.track} · {quiz.question_type} · {quiz.difficulty} · {quiz.status}")
        st.markdown(f"### 문제 {index + 1}/{len(quizzes)}")
        st.write(quiz.question)
        if quiz.question_type == "multiple_choice":
            answer = st.radio("답", quiz.options, key=f"lab_quiz_answer_{quiz.id}")
        else:
            answer = st.text_input("명령어 입력", key=f"lab_quiz_answer_{quiz.id}", placeholder=quiz.answer)

    if st.button("정답 확인", type="primary", use_container_width=True):
        record_activity(track_id, "quiz", 1)
        correct = evaluate_lab_quiz(quiz, answer)
        if correct:
            st.session_state.lab_completed_quizzes.add(quiz.id)
            st.success("정답입니다.")
        else:
            st.error(f"오답입니다. 정답: {quiz.answer}")
            wrong_ids = {item["id"] for item in st.session_state.lab_wrong_notes}
            if quiz.id not in wrong_ids:
                st.session_state.lab_wrong_notes.append(
                    {
                        "id": quiz.id,
                        "item_type": "quiz",
                        "track": quiz.track,
                        "question": quiz.question,
                        "user_answer": str(answer),
                        "correct_answer": quiz.answer,
                        "explanation": quiz.explanation,
                    }
                )
        st.markdown('<div class="answer-explanation">', unsafe_allow_html=True)
        st.markdown(quiz.explanation)
        st.markdown("</div>", unsafe_allow_html=True)

    prev_col, next_col = st.columns(2)
    if prev_col.button("이전 퀴즈", use_container_width=True, disabled=index == 0):
        st.session_state.lab_quiz_index = max(0, index - 1)
        st.rerun()
    if next_col.button("다음 퀴즈", use_container_width=True, disabled=index >= len(quizzes) - 1):
        st.session_state.lab_quiz_index = min(len(quizzes) - 1, index + 1)
        st.rerun()


def render_exam_mode():
    st.subheader("시험 모드")
    st.caption("초기 버전은 시험 세션을 시작하기 전 설정 화면입니다.")
    exam_type = st.selectbox("시험 종류", ["AZ-104 모의시험", "LFCS 스타일 실습 시험", "Linux 기초 시험", "리눅스마스터 필기 스타일"])
    question_count = st.selectbox("문제 수", [5, 10, 20, 40], index=1)
    duration = st.selectbox("제한 시간", ["10분", "20분", "40분", "90분"], index=1)
    with st.container(border=True):
        st.markdown(f"**{exam_type}**")
        st.write(f"- 문제 수: {question_count}문제")
        st.write(f"- 제한 시간: {duration}")
        st.write("- 결과: 점수, 정답률, 오답 저장 영역으로 확장 예정")
    if st.button("시험 시작 준비", type="primary", use_container_width=True):
        st.info("다음 단계에서 기존 문제은행과 연결해 실제 시험 세션을 생성합니다.")


def render_lab_practice():
    st.subheader("실습하기")
    st.caption("현재는 Docker 터미널이 아니라 fake terminal simulator입니다.")
    track_id = selected_lab_track()
    tasks = [task for task in PRACTICE_TASKS if task.track == track_id and task.status == "approved"]
    if not tasks:
        st.info("이 Track의 실습은 아직 준비 중입니다. 현재 fake terminal 실습은 Linux / LFCS 중심으로 제공합니다.")
        return
    index = min(st.session_state.lab_practice_index, len(tasks) - 1)
    task = tasks[index]

    with st.container(border=True):
        st.caption(f"{task.track} · {task.difficulty} · {task.status}")
        st.markdown(f"### {task.title}")
        st.write(task.task_description)
        command = st.text_input("터미널 입력", key=f"practice_command_{task.id}", placeholder=task.expected_command)
        with st.expander("힌트", expanded=False):
            st.write(task.hint)

    if st.button("실습 채점", type="primary", use_container_width=True):
        if evaluate_practice(task, command):
            st.session_state.lab_completed_practices.add(task.id)
            record_activity(track_id, "practice", 1)
            st.success(f"정답입니다. 오늘 누적 {study_units():.1f}단위")
        else:
            st.error("아직 조건을 만족하지 못했습니다.")
        st.markdown('<div class="answer-explanation">', unsafe_allow_html=True)
        st.markdown(task.explanation)
        st.markdown("</div>", unsafe_allow_html=True)

    prev_col, next_col = st.columns(2)
    if prev_col.button("이전 실습", use_container_width=True, disabled=index == 0):
        st.session_state.lab_practice_index = max(0, index - 1)
        st.rerun()
    if next_col.button("다음 실습", use_container_width=True, disabled=index >= len(tasks) - 1):
        st.session_state.lab_practice_index = min(len(tasks) - 1, index + 1)
        st.rerun()


def render_progress():
    st.subheader("진도율")
    completed_lessons = set(st.session_state.lab_completed_lessons)
    completed_quizzes = set(st.session_state.lab_completed_quizzes)
    completed_practices = set(st.session_state.lab_completed_practices)
    for track in active_tracks():
        certification = certification_for_track(track["id"])
        progress = track_progress(track["id"], completed_lessons, completed_quizzes, completed_practices)
        with st.container(border=True):
            st.markdown(f"**{track['name']}**")
            st.caption(f"{track['description']} · 목표 자격증: {certification['name']}")
            st.progress(progress["percent"] / 100 if progress["total"] else 0, text=f"{progress['completed']}/{progress['total']} 완료")
    st.metric("오늘 완료한 학습", len(completed_lessons) + len(completed_quizzes) + len(completed_practices))

    st.markdown("#### AZ-104 문제은행 영역 분포")
    db = SessionLocal()
    try:
        rows = (
            db.query(Question.category, func.count(Question.id))
            .filter(Question.source == "AZ-104")
            .group_by(Question.category)
            .order_by(func.count(Question.id).desc())
            .all()
        )
        if not rows:
            st.caption("아직 AZ-104 문제 분류 결과가 없습니다.")
        else:
            total = sum(count for _category, count in rows)
            for category, count in rows:
                ratio = count / total if total else 0
                st.progress(ratio, text=f"{concept_label(category)} · {count}문항")
    finally:
        db.close()


def render_content_management():
    st.subheader("콘텐츠 관리")
    st.caption("현재는 기존 관리 기능으로 이동하는 허브입니다.")
    col1, col2 = st.columns(2)
    if col1.button("PDF 업로드", use_container_width=True):
        go_to("PDF 업로드")
    if col2.button("처리 현황", use_container_width=True):
        go_to("처리 현황")
    col3, col4 = st.columns(2)
    if col3.button("시험 현황", use_container_width=True):
        go_to("시험 현황")
    if col4.button("AI 색인", use_container_width=True):
        go_to("AI 색인")
    st.markdown("#### 콘텐츠 상태")
    st.write("생성 콘텐츠 상태값은 `generated`, `reviewed`, `approved`, `rejected`를 기준으로 확장합니다.")
    with st.expander("AZ-104 분류 검수", expanded=False):
        render_classification_review("AZ-104")


def render_classification_review(source="AZ-104"):
    db = SessionLocal()
    try:
        categories = [
            "az104_identity_governance",
            "az104_storage",
            "az104_compute",
            "az104_networking",
            "az104_monitor_recovery",
        ]
        category_label_map = {category: CATEGORY_LABELS.get(category, category) for category in categories}
        selected_category_label = st.selectbox(
            "검수할 대분류",
            ["전체"] + list(category_label_map.values()),
            key="review_category_filter",
        )
        selected_category = None
        if selected_category_label != "전체":
            selected_category = next(category for category, label in category_label_map.items() if label == selected_category_label)

        query = db.query(Question).filter(Question.source == source)
        if selected_category:
            query = query.filter(Question.category == selected_category)
        questions = query.order_by(Question.question_number.asc(), Question.id.asc()).limit(20).all()
        if not questions:
            st.caption("검수할 문제가 없습니다.")
            return

        st.caption("평소에는 닫아두고, 자동 분류가 어색한 문제만 고치면 됩니다.")
        category_options = categories + ["uncategorized"]
        for question in questions:
            with st.container(border=True):
                number = question.question_number or question.id
                st.markdown(f"**문제 {number}번**")
                st.caption((question.stem or "")[:180])

                current_category = question.category if question.category in category_options else "uncategorized"
                category_index = category_options.index(current_category)
                new_category = st.selectbox(
                    "대분류",
                    category_options,
                    index=category_index,
                    format_func=lambda value: CATEGORY_LABELS.get(value, value),
                    key=f"class_category_{question.id}",
                )

                subcategory_options = sorted(SUBCATEGORY_LABELS.keys())
                current_subcategory = question.subcategory if question.subcategory in subcategory_options else None
                sub_labels = ["미지정"] + subcategory_options
                sub_index = sub_labels.index(current_subcategory) if current_subcategory in sub_labels else 0
                new_subcategory = st.selectbox(
                    "세부 개념",
                    sub_labels,
                    index=sub_index,
                    format_func=lambda value: "미지정" if value == "미지정" else SUBCATEGORY_LABELS.get(value, value),
                    key=f"class_subcategory_{question.id}",
                )
                if st.button("분류 저장", use_container_width=True, key=f"save_classification_{question.id}"):
                    question.category = new_category
                    question.subcategory = None if new_subcategory == "미지정" else new_subcategory
                    db.commit()
                    st.success("분류를 저장했습니다.")
                    st.rerun()
    finally:
        db.close()


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
    headings = {
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
    }
    sections = []
    title = "요약"
    body = []
    for line in lines:
        normalized = line.rstrip(":")
        is_heading = normalized in headings or (
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
    headings = {
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
    }
    rendered = []
    for raw_line in display_parent_text(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = line.rstrip(":")
        is_heading = normalized in headings or (
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


def visual_statements(question) -> list[dict]:
    try:
        analysis = json.loads(question.get("visual_analysis_json") or "{}")
    except Exception:
        return []
    statements = analysis.get("statements") if isinstance(analysis, dict) else None
    if isinstance(statements, list):
        return [statement for statement in statements if isinstance(statement, dict)]
    return []


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


def render_quiz_controls(service, source, current_question=None):
    with st.expander("문제 이동", expanded=False):
        mode = st.radio(
            "풀이 순서",
            ["순서대로", "랜덤"],
            horizontal=True,
            key="quiz_order_mode",
        )
        max_number = max(1, service.max_question_number(source))
        st.caption(f"문제 번호 범위: 1번 ~ {max_number}번 · 처리 전 번호는 이동할 수 없습니다.")
        number = st.number_input(
            "문제 번호로 이동",
            min_value=1,
            max_value=max_number,
            step=1,
            value=min(max_number, int((current_question or {}).get("number") or 1)),
            key=f"jump_number_{(current_question or {}).get('id', 'none')}",
        )
        col1, col2 = st.columns(2)
        if col1.button("번호 이동", use_container_width=True):
            target = service.get_question_by_number(int(number), source)
            if not target:
                status = service.question_status_by_number(int(number), source)
                if not status:
                    st.warning("해당 번호의 문제가 없습니다.")
                elif status["status"] == "needs_visual":
                    st.warning(
                        f"{status['number']}번은 현재 '{status_label(status['status'])}' 상태라 "
                        "풀이 화면에서 제외되어 있습니다. 처리 현황에서 이미지 분석을 먼저 실행해 주세요."
                    )
                elif status["status"] in {"draft", "needs_review"}:
                    st.warning(
                        f"{status['number']}번은 현재 '{status_label(status['status'])}' 상태라 "
                        "풀이 화면에서 제외되어 있습니다. 처리 현황에서 보완 후 이동할 수 있습니다."
                    )
                else:
                    st.warning(
                        f"{status['number']}번은 현재 '{status_label(status['status'])}' 상태라 "
                        "풀이 화면에서 제외되어 있습니다."
                    )
            else:
                st.session_state.question_id = target["id"]
                st.session_state.selected = None
                st.session_state.last_result = None
                st.rerun()
        if col2.button("랜덤 문제", use_container_width=True):
            target = service.get_random_question(source, st.session_state.question_id)
            if not target:
                st.warning("랜덤으로 가져올 문제가 없습니다.")
            else:
                st.session_state.question_id = target["id"]
                st.session_state.selected = None
                st.session_state.last_result = None
                st.rerun()
        return mode or "순서대로"


def render_quiz(source=None):
    db, service = get_service()
    try:
        category, subcategory = render_quiz_skill_filter(db, source)
        filtered_source = "AZ-104" if category and source is None else source
        if category:
            question = service.get_unit_question(
                st.session_state.question_id,
                source=filtered_source,
                category=category,
                subcategory=subcategory,
            )
        else:
            question = service.get_question(st.session_state.question_id, source)
        if not question:
            st.info("선택한 시험에 등록된 문제가 없습니다.")
            return

        st.session_state.question_id = question["id"]
        order_mode = render_quiz_controls(service, filtered_source, question)
        render_question_header(question)
        render_question_body(question)
        render_question_image(question)

        st.session_state.selected = render_answer_input(question, "quiz")

        if st.button("채점", type="primary", use_container_width=True):
            if not st.session_state.selected:
                st.warning("답을 먼저 선택해 주세요.")
            else:
                chosen = str(st.session_state.selected).strip()
                st.session_state.last_result = service.answer(
                    question["id"],
                    chosen,
                    DEFAULT_USER,
                )
                record_activity(track_for_question_source(question.get("source")), "cert_question", 1)
                st.rerun()

        prev_col, next_col = st.columns(2)
        with prev_col:
            if st.button("이전", use_container_width=True):
                if category:
                    previous_question = service.previous_unit_question(
                        question["id"],
                        source=filtered_source,
                        category=category,
                        subcategory=subcategory,
                    )
                else:
                    previous_question = service.previous_question(question["id"], source)
                if previous_question.get("start"):
                    st.info("첫 번째 문제입니다.")
                else:
                    st.session_state.question_id = previous_question["id"]
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    st.rerun()
        with next_col:
            if st.button("다음", use_container_width=True):
                if order_mode == "랜덤":
                    if category:
                        next_question = service.get_random_unit_question(
                            source=filtered_source,
                            category=category,
                            subcategory=subcategory,
                            exclude_id=question["id"],
                        ) or {"end": True}
                    else:
                        next_question = service.get_random_question(source, question["id"]) or {"end": True}
                else:
                    if category:
                        next_question = service.next_unit_question(
                            question["id"],
                            source=filtered_source,
                            category=category,
                            subcategory=subcategory,
                        )
                    else:
                        next_question = service.next_question(question["id"], source)
                if next_question.get("end"):
                    st.success("마지막 문제입니다.")
                else:
                    st.session_state.question_id = next_question["id"]
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    st.rerun()

        if st.button("복습 추가", use_container_width=True):
            service.add_review(question["id"], DEFAULT_USER)
            st.toast("복습 목록에 추가했습니다.")

        if st.button("같은 단원/개념 계속 풀기", use_container_width=True):
            similar_type = service.similar_type_from_question(question["id"])
            if similar_type:
                st.session_state.similar_type = similar_type
                st.session_state.exam_source = similar_type["source"]
                st.session_state.question_id = None
                st.session_state.selected = None
                st.session_state.last_result = None
                go_to("같은 단원 학습")
            else:
                st.warning("같은 단원/개념 문제를 찾지 못했습니다.")

        if st.session_state.last_result:
            render_answer_result(st.session_state.last_result)
            render_concept_candidates(question)

        if st.toggle("질의응답", key=f"show_qa_{question['id']}"):
            render_quiz_assistant(question, source)
    finally:
        db.close()


def render_weak_quiz(source=None):
    db, service = get_service()
    try:
        weak_types = service.weak_types(DEFAULT_USER, source)
        if not weak_types:
            st.info("아직 오답 기록이 없습니다. 문제를 풀고 약한 개념이 생기면 여기에서 집중 학습할 수 있습니다.")
            return

        labels = [item["label"] for item in weak_types]
        current = st.session_state.weak_type
        current_label = current.get("label") if isinstance(current, dict) else None
        index = labels.index(current_label) if current_label in labels else 0
        selected_label = st.selectbox("학습할 취약 개념", labels, index=index)
        selected = weak_types[labels.index(selected_label)]

        if selected != st.session_state.weak_type:
            st.session_state.weak_type = selected
            st.session_state.question_id = None
            st.session_state.selected = None
            st.session_state.last_result = None

        question = service.get_weak_question(
            st.session_state.question_id,
            source=source,
            category=selected["category"] or None,
            subcategory=selected.get("subcategory") or None,
        )
        if not question:
            st.info("선택한 개념에 해당하는 문제가 없습니다.")
            return

        st.session_state.question_id = question["id"]
        render_question_header(question, selected["label"])
        render_question_body(question)
        render_question_image(question)

        st.session_state.selected = render_answer_input(question, "weak")

        if st.button("채점", type="primary", use_container_width=True):
            if not st.session_state.selected:
                st.warning("답을 먼저 선택해 주세요.")
            else:
                chosen = str(st.session_state.selected).strip()
                st.session_state.last_result = service.answer(question["id"], chosen, DEFAULT_USER)
                record_activity(track_for_question_source(question.get("source")), "cert_question", 1)
                st.rerun()

        prev_col, next_col = st.columns(2)
        with prev_col:
            if st.button("같은 개념 이전 문제", use_container_width=True):
                previous_question = service.previous_weak_question(
                    question["id"],
                    source=source,
                    category=selected["category"] or None,
                    subcategory=selected.get("subcategory") or None,
                )
                if previous_question.get("start"):
                    st.info("선택한 개념의 첫 번째 문제입니다.")
                else:
                    st.session_state.question_id = previous_question["id"]
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    st.rerun()
        with next_col:
            if st.button("같은 개념 다음 문제", use_container_width=True):
                next_question = service.next_weak_question(
                    question["id"],
                    source=source,
                    category=selected["category"] or None,
                    subcategory=selected.get("subcategory") or None,
                )
                if next_question.get("end"):
                    st.success("선택한 개념의 마지막 문제입니다.")
                else:
                    st.session_state.question_id = next_question["id"]
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    st.rerun()

        if st.session_state.last_result:
            render_answer_result(st.session_state.last_result)
    finally:
        db.close()


def render_similar_quiz():
    similar_type = st.session_state.similar_type
    if not similar_type:
        st.info("먼저 문제 풀이에서 기준 문제를 선택해 주세요.")
        return

    source = similar_type.get("source")
    category = similar_type.get("category")
    question_type = similar_type.get("question_type")

    db, service = get_service()
    try:
        st.caption(similar_type["label"])
        question = service.get_unit_question(
            st.session_state.question_id,
            source=source,
            category=category,
            subcategory=similar_type.get("subcategory"),
            question_type=question_type,
        )
        if not question:
            st.info("같은 단원/개념 문제가 없습니다.")
            return

        st.session_state.question_id = question["id"]
        render_question_header(question, similar_type["label"])
        render_question_body(question)
        render_question_image(question)

        st.session_state.selected = render_answer_input(question, "similar")

        if st.button("채점", type="primary", use_container_width=True):
            if not st.session_state.selected:
                st.warning("답을 먼저 선택해 주세요.")
            else:
                chosen = str(st.session_state.selected).strip()
                st.session_state.last_result = service.answer(question["id"], chosen, DEFAULT_USER)
                st.rerun()

        prev_col, next_col = st.columns(2)
        with prev_col:
            if st.button("이전 문제", use_container_width=True):
                previous_question = service.previous_unit_question(
                    question["id"],
                    source=source,
                    category=category,
                    subcategory=similar_type.get("subcategory"),
                    question_type=question_type,
                )
                if previous_question.get("start"):
                    st.info("첫 번째 문제입니다.")
                else:
                    st.session_state.question_id = previous_question["id"]
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    st.rerun()
        with next_col:
            if st.button("다음 문제", use_container_width=True):
                next_question = service.next_unit_question(
                    question["id"],
                    source=source,
                    category=category,
                    subcategory=similar_type.get("subcategory"),
                    question_type=question_type,
                )
                if next_question.get("end"):
                    st.success("마지막 문제입니다.")
                else:
                    st.session_state.question_id = next_question["id"]
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    st.rerun()

        if st.session_state.last_result:
            render_answer_result(st.session_state.last_result)
    finally:
        db.close()


def render_notes(source=None):
    db, service = get_service()
    try:
        payload = service.wrong_review(DEFAULT_USER, source)
        st.subheader(f"오답/복습 {payload['count']}개")
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
                if st.button("복습 완료", use_container_width=True, key=f"review_done_{item['question_id']}"):
                    record_activity(track_for_question_source(item.get("source")), "review", 1)
                    st.success(f"복습을 기록했습니다. 오늘 누적 {study_units():.1f}단위")
    finally:
        db.close()


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


def render_review(source=None):
    st.subheader("처리 현황")
    with st.expander("처리 현황에서 보는 것", expanded=False):
        st.markdown(
            """
처리 현황은 PDF 업로드 이후 문제 풀이 준비 과정을 한 곳에서 보여줍니다.

1. Airflow 파싱 작업이 진행 중인지 확인합니다.
2. 풀이 가능/이미지 분석 대기/질문 필요 문항 수를 봅니다.
3. 남은 이미지 분석과 개념 분류를 백그라운드로 보완합니다.
4. 애매한 문제만 직접 확인합니다.

네가 직접 봐야 하는 것은 `질문 필요`에 남은 처음 보는 패턴뿐입니다.
            """.strip()
        )
    render_airflow_status()
    st.divider()
    render_ingestion_jobs(show_title=False)
    st.divider()
    db = SessionLocal()
    try:
        base = db.query(Question)
        if source:
            base = base.filter(Question.source == source)

        summary_state = automation_summary(db, source)
        counts = summary_state["status_counts"]
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("승인 완료", counts.get("approved", 0))
        col_b.metric("이미지 분석 대기", summary_state["image_needed"])
        col_c.metric("질문 필요", summary_state["question_needed"])

        with st.expander("이미지 분석 대기란?", expanded=bool(summary_state["image_needed"])):
            st.markdown(
                """
`이미지 분석 대기`는 텍스트만으로는 문제를 안정적으로 풀 수 없는 상태입니다.

주로 이런 문제입니다.

- 상자/드롭다운/핫스팟 선택지가 이미지에만 있는 문제
- Yes/No 진술 행이 OCR로 충분히 안 잡힌 문제
- qwen 이미지 분석이 실패했거나 JSON 구조가 불완전했던 문제
- 사람이 직접 원문 이미지를 보고 행/선택지를 확인해야 하는 문제
                """.strip()
            )
            needs_visual_numbers = [
                question.question_number or question.id
                for question in base.filter(Question.parse_status == "needs_visual")
                .order_by(Question.question_number.asc(), Question.id.asc())
                .limit(80)
                .all()
            ]
            if needs_visual_numbers:
                st.caption("남은 번호: " + ", ".join(str(number) for number in needs_visual_numbers))

        if summary_state["question_needed"]:
            st.warning("처음 보는 패턴이 있어요. 아래 '질문 필요'에서 유형을 알려주면 다음부터 처리 규칙에 활용합니다.")
        elif summary_state["image_needed"]:
            st.info("이미지 분석 대기 문제가 남아 있습니다. 아래에서 Airflow 이미지 분석을 실행해 주세요.")
        else:
            st.success("핵심 처리가 끝났습니다. 남은 항목은 아래 상세 목록에서 확인하면 됩니다.")

        with st.container():
            col1, col2 = st.columns([2, 1])
            concept_overwrite = col1.checkbox("기존 AZ-104 영역 분류도 다시 계산", value=False)
            if col2.button("AZ-104 영역 분류", use_container_width=True):
                concept_summary = classify_question_batch(
                    db,
                    source=source,
                    limit=1000,
                    overwrite=concept_overwrite,
                )
                st.success(
                    f"AZ-104 영역 분류 {concept_summary['checked']}개 · "
                    f"분류됨 {concept_summary['classified']}개 · "
                    f"미분류 {concept_summary['uncategorized']}개"
                )
                st.rerun()

        with st.container():
            col1, col2 = st.columns([2, 1])
            airflow_visual_limit = col1.number_input(
                "Airflow 이미지 분석 개수",
                min_value=1,
                max_value=200,
                value=min(50, max(1, int(summary_state["image_needed"] or 1))),
                step=5,
            )
            if col2.button("Airflow로 이미지 분석 시작", use_container_width=True):
                try:
                    result = AirflowService().trigger_visual_analysis(
                        source_name=source,
                        limit=int(airflow_visual_limit),
                        model=DEFAULT_VISUAL_MODEL,
                    )
                    st.success(f"Airflow 이미지 분석 작업을 등록했습니다: {result.get('dag_run_id')}")
                except AirflowTriggerError as exc:
                    st.error(str(exc))
                    st.caption("Airflow가 켜져 있는지, http://localhost:8080 접속이 되는지 확인해 주세요.")

        with st.expander("문제 유형 메타데이터", expanded=False):
            type_counts = summary_state["type_counts"]
            if not type_counts:
                st.caption("아직 유형 메타데이터가 없습니다.")
            for qtype, count in sorted(type_counts.items()):
                meta = type_metadata(qtype)
                st.markdown(f"**{meta['label']}** · {count}개")
                st.caption(f"파싱: {meta['parser']} · 풀이 UI: {meta['ui']} · 이미지 필요: {'예' if meta['needs_image'] else '아니오'}")

        with st.expander("개념 분류 현황", expanded=False):
            concept_rows = (
                base.with_entities(Question.category, Question.subcategory, func.count(Question.id))
                .group_by(Question.category, Question.subcategory)
                .order_by(func.count(Question.id).desc())
                .all()
            )
            if not concept_rows:
                st.caption("아직 개념 분류가 없습니다.")
            for category, subcategory, count in concept_rows:
                st.markdown(f"**{concept_label(category, subcategory)}** · {count}문항")

        status_options = ["needs_reparse", "needs_review", "needs_visual", "draft", "approved", "rejected", "all"]
        default_status = (
            "needs_reparse"
            if summary_state.get("reparse_needed")
            else ("needs_visual" if summary_state["image_needed"] else ("needs_review" if summary_state["question_needed"] else "all"))
        )
        status_filter = st.selectbox(
            "상태",
            status_options,
            index=status_options.index(default_status),
            format_func=lambda value: "전체" if value == "all" else status_label(value),
        )

        query = base
        if status_filter != "all":
            query = query.filter(Question.parse_status == status_filter)
        questions = query.order_by(Question.id.asc()).limit(300).all()
        if not questions:
            st.info("선택한 상태의 문제가 없습니다.")
            return

        ids = [question.id for question in questions]
        current_id = st.session_state.review_question_id
        index = ids.index(current_id) if current_id in ids else 0
        selected_id = st.selectbox("문제", ids, index=index, format_func=lambda qid: f"#{qid}")
        st.session_state.review_question_id = selected_id

        question = db.query(Question).filter(Question.id == selected_id).first()
        if not question:
            st.warning("문제를 찾을 수 없습니다.")
            return

        if question.image_path and Path(question.image_path).exists():
            if st.toggle("원문 이미지 보기", key=f"review_img_{question.id}", value=False):
                st.image(question.image_path, use_container_width=True)

        score_text = "미실행" if question.review_score is None else f"{question.review_score}점"
        st.caption(f"{status_label(question.parse_status)} · 자동 점수 {score_text}")
        if question.quality_status:
            st.caption(
                f"품질: {question.quality_status}"
                + (f" · 점수 {question.quality_score}" if question.quality_score is not None else "")
                + (f" · chunk {question.chunk_index}" if question.chunk_index is not None else "")
            )
        if question.quality_issues:
            try:
                quality_issues = json.loads(question.quality_issues)
            except Exception:
                quality_issues = []
            quality_codes = [
                str(issue.get("code"))
                for issue in quality_issues
                if isinstance(issue, dict) and issue.get("code")
            ]
            if quality_codes:
                st.warning("품질 이슈: " + " / ".join(quality_codes))
        try:
            structured = json.loads(question.structured_data_json or "{}")
        except Exception:
            structured = {}
        meta = structured.get("question_type_metadata") or type_metadata(question.question_type)
        st.caption(f"유형: {meta.get('label')} · 파싱 방식: {meta.get('parser')} · 풀이 UI: {meta.get('ui')}")
        if question.review_issues:
            try:
                issues = json.loads(question.review_issues)
            except Exception:
                issues = [question.review_issues]
            if issues:
                st.warning(" / ".join(str(issue) for issue in issues))

        form_title = "질문 필요 항목 수정" if question.parse_status in {"needs_review", "draft"} else "문제 구조 확인"
        visual_types = {"hotspot", "table_choice", "matching", "ordering", "yes_no"}
        existing_visual = visual_analysis_data(question)
        show_visual_editor = (question.question_type or "").lower() in visual_types or bool(existing_visual)
        st.markdown(f"#### {form_title}")
        with st.form(f"review_form_{question.id}"):
            stem = st.text_area("문제 본문", value=question.stem or "", height=180)
            type_options = ["mcq", "multi_select", "yes_no", "matching", "ordering", "table_choice", "case_study", "hotspot", "unparsed"]
            current_type = (question.question_type or "unparsed").lower()
            type_index = type_options.index(current_type) if current_type in type_options else 0
            question_type = st.selectbox(
                "문제 유형",
                type_options,
                index=type_index,
            )
            options_text = st.text_area("보기", value=options_to_text(question.get_options()), height=140)
            answer = st.text_input("정답", value=question.answer or "")
            explanation = st.text_area("해설", value=question.explanation or "", height=120)
            visual_source = ""
            visual_areas_text = ""
            if show_visual_editor:
                st.markdown("##### 이미지 기반 구조")
                visual_source = st.text_area(
                    "문제 근거/이미지 설명",
                    value=visual_source_content(question),
                    height=110,
                    help="이미지 안의 코드, 표, 설정값, 다이어그램 텍스트처럼 문제 풀이에 필요한 원문 내용을 적습니다.",
                )
                visual_areas_text = st.text_area(
                    "이미지 답변 영역",
                    value=visual_answer_areas_to_text(visual_answer_areas(question)),
                    height=120,
                    help="행마다 '왼쪽 문구 | 선택지1, 선택지2 | 정답' 형식으로 입력합니다.",
                )
            review_note = st.text_area("검수 메모", value=question.review_note or "", height=80)
            raw_text = st.text_area("OCR 원문", value=question.raw_text or question.stem or "", height=120)

            col1, col2, col3 = st.columns(3)
            save = col1.form_submit_button("수정 저장", use_container_width=True)
            approve = col2.form_submit_button("풀이 가능 처리", type="primary", use_container_width=True)
            reject = col3.form_submit_button("제외", use_container_width=True)

        if save or approve or reject:
            question.stem = stem.strip()
            question.question_type = question_type
            question.answer = answer.strip()
            question.explanation = explanation.strip()
            question.review_note = review_note.strip()
            question.raw_text = raw_text.strip()
            question.set_options(parse_options_text(options_text))
            visual_areas = parse_visual_answer_areas_text(visual_areas_text) if show_visual_editor else []
            if show_visual_editor:
                visual_payload = dict(existing_visual)
                visual_payload.update(
                    {
                        "ok": True,
                        "model": visual_payload.get("model") or "manual-review",
                        "question_type": question.question_type,
                        "stem": question.stem,
                        "source_content": visual_source.strip(),
                        "answer_areas": visual_areas,
                        "options": question.get_options(),
                        "confidence": max(int(visual_payload.get("confidence") or 0), 95 if approve else 80),
                        "notes": "수동 보정",
                    }
                )
                question.visual_analysis_json = json.dumps(visual_payload, ensure_ascii=False)
                if not question.answer and visual_areas:
                    question.answer = visual_selected_answers(visual_areas)
            question.structured_data_json = json.dumps(
                {
                    "stem": question.stem,
                    "options": question.get_options(),
                    "answer": question.answer,
                    "explanation": question.explanation,
                    "question_type": question.question_type,
                    "question_type_metadata": type_metadata(question.question_type),
                    "visual_analysis": visual_analysis_data(question),
                },
                ensure_ascii=False,
            )
            if approve:
                question.parse_status = "approved"
                question.reviewed_at = datetime.utcnow()
            elif reject:
                question.parse_status = "rejected"
                question.reviewed_at = datetime.utcnow()
            elif not question.parse_status:
                question.parse_status = "draft"
            db.commit()
            st.success("저장했습니다.")
            st.rerun()
    finally:
        db.close()


def render_upload(exams):
    st.subheader("시험별 PDF 업로드")
    existing_names = [exam["name"] for exam in exams]
    selected_exam = ""
    if existing_names:
        selected_exam = st.selectbox("기존 시험 불러오기", [""] + existing_names)
    exam_name = st.text_input(
        "시험명",
        value=selected_exam,
        placeholder="예: AZ-104, AWS SAA-C03, 정보처리기사",
    )

    uploaded = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
    use_llm = st.checkbox("LLM 파싱 사용", value=False)
    auto_visual_analysis = st.checkbox("이미지 분석까지 자동 실행", value=True)
    visual_batch_size = 0
    if auto_visual_analysis:
        analyze_all_images = st.checkbox("이미지 분석 대기 문제 전체 처리", value=False)
        if analyze_all_images:
            visual_batch_size = 10000
            st.caption("Airflow 백그라운드에서 전체 이미지 분석을 시도합니다. PDF가 크면 오래 걸릴 수 있습니다.")
        else:
            visual_batch_size = st.number_input("업로드 후 qwen 이미지 분석 개수", min_value=1, max_value=50, value=5, step=1)
    llm_model = DEFAULT_MAIN_MODEL
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if use_llm:
        llm_model = st.text_input("Ollama 모델", value=llm_model)
        ollama_base_url = st.text_input("Ollama URL", value=ollama_base_url)
    if uploaded and st.button("파싱 작업 등록", type="primary"):
        exam_name = exam_name.strip()
        if not exam_name:
            st.warning("시험명을 입력해 주세요.")
            return
        ensure_runtime_dirs()
        safe_name = Path(uploaded.name).name
        target = f"data/uploads/{slugify(exam_name)}_{safe_name}"
        with open(target, "wb") as f:
            f.write(uploaded.getbuffer())

        db = SessionLocal()
        try:
            job_service = IngestionJobService(db)
            job = job_service.create_job(
                exam_name=exam_name,
                pdf_path=target,
                use_llm=use_llm,
                llm_model=llm_model,
                ollama_base_url=ollama_base_url,
                auto_visual_analysis=auto_visual_analysis,
                visual_batch_size=int(visual_batch_size),
            )
            job_id = job.id
            try:
                AirflowService().trigger_pdf_ingestion(
                    job_id=job_id,
                    pdf_path=target,
                    source_name=exam_name,
                    use_llm=use_llm,
                    llm_model=llm_model,
                    ollama_base_url=ollama_base_url,
                )
                job_service.mark_queued(job_id, "Airflow DAG 실행을 요청했습니다.")
            except AirflowTriggerError as exc:
                job_service.fail_job(job_id, str(exc))
        finally:
            db.close()

        st.success(f"파싱 작업 #{job_id}을 등록했습니다.")
        go_to("처리 현황")


def render_airflow_status():
    st.markdown("#### Airflow DAG 상태")
    try:
        airflow = AirflowService()
        dag_labels = [
            ("cert_study_pdf_ingestion", "PDF 파싱"),
            ("cert_study_visual_analysis", "이미지 분석"),
        ]
        for dag_id, label in dag_labels:
            runs = airflow.list_dag_runs(dag_id, limit=3)
            if not runs:
                st.caption(f"{label}: 실행 기록 없음")
                continue
            latest = runs[0]
            state = latest.get("state") or "unknown"
            run_id = latest.get("dag_run_id") or ""
            started = latest.get("start_date") or "-"
            ended = latest.get("end_date") or "-"
            if state == "success":
                st.success(f"{label}: success · {run_id}")
            elif state in {"running", "queued"}:
                st.info(f"{label}: {state} · {run_id}")
            elif state == "failed":
                st.error(f"{label}: failed · {run_id}")
            else:
                st.caption(f"{label}: {state} · {run_id}")
            st.caption(f"시작 {started} · 종료 {ended}")
    except AirflowTriggerError as exc:
        st.warning("Airflow 상태를 불러오지 못했습니다.")
        st.caption(str(exc))


def render_ingestion_jobs(show_title=True):
    if show_title:
        st.subheader("최근 파싱 작업")
    db = SessionLocal()
    try:
        jobs = [
            {
                "id": job.id,
                "exam_name": job.exam_name,
                "pdf_path": job.pdf_path,
                "status": job.status,
                "stage": job.stage,
                "message": job.message,
                "current": job.current,
                "total": job.total,
                "inserted": job.inserted,
                "output_json": job.output_json,
                "quality_score": job.quality_score,
                "quality_status": job.quality_status,
                "quality_report_json": job.quality_report_json,
                "quality_gate_json": job.quality_gate_json,
                "error_message": job.error_message,
            }
            for job in IngestionJobService(db).list_jobs()
        ]
    finally:
        db.close()

    if st.button("작업 상태 새로고침", use_container_width=True):
        st.rerun()

    if not jobs:
        st.info("등록된 파싱 작업이 없습니다.")
        return

    for job in jobs:
        title = f"#{job['id']} {job['exam_name']} · {job['status']}"
        with st.expander(title, expanded=job["status"] in {"queued", "running", "held"}):
            st.write(job["pdf_path"])
            ratio = min(max((job["current"] or 0) / max(job["total"] or 1, 1), 0), 1)
            st.progress(ratio)
            st.caption(f"{job['stage']}: {job['message'] or ''}")
            st.caption(f"{job['current'] or 0} / {job['total'] or 1} · 적재 {job['inserted'] or 0}개")
            if job.get("quality_status"):
                st.caption(f"품질 게이트: {job['quality_status']} · 점수 {job.get('quality_score') if job.get('quality_score') is not None else '-'}")
            if job["error_message"]:
                st.error(job["error_message"][:1200])
            render_quality_gate_report(job.get("quality_gate_json"))
            render_parse_quality_report(job.get("output_json"), job.get("quality_report_json"))
            log_path = Path("data/run_logs") / f"job_{job['id']}.log"
            if log_path.exists():
                if st.toggle("로그 보기", key=f"show_job_log_{job['id']}"):
                    st.code(log_path.read_text(encoding="utf-8")[-3000:])


def render_quality_gate_report(gate_json):
    if not gate_json:
        return
    gate_path = Path(gate_json)
    if not gate_path.exists():
        return
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except Exception:
        return
    status = gate.get("status") or "unknown"
    action = gate.get("action") or "unknown"
    reason = gate.get("reason") or ""
    if action == "hold":
        st.error(f"자동 판정: 보류 · {status}")
    elif action == "proceed_with_review":
        st.warning(f"자동 판정: 경고 적재 · {status}")
    else:
        st.success(f"자동 판정: 통과 · {status}")
    if reason:
        st.caption(reason)


def render_parse_quality_report(output_json, quality_report_json=None):
    if not output_json and not quality_report_json:
        st.caption("파싱 품질 리포트: 아직 생성 전")
        return
    report_path = Path(quality_report_json or default_quality_report_path(output_json))
    if not report_path.exists():
        st.caption("파싱 품질 리포트: 없음")
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        st.warning(f"파싱 품질 리포트를 읽지 못했습니다: {exc}")
        return

    score = int(report.get("score") or 0)
    status = report.get("status") or "unknown"
    question_count = int(report.get("question_count") or 0)
    if score >= 85:
        st.success(f"파싱 품질 {score}점 · {status} · {question_count}문항")
    elif score >= 65:
        st.warning(f"파싱 품질 {score}점 · {status} · {question_count}문항")
    else:
        st.error(f"파싱 품질 {score}점 · {status} · {question_count}문항")

    with st.expander("파싱/청킹 품질 리포트", expanded=score < 85):
        issue_counts = report.get("issue_counts") or {}
        if issue_counts:
            st.dataframe(
                [{"이슈": key, "개수": value} for key, value in sorted(issue_counts.items(), key=lambda row: (-row[1], row[0]))],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("감지된 구조 이슈가 없습니다.")

        metrics = report.get("metrics") or {}
        numbers = metrics.get("numbers") or {}
        chunks = metrics.get("chunk_lengths") or {}
        st.caption(
            f"번호 {numbers.get('first')}~{numbers.get('last')} · "
            f"청크 길이 min/median/max {chunks.get('min')}/{chunks.get('median')}/{chunks.get('max')}"
        )
        if numbers.get("gaps"):
            st.warning("번호 누락 의심: " + ", ".join(f"{start}-{end}" if start != end else str(start) for start, end in numbers["gaps"][:12]))
        if numbers.get("duplicates"):
            st.warning("번호 중복 의심: " + ", ".join(str(number) for number in numbers["duplicates"][:20]))

        samples = report.get("samples") or []
        if samples:
            st.markdown("##### 우선 확인할 샘플")
            for sample in samples[:10]:
                issue_text = " / ".join(issue.get("code", "") for issue in sample.get("issues", []))
                st.markdown(f"**#{sample.get('number') or sample.get('index')} · p.{sample.get('page')}** · {issue_text}")
                st.caption(sample.get("stem_preview") or sample.get("raw_preview") or "")
        st.caption(f"리포트 파일: {report_path.as_posix()}")


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

    db, service = SessionLocal(), None
    try:
        service = StudyAssistantService(
            db,
            vector_store=QuestionVectorStore(embedding_model=embedding_model),
        )
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
    finally:
        db.close()


def render_vector_index():
    st.subheader("AI 색인")
    embedding_model = st.selectbox(
        "임베딩 모델",
        EMBEDDING_MODEL_OPTIONS,
        index=EMBEDDING_MODEL_OPTIONS.index(DEFAULT_EMBEDDING_MODEL)
        if DEFAULT_EMBEDDING_MODEL in EMBEDDING_MODEL_OPTIONS
        else 0,
        help="한국어 질문과 영어 Azure Docs를 같이 검색하려면 BAAI/bge-m3를 추천합니다.",
    )
    st.caption(f"Chroma 컬렉션은 임베딩 모델별로 분리됩니다. 현재 모델: `{embedding_model}`")
    db, service = SessionLocal(), None
    try:
        service = StudyAssistantService(
            db,
            vector_store=QuestionVectorStore(embedding_model=embedding_model),
        )
        if st.button("문제 DB 벡터 색인", type="primary", use_container_width=True):
            with st.spinner("문제와 해설을 Chroma에 색인하는 중입니다."):
                indexed = service.index_questions()
            st.success(f"{indexed}개 문항을 색인했습니다.")

        st.divider()
        st.markdown("#### Azure Docs")
        docs_service = AzureDocsService(db, embedding_model=embedding_model)
        latest_sync = docs_service.latest_sync()
        if latest_sync:
            st.caption(
                f"마지막 동기화: {latest_sync.status} · "
                f"{latest_sync.documents_indexed or 0}개 문서 · "
                f"{latest_sync.chunks_indexed or 0}개 chunk · "
                f"{latest_sync.completed_at or latest_sync.created_at}"
            )
            if latest_sync.error_message:
                st.error(latest_sync.error_message[:1000])
        else:
            st.caption("아직 Azure Docs 색인이 없습니다.")
        st.caption("권장 주기: 분기 1회 · 시험 직전에는 수동 동기화를 한 번 실행하세요.")
        docs_limit = st.number_input("동기화할 Azure Docs URL 수", min_value=1, max_value=50, value=12, step=1)
        if st.button("Azure Docs 벡터 색인", use_container_width=True):
            with st.spinner("Azure Docs를 가져와 Chroma에 색인하는 중입니다. 첫 실행은 모델 다운로드 때문에 오래 걸릴 수 있습니다."):
                summary = docs_service.sync(limit=int(docs_limit))
            if summary["status"] == "success":
                st.success(summary["message"])
            else:
                st.error(summary["message"])
                if summary.get("error_message"):
                    st.caption(summary["error_message"])
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


def main():
    ensure_runtime_dirs()
    init_db(verbose=False)
    db = SessionLocal()
    try:
        seed_demo_questions_if_empty(db)
    finally:
        db.close()
    init_state()
    inject_pwa_assets()
    apply_mobile_styles()

    st.title("Cert Study Lab")
    exams = get_exams()
    page = st.session_state.page

    if page == "홈":
        render_home(exams)
        return

    render_back_home()
    if page == "대시보드":
        render_dashboard(exams)
        return
    if page in {"이어서 공부", "Daily Mode"}:
        render_continue_study()
        return
    if page == "Focus Mode":
        render_focus_mode()
        return
    if page == "Exam Mode":
        render_exam_study_mode()
        return
    if page == "오늘 학습 세션":
        render_continue_study()
        return
    if page == "로드맵":
        render_roadmap()
        return
    if page == "이론 학습":
        render_theory_learning()
        return
    if page == "확인 퀴즈":
        render_learning_quiz()
        return
    if page == "시험 모드":
        render_exam_mode()
        return
    if page == "실습하기":
        render_lab_practice()
        return
    if page == "진도율":
        render_progress()
        return
    if page == "콘텐츠 관리":
        render_content_management()
        return

    selected_exam, selected_source = render_exam_selector(exams)

    if page == "시험 현황":
        render_exam_overview(exams, selected_exam)
    elif page in {"처리 현황", "자동 정리 현황", "문제 검수"}:
        render_review(selected_source)
    elif page in {"문제 풀이", "자격증 문제"}:
        render_quiz(selected_source)
    elif page in {"취약 개념 학습", "취약 유형 학습"}:
        render_weak_quiz(selected_source)
    elif page in {"같은 단원 학습", "비슷한 유형 학습"}:
        render_similar_quiz()
    elif page in {"오답/복습", "오답노트"}:
        render_notes(selected_source)
    elif page == "개념 정리":
        render_concept_notes(selected_source)
    elif page == "AI 색인":
        render_vector_index()
    elif page == "파싱 작업 상태":
        render_review(selected_source)
    else:
        render_upload(exams)


if __name__ == "__main__":
    main()

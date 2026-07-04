import os
import re
import json
import random
from datetime import datetime, date, timedelta
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
from cert_study_app.services.concept_note_service import ConceptNoteService
from cert_study_app.services.demo_seed_service import seed_demo_questions_if_empty, seed_concept_questions
from cert_study_app.services.docs_source_service import active_docs_sources, doc_source_by_id, docs_source_options
from cert_study_app.services.ingestion_job_service import IngestionJobService
from cert_study_app.services.official_docs_service import OfficialDocsService
from cert_study_app.services.learning_lab_service import (
    PRACTICE_TASKS,
    active_tracks,
    certification_for_track,
    certifications_for_track,
    evaluate_lab_quiz,
    evaluate_lab_quiz_detail,
    evaluate_practice,
    evaluate_practice_detail,
    lessons_for_track,
    normalize_track_id,
    quizzes_for_track,
    roadmap_for_track,
    track_by_id,
    track_progress,
)
from cert_study_app.services.learning_progress_service import (
    completed_steps,
    lab_spaced_review_count,
    lab_spaced_review_due_today,
    load_completed_items,
    load_wrong_notes,
    mark_learning_step,
    next_day_recommendation,
    preferred_track,
    record_activity,
    save_completed_items,
    save_preferred_track,
    save_wrong_notes,
    spaced_review_count,
    spaced_review_due_today,
    streak_days,
    study_units,
    update_lab_spaced_review,
    update_spaced_review,
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
    st.session_state.setdefault("lab_lesson_index", 0)
    st.session_state.setdefault("lab_quiz_index", 0)
    st.session_state.setdefault("lab_practice_index", 0)
    if "lab_completed_lessons" not in st.session_state:
        lessons, quizzes, practices = load_completed_items()
        st.session_state.lab_completed_lessons = lessons
        st.session_state.lab_completed_quizzes = quizzes
        st.session_state.lab_completed_practices = practices
    if "lab_wrong_notes" not in st.session_state:
        st.session_state.lab_wrong_notes = load_wrong_notes()
    st.session_state.setdefault("quiz_skill_category", "전체")
    st.session_state.setdefault("quiz_skill_subcategory", "전체")
    st.session_state.setdefault("lab_lesson_just_completed", None)


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

        /* ── Primary button enhancement ─────────────────────────── */
        div[data-testid="stBaseButton-primary"] > button,
        button[data-testid="stBaseButton-primary"] {
            font-size: 1rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em !important;
            min-height: 52px !important;
        }

        /* ── Home Hero ─────────────────────────────────────────── */
        .cert-hero {
            background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
            border-radius: 14px 14px 0 0;
            padding: 1.3rem 1.3rem 1rem;
            margin-bottom: 0;
            color: #fff;
        }
        /* pull next element-container flush so button attaches */
        div[data-testid="element-container"]:has(.cert-hero) {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        div[data-testid="element-container"]:has(.cert-hero)
            + div[data-testid="element-container"]
            button[data-testid="stBaseButton-primary"] {
            border-top-left-radius: 0 !important;
            border-top-right-radius: 0 !important;
            margin-top: 0 !important;
        }
        .cert-hero-track {
            font-size: 0.78rem;
            opacity: 0.75;
            margin-bottom: 0.2rem;
            letter-spacing: 0.02em;
        }
        .cert-hero-streak {
            font-size: 1.45rem;
            font-weight: 800;
            margin-bottom: 0.85rem;
            letter-spacing: -0.02em;
        }
        .cert-hero-bar-wrap {
            background: rgba(255,255,255,0.22);
            border-radius: 6px;
            height: 9px;
            overflow: hidden;
            margin-bottom: 0.4rem;
        }
        .cert-hero-bar-fill {
            height: 100%;
            border-radius: 6px;
            background: #93c5fd;
            transition: width 0.4s ease;
        }
        .cert-hero-bar-label {
            font-size: 0.8rem;
            opacity: 0.85;
        }
        /* ── Home Stats ─────────────────────────────────────────── */
        .cert-stats-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
            margin: 0.55rem 0 0.7rem;
        }
        .cert-stat-card {
            background: rgba(37, 99, 235, 0.05);
            border: 1px solid rgba(37, 99, 235, 0.14);
            border-radius: 10px;
            padding: 0.7rem 0.85rem;
            text-align: center;
        }
        .cert-stat-card.alert {
            background: rgba(239, 68, 68, 0.05);
            border-color: rgba(239, 68, 68, 0.22);
        }
        .cert-stat-value {
            font-size: 1.45rem;
            font-weight: 800;
            color: #2563eb;
            line-height: 1.1;
        }
        .cert-stat-card.alert .cert-stat-value { color: #dc2626; }
        .cert-stat-label {
            font-size: 0.75rem;
            color: rgba(15, 23, 42, 0.55);
            margin-top: 0.15rem;
        }
        /* ── Section title ───────────────────────────────────────── */
        .cert-section-title {
            margin: 1.1rem 0 0.4rem;
            font-size: 0.88rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.5);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        /* ── Mode status chips ──────────────────────────────────── */
        .cert-chip {
            display: inline-block;
            padding: 0.1rem 0.55rem;
            border-radius: 99px;
            font-size: 0.72rem;
            font-weight: 600;
            vertical-align: middle;
            margin-left: 0.35rem;
        }
        .cert-chip-done   { background: rgba(34,197,94,0.12); color: #15803d; }
        .cert-chip-active { background: rgba(37,99,235,0.1);  color: #1d4ed8; }
        .cert-chip-alert  { background: rgba(239,68,68,0.1);  color: #dc2626; }
        .cert-chip-dim    { background: rgba(15,23,42,0.06);  color: rgba(15,23,42,0.45); }
        /* ── Today Steps ─────────────────────────────────────────── */
        .cert-steps-row {
            display: flex;
            gap: 0.3rem;
            margin: 0.55rem 0 0.75rem;
        }
        .cert-step {
            flex: 1;
            text-align: center;
            padding: 0.45rem 0.2rem 0.35rem;
            border-radius: 8px;
            font-size: 0.72rem;
            font-weight: 600;
            line-height: 1.4;
        }
        .cert-step-done    { background: rgba(34,197,94,0.1); color: #15803d; }
        .cert-step-next    { background: rgba(37,99,235,0.1); color: #1d4ed8;
                             border: 1.5px solid rgba(37,99,235,0.25); }
        .cert-step-pending { background: rgba(15,23,42,0.04); color: rgba(15,23,42,0.38); }
        /* ── Mode cards (clickable full row) ────────────────────── */
        .cert-mode-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.7rem 0.85rem;
            margin-bottom: 0.4rem;
            border: 1px solid var(--cert-border);
            border-radius: 10px;
            cursor: pointer;
            background: #fff;
        }
        .cert-mode-card:active { background: rgba(37,99,235,0.04); }
        .cert-mode-left { flex: 1; }
        .cert-mode-title { font-size: 0.92rem; font-weight: 700; }
        .cert-mode-desc  { font-size: 0.76rem; color: rgba(15,23,42,0.5); margin-top: 0.1rem; }
        .cert-mode-arrow { font-size: 1.1rem; color: rgba(15,23,42,0.3); padding-left: 0.6rem; }
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


def render_top_bar():
    title_col, menu_col = st.columns([0.74, 0.26], vertical_alignment="center")
    title_col.title("Cert Study Lab")
    with menu_col.popover("메뉴", use_container_width=True):
        st.caption("학습 모드")
        menu_items = [
            ("📖 개념 공부", "개념공부"),
            ("🖥 실습", "실습"),
            ("📋 시험 준비", "시험준비"),
            ("오답노트", "오답노트"),
            ("학습 현황", "대시보드"),
        ]
        for label, page in menu_items:
            if st.button(label, use_container_width=True, key=f"menu_study_{page}"):
                go_to(page)

        st.divider()
        st.caption("관리")
        admin_items = [
            ("콘텐츠 관리", "콘텐츠 관리"),
            ("PDF 업로드", "PDF 업로드"),
            ("처리 현황", "처리 현황"),
            ("시험 현황", "시험 현황"),
            ("AI 색인", "AI 색인"),
        ]
        for label, page in admin_items:
            if st.button(label, use_container_width=True, key=f"menu_admin_{page}"):
                go_to(page)


def track_for_question_source(source):
    normalized = (source or "").strip().lower()
    if normalized.startswith("az-104") or "azure" in normalized:
        return "azure"
    if "linux" in normalized or "lfcs" in normalized:
        return "linux"
    return normalize_track_id(st.session_state.get("lab_track", "linux"))


def render_home(exams):
    # ── Track 스위처 ────────────────────────────────────────────
    tracks = active_tracks()
    track_ids = [t["id"] for t in tracks]
    track_labels = [t["name"] for t in tracks]
    current_track_id = normalize_track_id(st.session_state.get("lab_track", preferred_track()))
    current_idx = track_ids.index(current_track_id) if current_track_id in track_ids else 0
    selected_label = st.radio("", track_labels, index=current_idx, horizontal=True)
    track_id = track_ids[track_labels.index(selected_label)]
    if track_id != st.session_state.get("lab_track"):
        save_preferred_track(track_id)
        st.session_state.lab_track = track_id

    # ── 데이터 ──────────────────────────────────────────────────
    certification = certification_for_track(track_id)
    session_done = completed_steps(track_id)
    streak = streak_days()
    units = study_units()
    due_count = spaced_review_count()

    _, _, apply_action_label, apply_target = focus_apply_step(track_id)

    # 3모드 진도
    concept_done = {"lesson", "quiz"} <= session_done
    practice_done = "apply" in session_done
    review_done = "review" in session_done
    done_count = sum([concept_done, practice_done, review_done])
    all_done = done_count == 3

    # Smart CTA: 가장 앞에 안 된 단계로 직접 안내
    if not concept_done:
        if "lesson" not in session_done:
            next_label = "이론 카드 시작하기 →"
            next_page = "이론 학습"
        else:
            next_label = "확인 퀴즈 이어가기 →"
            next_page = "확인 퀴즈"
    elif not practice_done:
        next_label = f"{apply_action_label} →"
        next_page = "실습" if track_id != "azure" else "시험준비"
    elif not review_done:
        next_label = "오답 복습하기 →"
        next_page = "오답노트"
    else:
        next_label = "시험 문제 더 풀기 →"
        next_page = "시험준비"

    # ── 완료 축하 (오늘 처음 완료 시 한 번만) ────────────────────
    celebrate_key = f"_celebrated_{track_id}_{date.today().isoformat()}"
    if all_done and not st.session_state.get(celebrate_key):
        st.session_state[celebrate_key] = True
        st.balloons()

    # ── Hero 카드 ────────────────────────────────────────────────
    streak_text = f"🔥 {streak}일 연속 학습 중" if streak > 0 else "오늘 첫 학습을 시작해보세요"
    step_label = "오늘 목표 달성! 🎉" if all_done else f"오늘 {done_count}/3 단계 완료"
    bar_pct = done_count / 3 * 100
    cert_name = certification.get("name", "")

    st.markdown(
        f"""
        <div class="cert-hero">
            <div class="cert-hero-track">{cert_name} 대비</div>
            <div class="cert-hero-streak">{streak_text}</div>
            <div class="cert-hero-bar-wrap">
                <div class="cert-hero-bar-fill" style="width:{bar_pct:.0f}%"></div>
            </div>
            <div class="cert-hero-bar-label">{step_label}</div>
        </div>
        <script>
        (function() {{
            function connect() {{
                try {{
                    var doc = window.parent.document;
                    var heroes = doc.querySelectorAll('.cert-hero');
                    heroes.forEach(function(hero) {{
                        hero.style.borderBottomLeftRadius = '0';
                        hero.style.borderBottomRightRadius = '0';
                        hero.style.marginBottom = '0';
                        var el = hero;
                        while (el && el.getAttribute && el.getAttribute('data-testid') !== 'element-container') el = el.parentElement;
                        if (!el) return;
                        var sib = el.nextElementSibling;
                        for (var i = 0; i < 4 && sib; i++) {{
                            var btn = sib.querySelector('button[data-testid="stBaseButton-primary"]');
                            if (btn) {{
                                btn.style.borderTopLeftRadius = '0';
                                btn.style.borderTopRightRadius = '0';
                                break;
                            }}
                            sib = sib.nextElementSibling;
                        }}
                    }});
                }} catch(e) {{}}
            }}
            setTimeout(connect, 120);
            setTimeout(connect, 600);
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )

    # ── 오늘 3단계 진도 표시 ────────────────────────────────────────
    def _step_cls(done): return "cert-step-done" if done else ("cert-step-next" if True else "cert-step-pending")
    step1_cls = "cert-step-done" if concept_done else "cert-step-next"
    step2_cls = "cert-step-done" if practice_done else ("cert-step-next" if concept_done else "cert-step-pending")
    step3_cls = "cert-step-done" if review_done else ("cert-step-next" if practice_done else "cert-step-pending")
    st.markdown(
        f"""
        <div class="cert-steps-row">
            <div class="cert-step {step1_cls}">{"✓" if concept_done else "①"}<br>개념</div>
            <div class="cert-step {step2_cls}">{"✓" if practice_done else "②"}<br>실습</div>
            <div class="cert-step {step3_cls}">{"✓" if review_done else "③"}<br>복습</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if all_done:
        if st.button("🎉 오늘 완료! 추가 문제 더 풀기", type="primary", use_container_width=True):
            go_to("자격증 문제")
    else:
        if st.button(next_label, type="primary", use_container_width=True):
            if next_page == apply_target and track_id == "azure":
                st.session_state.exam_source = "AZ-104"
            go_to(next_page)

    # ── 통계 카드 ────────────────────────────────────────────────
    due_class = "cert-stat-card alert" if due_count > 0 else "cert-stat-card"
    due_value = str(due_count) if due_count > 0 else "—"
    st.markdown(
        f"""
        <div class="cert-stats-row">
            <div class="{due_class}">
                <div class="cert-stat-value">{due_value}</div>
                <div class="cert-stat-label">간격 복습 대기</div>
            </div>
            <div class="cert-stat-card">
                <div class="cert-stat-value">{units:.1f}</div>
                <div class="cert-stat-label">오늘 활동 단위</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if due_count > 0:
        due_ids = spaced_review_due_today(limit=1)
        if due_ids:
            if st.button(f"간격 복습 시작 ({due_count}문제 대기)", use_container_width=True):
                st.session_state.question_id = due_ids[0]
                st.session_state.exam_source = None
                st.session_state.selected = None
                st.session_state.last_result = None
                go_to("자격증 문제")

    # ── 3 모드 카드 ─────────────────────────────────────────────
    st.markdown('<div class="cert-section-title">학습 모드</div>', unsafe_allow_html=True)

    # 1. 개념 공부
    lessons = lessons_for_track(track_id)
    quizzes_list = quizzes_for_track(track_id)
    _cl = st.session_state.lab_completed_lessons
    _cq = st.session_state.lab_completed_quizzes
    done_lessons = len([l for l in lessons if l.id in _cl])
    done_quizzes = len([q for q in quizzes_list if q.id in _cq])
    c_chip_txt = "✓ 완료" if concept_done else "학습 중"
    c_desc = f"이론 {done_lessons}/{len(lessons)} · 퀴즈 {done_quizzes}/{len(quizzes_list)}"
    concept_target = "개념공부" if concept_done else ("이론 학습" if "lesson" not in session_done else "확인 퀴즈")
    if st.button(
        f"📖 개념 공부  ·  {c_desc}  ·  {c_chip_txt} →",
        key="home_concept",
        use_container_width=True,
        type="secondary",
    ):
        go_to(concept_target)

    # 2. 실습 / 문제 적용
    practices = [t for t in PRACTICE_TASKS if t.track == track_id and t.status == "approved"]
    _cp = st.session_state.lab_completed_practices
    done_practices = len([t for t in practices if t.id in _cp])
    if track_id == "azure":
        p_title, p_page = "📝 문제 적용", "시험준비"
        p_desc = "AZ-104 실전 문제 적용"
        p_chip_txt = "✓ 완료" if practice_done else "학습 중"
    elif practices:
        p_title, p_page = "🖥 실습", "실습"
        p_desc = f"실습 {done_practices}/{len(practices)}"
        p_chip_txt = "✓ 완료" if practice_done else "학습 중"
    else:
        p_title, p_desc, p_page = "🖥 실습", "이 Track은 실습 과제를 준비 중입니다", "실습"
        p_chip_txt = "준비 중"
    if st.button(
        f"{p_title}  ·  {p_desc}  ·  {p_chip_txt} →",
        key="home_practice",
        use_container_width=True,
        type="secondary",
    ):
        if p_page == "시험준비" and track_id == "azure":
            st.session_state.exam_source = "AZ-104"
        go_to(p_page)

    # 3. 시험 준비
    total_questions = sum(exam["count"] for exam in exams)
    if track_id == "azure" and total_questions > 0:
        e_desc = f"AZ-104 덤프 {total_questions}문제 · 간격 반복"
        e_chip_txt = f"복습 {due_count}개 대기" if due_count > 0 else "준비됨"
    else:
        e_desc = "덤프 문제 풀이 · AZ-104만 현재 지원"
        e_chip_txt = f"복습 {due_count}개 대기" if due_count > 0 else "준비 중"
    if st.button(
        f"📋 시험 준비  ·  {e_desc}  ·  {e_chip_txt} →",
        key="home_exam",
        use_container_width=True,
        type="secondary",
    ):
        go_to("시험준비")


def render_back_home():
    if st.button("처음으로", use_container_width=True):
        go_to("홈")


# ── 모드 랜딩 페이지 ─────────────────────────────────────────────

def render_concept_mode_home():
    """개념 공부 랜딩: 이론 카드 → 확인 퀴즈 순서를 안내하고 진입시킨다."""
    track_id = selected_lab_track()
    certification = certification_for_track(track_id)
    lessons = lessons_for_track(track_id)
    quizzes_list = quizzes_for_track(track_id)
    session_done = completed_steps(track_id)
    lesson_done = "lesson" in session_done
    quiz_done = "quiz" in session_done

    st.subheader("📖 개념 공부")
    st.caption(f"{certification.get('name', '')} 대비 · 이론 카드를 보고 확인 퀴즈로 이해도를 점검합니다")
    st.info("💡 이 섹션은 **직접 제작한 개념 학습 콘텐츠**입니다. 아래 '시험 준비'의 덤프 문제와는 별개입니다. 개념을 이해한 뒤 시험 준비로 넘어가면 효과적입니다.", icon=None)

    with st.container(border=True):
        done_chip = "<span class='cert-chip cert-chip-done'>✓ 완료</span>" if lesson_done else ""
        st.markdown(f"**이론 카드** {done_chip}", unsafe_allow_html=True)
        st.caption(f"{len(lessons)}개 카드 · 핵심 개념을 정리합니다. 모르는 게 있으면 다음 카드로 이어갑니다.")
        btn_label = "이어서 보기" if lesson_done else "시작하기"
        btn_type = "secondary" if lesson_done else "primary"
        if st.button(btn_label, type=btn_type, use_container_width=True, key="concept_lesson_btn"):
            go_to("이론 학습")

    with st.container(border=True):
        done_chip = "<span class='cert-chip cert-chip-done'>✓ 완료</span>" if quiz_done else ""
        st.markdown(f"**확인 퀴즈** {done_chip}", unsafe_allow_html=True)
        st.caption(f"{len(quizzes_list)}문제 · 방금 본 개념을 짧은 퀴즈로 점검합니다.")
        btn_label = "다시 풀기" if quiz_done else "퀴즈 풀기"
        btn_type = "secondary" if quiz_done else "primary"
        if st.button(btn_label, type=btn_type, use_container_width=True, key="concept_quiz_btn"):
            go_to("확인 퀴즈")

    if lesson_done and quiz_done:
        st.success("오늘 개념 공부를 마쳤습니다. 실습이나 시험 준비로 이어갈 수 있습니다.")


def render_practice_mode_home():
    """실습 랜딩: track별 실습 현황과 진입 버튼."""
    track_id = selected_lab_track()
    certification = certification_for_track(track_id)
    practices = [t for t in PRACTICE_TASKS if t.track == track_id and t.status == "approved"]
    completed = st.session_state.lab_completed_practices
    done_ids = completed & {t.id for t in practices}
    session_done = completed_steps(track_id)
    apply_done = "apply" in session_done

    st.subheader("🖥 실습")
    st.caption(f"{certification.get('name', '')} 대비 · 명령어나 도구를 직접 실행해 봅니다")

    if not practices:
        st.info(
            "이 Track은 아직 실습 과제를 준비 중입니다. "
            "Linux Track을 선택하면 LFCS 명령어 실습을 바로 시작할 수 있습니다."
        )
        return

    progress_pct = len(done_ids) / len(practices) if practices else 0
    st.progress(progress_pct, text=f"전체 진도 {len(done_ids)}/{len(practices)} 완료")

    if apply_done:
        st.success("오늘 실습을 완료했습니다.")

    btn_label = "실습 이어가기" if len(done_ids) > 0 else "실습 시작하기"
    btn_type = "secondary" if apply_done else "primary"
    if st.button(btn_label, type=btn_type, use_container_width=True):
        go_to("실습하기")

    with st.expander("실습 가이드", expanded=False):
        st.write(
            "명령어를 직접 입력하고 채점을 받습니다. "
            "힌트를 보면 학습 효과가 줄어드니 최대한 혼자 먼저 시도해 보세요. "
            "틀려도 바로 다음 문제로 넘어가지 말고 정답 명령어를 한 번 직접 쳐보는 걸 권장합니다."
        )


def render_exam_prep_home(exams):
    """시험 준비 랜딩: 시험별 문제 풀이 + 간격 복습 진입."""
    st.subheader("📋 시험 준비")
    st.caption("덤프 문제로 실전 감각을 익히고, 틀린 문제는 간격 반복으로 완전히 내 것으로 만듭니다.")
    st.info("💡 여기는 **실제 시험 형식 문제 풀이** 공간입니다. 개념이 아직 익숙하지 않다면 '개념 공부'를 먼저 하세요.", icon=None)

    due_count = spaced_review_count()

    # 간격 복습 배너 (우선순위 높음)
    if due_count > 0:
        with st.container(border=True):
            st.markdown(f"**🔁 간격 복습 · {due_count}문제 대기**")
            st.caption("틀렸던 문제가 오늘 복습 기한이 됐습니다. 복습부터 하면 장기 기억 효율이 높아집니다.")
            if st.button(f"복습 시작 ({due_count}문제)", type="primary", use_container_width=True):
                due_ids = spaced_review_due_today(limit=1)
                if due_ids:
                    st.session_state.question_id = due_ids[0]
                    st.session_state.exam_source = None
                    st.session_state.selected = None
                    st.session_state.last_result = None
                    go_to("자격증 문제")

    # 시험별 문제 풀이
    st.markdown('<div class="cert-section-title">시험별 문제 풀이</div>', unsafe_allow_html=True)

    az_exam = next((e for e in exams if e.get("source") == "AZ-104"), None)
    with st.container(border=True):
        tc, bc = st.columns([4, 1])
        tc.markdown("**AZ-104** · Microsoft Azure Administrator")
        if az_exam:
            tc.caption(f"문제은행 {az_exam['count']}문항 · 준비됨")
        else:
            tc.caption("준비됨 · 문제 수를 불러오는 중")
        if bc.button("시작", key="exam_az104", use_container_width=True):
            st.session_state.exam_source = "AZ-104"
            go_to("자격증 문제")

    with st.container(border=True):
        tc, bc = st.columns([4, 1])
        tc.markdown("**LFCS** · Linux Foundation Certified Sysadmin")
        tc.caption("문제은행 준비 중 · 현재는 실습으로 대비")
        if bc.button("실습으로 이동", key="exam_lfcs", use_container_width=True):
            go_to("실습")

    # 개념 모의시험 (JSON 퀴즈 기반)
    st.markdown('<div class="cert-section-title">개념 모의시험</div>', unsafe_allow_html=True)
    with st.container(border=True):
        tc, bc = st.columns([4, 1])
        tc.markdown("**🧪 개념 모의시험** · 직접 제작 퀴즈 기반")
        tc.caption("이론·CLI 퀴즈를 랜덤 출제, 타이머 있음 · 덤프 문제와 별개")
        if bc.button("시작", key="exam_concept_mock", use_container_width=True):
            go_to("시험 모드")

    st.markdown('<div class="cert-section-title">복습</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    if col1.button("오답노트", use_container_width=True):
        go_to("오답노트")
    if col2.button("취약 개념 학습", use_container_width=True):
        go_to("취약 개념 학습")


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
    labels = []
    for track in tracks:
        certification_names = " / ".join(certification["name"] for certification in certifications_for_track(track["id"]))
        labels.append(f"{track['name']} · {certification_names or '미정'}")
    ids = [track["id"] for track in tracks]
    current = normalize_track_id(st.session_state.get("lab_track", "linux"))
    index = ids.index(current) if current in ids else 0
    selected_label = st.selectbox("Track", labels, index=index)
    track_id = ids[labels.index(selected_label)]
    if track_id != st.session_state.get("lab_track"):
        save_preferred_track(track_id)
    st.session_state.lab_track = track_id
    return track_id


def render_spaced_review_panel():
    due_count = spaced_review_count()
    if due_count == 0:
        return
    with st.container(border=True):
        st.markdown(f"#### 간격 복습 · 오늘 {due_count}문제 대기")
        st.caption("틀린 문제를 1→3→7→14→30일 간격으로 재출제합니다. 3회 연속 정답이면 완전 학습으로 처리됩니다.")
        due_ids = spaced_review_due_today(limit=5)
        for qid in due_ids:
            if st.button(f"문제 #{qid} 풀기", key=f"spaced_go_{qid}", use_container_width=True):
                st.session_state.question_id = qid
                st.session_state.exam_source = None
                st.session_state.selected = None
                st.session_state.last_result = None
                go_to("자격증 문제")
        if due_count > 5:
            st.caption(f"…외 {due_count - 5}문제")


def render_dashboard(exams):
    st.subheader("대시보드")
    st.caption("진도와 추천 복습은 여기에서만 확인합니다.")
    render_today_plan(exams)
    render_spaced_review_panel()
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
        focus_step_count = len(persisted_steps & {"lesson", "quiz", "apply", "review"})
        st.progress(focus_step_count / 4, text=f"Focus 진도 {focus_step_count}/4")
        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("연속 학습", f"{streak}일")
        metric2.metric("오늘 활동", f"{study_units():.1f}단위")
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


def focus_apply_step(track_id: str) -> tuple[str, str, str, str]:
    if track_id == "linux":
        return (
            "실습 적용",
            "방금 본 개념을 명령어 실습으로 바로 써봅니다.",
            "실습하기",
            "실습하기",
        )
    if track_id == "azure":
        return (
            "문제 적용",
            "개념을 AZ-104 문제에 바로 적용해 봅니다.",
            "문제 풀기",
            "자격증 문제",
        )
    return (
        "문서 적용",
        "공식 문서 카드와 퀴즈를 이어 보며 도구 개념을 굳힙니다.",
        "이론 이어보기",
        "이론 학습",
    )


def focus_step_flow(track_id: str) -> list[tuple[str, str, str, str, str]]:
    lessons = lessons_for_track(track_id)
    quizzes = quizzes_for_track(track_id)
    apply_title, apply_description, apply_label, apply_target = focus_apply_step(track_id)
    return [
        ("lesson", "개념 이해", f"카드 {min(1, len(lessons))}개부터 시작하고, 원하면 계속 다음 카드로 넘어갑니다.", "개념 보기", "이론 학습"),
        ("quiz", "바로 확인", f"{min(3, len(quizzes))}개로 이해도를 점검한 뒤 계속 풀 수 있습니다.", "확인 퀴즈 풀기", "확인 퀴즈"),
        ("apply", apply_title, apply_description, apply_label, apply_target),
        ("review", "오답 정리", "오답 1개부터 보고, 더 복습하면 누적 학습량으로 기록됩니다.", "오답 복습으로 이동", "오답노트"),
    ]


def render_focus_progress_flow(track_id: str):
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    session_done = completed_steps(track_id)
    session_steps = focus_step_flow(track_id)
    _, _, _, apply_target = focus_apply_step(track_id)

    st.caption(f"{track['name']} Track · {certification['name']} · 개념부터 오답까지 순서대로 이어갑니다.")
    done_count = len(session_done & {step[0] for step in session_steps})
    st.progress(done_count / len(session_steps), text=f"진도 흐름 {done_count}/{len(session_steps)} · 오늘 활동 {study_units():.1f}단위")
    if st.button("계속 이어가기", type="primary", use_container_width=True):
        if "lesson" not in session_done:
            go_to("이론 학습")
        if "quiz" not in session_done:
            go_to("확인 퀴즈")
        if "apply" not in session_done:
            if track_id == "azure":
                st.session_state.exam_source = "AZ-104"
            go_to(apply_target)
        if "review" not in session_done:
            go_to("오답노트")
        go_to("이론 학습")

    for index, (step_id, title, description, action_label, target_page) in enumerate(session_steps, 1):
        with st.container(border=True):
            done = step_id in session_done
            st.markdown(f"### {index}. {'완료 · ' if done else ''}{title}")
            st.write(description)
            col1, col2 = st.columns([1, 1])
            if col1.button(action_label, type="primary" if not done else "secondary", use_container_width=True, key=f"today_go_{step_id}"):
                if step_id == "apply" and track_id == "azure":
                    st.session_state.exam_source = "AZ-104"
                go_to(target_page)
            if col2.button("완료 체크", use_container_width=True, key=f"today_done_{step_id}", disabled=done):
                mark_learning_step(track_id, step_id)
                st.rerun()

    if done_count == len(session_steps):
        st.success("진도 흐름을 지나왔습니다. 더 공부하면 오늘 활동량에 계속 더해집니다.")


def render_continue_study():
    st.subheader("Focus")
    track_id = selected_lab_track()
    render_focus_progress_flow(track_id)


def render_focus_mode():
    st.subheader("Focus 공부")
    track_id = selected_lab_track()
    track = track_by_id(track_id)
    certification = certification_for_track(track_id)
    st.caption(f"{track['name']} Track · {certification['name']} · 진도를 이어가거나, 지금 필요한 것만 골라 공부합니다.")

    focus_mode = st.radio("공부 방식", ["진도 이어가기", "원하는 것만 하기"], horizontal=True)
    if focus_mode == "진도 이어가기":
        render_focus_progress_flow(track_id)
        return

    focus_options = ["개념", "확인", "적용", "오답", "로드맵"]
    selected_focus = st.radio("지금 할 것", focus_options, horizontal=True)
    apply_target = focus_apply_step(track_id)[3]
    focus_targets = {
        "개념": "이론 학습",
        "확인": "확인 퀴즈",
        "적용": apply_target,
        "오답": "오답노트",
        "로드맵": "로드맵",
    }
    focus_descriptions = {
        "개념": "새 개념을 먼저 정리합니다. 헷갈리는 용어와 자주 틀리는 포인트를 확인하기 좋습니다.",
        "확인": "짧은 퀴즈로 방금 아는지 바로 점검합니다.",
        "적용": "Linux는 실습, Azure는 문제 적용, Tool Docs는 문서 카드 복습으로 연결합니다.",
        "오답": "틀린 문제와 약한 개념을 다시 봅니다.",
        "로드맵": "지금 공부하는 Track의 전체 순서를 확인합니다.",
    }
    st.info(focus_descriptions[selected_focus])
    if st.button(f"{selected_focus} 시작", type="primary", use_container_width=True):
        go_to(focus_targets[selected_focus])

    if track_id == "tool_docs":
        st.info("Tool Docs는 공식 문서 요약 카드와 확인 퀴즈를 반복하는 방식으로 운영합니다.")
    elif track_id == "azure":
        st.info("AZ-104 문제풀이에 몰입하려면 `Exam`을 사용하세요.")


def render_exam_study_mode():
    st.subheader("Exam")
    st.caption("자격증 집중 모드입니다. 먼저 Track과 시험을 고른 뒤 현재 준비 상태에 맞게 공부합니다.")
    exam_tracks = [track for track in active_tracks() if track["id"] in {"azure", "linux"}]
    track_labels = [track["name"] for track in exam_tracks]
    current_track = normalize_track_id(st.session_state.get("lab_track", "linux"))
    track_index = next((index for index, track in enumerate(exam_tracks) if track["id"] == current_track), 0)
    selected_track_label = st.selectbox("Track", track_labels, index=track_index, key="exam_track_selector")
    selected_track = exam_tracks[track_labels.index(selected_track_label)]
    st.session_state.lab_track = selected_track["id"]
    save_preferred_track(selected_track["id"])

    certifications = certifications_for_track(selected_track["id"])
    cert_labels = [f"{cert['name']} · {cert['study_mode']}" for cert in certifications]
    selected_cert_label = st.selectbox("자격증", cert_labels, key="exam_certification_selector")
    certification = certifications[cert_labels.index(selected_cert_label)]

    if certification["id"] == "az-104":
        st.session_state.exam_source = "AZ-104"
    else:
        st.session_state.exam_source = None

    readiness_messages = {
        "ready_with_questions": "문제은행이 준비되어 있어 문제풀이와 세부개념 반복을 바로 사용할 수 있습니다.",
        "practice_based": "문제은행은 아직 없지만, 실습 과제와 명령어 수행으로 시험 대비를 진행합니다.",
        "concept_quiz_based": "문제은행은 아직 없지만, 개념 카드와 확인 퀴즈로 필기형 대비를 시작합니다.",
    }
    st.info(readiness_messages.get(certification.get("readiness"), "학습 자료를 준비 중입니다."))

    col1, col2 = st.columns(2)
    if col1.button("문제풀이", type="primary", use_container_width=True):
        if certification["id"] == "lfcs":
            st.toast("LFCS 문제은행은 아직 준비 중입니다. 실습형 학습으로 연결합니다.")
            go_to("실습하기")
        if certification["id"] == "linux-master":
            st.toast("리눅스마스터 문제은행은 아직 준비 중입니다. 확인 퀴즈로 연결합니다.")
            go_to("확인 퀴즈")
        go_to("자격증 문제")
    if col2.button("시험 모드 설정", use_container_width=True):
        go_to("시험 모드")
    col3, col4 = st.columns(2)
    if col3.button("세부개념 반복", use_container_width=True):
        if certification["id"] == "lfcs":
            go_to("로드맵")
        if certification["id"] == "linux-master":
            go_to("이론 학습")
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
    all_lessons = lessons_for_track(track_id)
    if not all_lessons:
        st.info("아직 승인된 이론 카드가 없습니다.")
        return

    # ── 검색 / 필터 ──────────────────────────────────────────────────────────
    search_col, level_col, filter_col = st.columns([3, 1, 1])
    search_q = search_col.text_input("레슨 검색", placeholder="키워드 또는 제목 입력…", label_visibility="collapsed", key="lesson_search")
    level_filter = level_col.selectbox("레벨", ["전체", "입문", "중급", "고급"], key="lesson_level_filter", label_visibility="collapsed")
    show_incomplete = filter_col.checkbox("미완료만", key="lesson_incomplete_only")

    completed_lessons = st.session_state.lab_completed_lessons
    lessons = all_lessons
    if search_q.strip():
        q = search_q.strip().lower()
        lessons = [l for l in lessons if q in l.title.lower() or any(q in kw.lower() for kw in l.keywords) or q in l.summary.lower()]
    if level_filter != "전체":
        lessons = [l for l in lessons if l.level == level_filter]
    if show_incomplete:
        lessons = [l for l in lessons if l.id not in completed_lessons]

    if not lessons:
        st.info("검색 결과가 없습니다.")
        return

    # 필터 결과 내에서 index 유지
    raw_index = st.session_state.lab_lesson_index
    # lesson의 전체 index를 기준으로 필터된 lessons에서 현재 위치 찾기
    if raw_index < len(all_lessons):
        cur_id = all_lessons[raw_index].id
        filtered_ids = [l.id for l in lessons]
        if cur_id in filtered_ids:
            index = filtered_ids.index(cur_id)
        else:
            index = 0
    else:
        index = 0
    index = min(index, len(lessons) - 1)
    lesson = lessons[index]

    # 진도 표시
    done_count = len([l for l in all_lessons if l.id in completed_lessons])
    st.progress(done_count / len(all_lessons), text=f"{done_count}/{len(all_lessons)} 완료")
    if search_q.strip() or show_incomplete:
        st.caption(f"필터 결과: {len(lessons)}개 · {index + 1}/{len(lessons)}")
    else:
        st.caption(f"{index + 1}/{len(all_lessons)}")

    is_done = lesson.id in completed_lessons
    _level_badge = {"입문": "🟢 입문", "중급": "🟡 중급", "고급": "🔴 고급"}.get(lesson.level, lesson.level)
    with st.container(border=True):
        title_line = f"### {'✅ ' if is_done else ''}{lesson.title}"
        st.markdown(title_line)
        st.caption(_level_badge)
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
        source = doc_source_by_id(lesson.source_id)
        if source:
            st.markdown(f"출처: [{source.provider} · {source.title}]({source.url})")

    if not is_done:
        if st.button("학습 완료", type="primary", use_container_width=True):
            st.session_state.lab_completed_lessons.add(lesson.id)
            save_completed_items(
                st.session_state.lab_completed_lessons,
                st.session_state.lab_completed_quizzes,
                st.session_state.lab_completed_practices,
            )
            mark_learning_step(track_id, "lesson")
            record_activity(track_id, "lesson", 1)
            st.session_state.lab_lesson_just_completed = lesson.id
            st.rerun()
    else:
        # 방금 완료한 경우 — 다음 단계 명확히 안내
        if st.session_state.get("lab_lesson_just_completed") == lesson.id:
            st.success(f"✅ 학습 완료! 오늘 활동 {study_units():.1f}단위 · 이제 확인 퀴즈로 이해도를 점검하세요.")

        # 이 레슨의 관련 퀴즈 목록
        all_quizzes = quizzes_for_track(track_id)
        related = [q for q in all_quizzes if q.lesson_id == lesson.id]
        if related:
            btn_label = f"이 레슨 확인 퀴즈 {len(related)}개 바로 풀기 →"
            if st.button(btn_label, type="primary", use_container_width=True):
                due_ids = set(lab_spaced_review_due_today())
                due_q = [q for q in all_quizzes if q.id in due_ids]
                other_q = [q for q in all_quizzes if q.id not in due_ids]
                ordered = due_q + other_q
                related_ids = {q.id for q in related}
                first_idx = next((i for i, q in enumerate(ordered) if q.id in related_ids), 0)
                st.session_state.lab_quiz_index = first_idx
                st.session_state.lab_lesson_just_completed = None
                go_to("확인 퀴즈")
        else:
            if st.button("확인 퀴즈 전체 이어가기 →", type="primary", use_container_width=True):
                st.session_state.lab_lesson_just_completed = None
                go_to("확인 퀴즈")

        # 관련 실습 바로 가기
        if lesson.related_practices:
            all_tasks = [t for t in PRACTICE_TASKS if t.track == track_id and t.status == "approved"]
            task_ids = [t.id for t in all_tasks]
            related_task_ids = [pid for pid in lesson.related_practices if pid in task_ids]
            if related_task_ids:
                st.markdown("**관련 실습 바로 가기**")
                for pid in related_task_ids:
                    task_idx = task_ids.index(pid)
                    task_title = all_tasks[task_idx].title
                    if st.button(f"실습: {task_title}", key=f"goto_practice_{pid}", use_container_width=True):
                        st.session_state.lab_practice_index = task_idx
                        st.session_state.lab_lesson_just_completed = None
                        go_to("실습하기")

    prev_col, next_col = st.columns(2)
    if prev_col.button("이전 카드", use_container_width=True, disabled=index == 0):
        prev_lesson = lessons[max(0, index - 1)]
        st.session_state.lab_lesson_index = next(
            (i for i, l in enumerate(all_lessons) if l.id == prev_lesson.id), 0
        )
        st.rerun()
    if next_col.button("다음 카드", use_container_width=True, disabled=index >= len(lessons) - 1):
        next_lesson = lessons[min(len(lessons) - 1, index + 1)]
        st.session_state.lab_lesson_index = next(
            (i for i, l in enumerate(all_lessons) if l.id == next_lesson.id), 0
        )
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

    # 오늘 복습 예정 퀴즈를 맨 앞에 배치
    due_ids = set(lab_spaced_review_due_today())
    due_quizzes = [q for q in quizzes if q.id in due_ids]
    other_quizzes = [q for q in quizzes if q.id not in due_ids]
    ordered_quizzes = due_quizzes + other_quizzes
    if due_quizzes:
        st.info(f"오늘 복습 예정 퀴즈 {len(due_quizzes)}개가 앞에 배치되었습니다.")

    index = min(st.session_state.lab_quiz_index, len(ordered_quizzes) - 1)
    quiz = ordered_quizzes[index]
    is_due = quiz.id in due_ids

    # 전체 퀴즈 진도 표시
    completed_quizzes = st.session_state.lab_completed_quizzes
    done_q = len([q for q in quizzes if q.id in completed_quizzes])
    st.progress(done_q / len(quizzes) if quizzes else 0, text=f"퀴즈 {done_q}/{len(quizzes)} 완료")

    with st.container(border=True):
        badge = "🔁 복습" if is_due else quiz.difficulty
        st.caption(f"{quiz.track} · {quiz.question_type} · {badge}")
        st.markdown(f"### 문제 {index + 1}/{len(ordered_quizzes)}")
        st.write(quiz.question)
        if quiz.question_type == "multiple_choice":
            answer = st.radio("답", quiz.options, key=f"lab_quiz_answer_{quiz.id}")
        else:
            answer = st.text_input("명령어 입력", key=f"lab_quiz_answer_{quiz.id}", placeholder="명령어를 입력하세요")
        source = doc_source_by_id(quiz.source_id)
        if source:
            st.markdown(f"출처: [{source.provider} · {source.title}]({source.url})")

    if st.button("정답 확인", type="primary", use_container_width=True):
        record_activity(track_id, "quiz", 1)
        correct, detail_tokens = evaluate_lab_quiz_detail(quiz, answer)

        if correct:
            st.session_state.lab_completed_quizzes.add(quiz.id)
            save_completed_items(
                st.session_state.lab_completed_lessons,
                st.session_state.lab_completed_quizzes,
                st.session_state.lab_completed_practices,
            )
            mark_learning_step(track_id, "quiz")
            st.success("정답입니다.")
        else:
            # command 타입: 토큰별 피드백
            if quiz.question_type == "command" and len(detail_tokens) > 1:
                parts_html = " ".join(
                    f'<span style="color:{"green" if ok else "red"};font-weight:bold">{tok}</span>'
                    for tok, ok in detail_tokens
                )
                st.error("오답입니다.")
                st.markdown(f"**정답 분석:** {parts_html} ", unsafe_allow_html=True)
                st.caption("초록색 = 입력됨 / 빨간색 = 누락 또는 오류")
            else:
                st.error(f"오답입니다. 정답: `{quiz.answer}`")

            # 오답노트 저장
            wrong_ids = {item["id"] for item in st.session_state.lab_wrong_notes}
            if quiz.id not in wrong_ids:
                st.session_state.lab_wrong_notes.append({
                    "id": quiz.id,
                    "item_type": "quiz",
                    "track": quiz.track,
                    "question": quiz.question,
                    "user_answer": str(answer),
                    "correct_answer": quiz.answer,
                    "explanation": quiz.explanation,
                })
                save_wrong_notes(st.session_state.lab_wrong_notes)

        # 간격 반복 갱신 (모든 퀴즈 타입)
        update_lab_spaced_review(quiz.id, correct)

        # DB 연동 (multiple_choice만)
        if quiz.question_type == "multiple_choice" and quiz.options:
            try:
                _db = SessionLocal()
                try:
                    from cert_study_app.models import Question as _Question
                    db_q = _db.query(_Question).filter(_Question.chunk_key == quiz.id).first()
                    if db_q:
                        try:
                            opts = list(quiz.options)
                            chosen_letter = chr(ord("A") + opts.index(str(answer))) if str(answer) in opts else None
                            if chosen_letter:
                                QuizService(_db).answer(db_q.id, chosen_letter, DEFAULT_USER)
                        except Exception:
                            pass
                        update_spaced_review(db_q.id, correct)
                finally:
                    _db.close()
            except Exception:
                pass

        st.markdown('<div class="answer-explanation">', unsafe_allow_html=True)
        st.markdown(quiz.explanation)
        st.markdown("</div>", unsafe_allow_html=True)

        # 관련 레슨 바로가기 (오답 시)
        if not correct and quiz.lesson_id:
            all_lessons = lessons_for_track(track_id)
            lesson_ids = [l.id for l in all_lessons]
            if quiz.lesson_id in lesson_ids:
                if st.button("이 레슨 다시 보기", key=f"goto_lesson_{quiz.id}"):
                    st.session_state.lab_lesson_index = lesson_ids.index(quiz.lesson_id)
                    go_to("이론 학습")

        # 다음 퀴즈 바로 이동 (설명 바로 아래)
        is_last = index >= len(ordered_quizzes) - 1
        if not is_last:
            if st.button("다음 퀴즈 →", type="primary", use_container_width=True, key=f"next_quiz_inline_{quiz.id}"):
                st.session_state.lab_quiz_index = index + 1
                st.rerun()
        else:
            st.info("마지막 퀴즈입니다. 처음으로 돌아가거나 홈에서 다음 단계로 이어가세요.")

    prev_col, next_col = st.columns(2)
    if prev_col.button("이전 퀴즈", use_container_width=True, disabled=index == 0):
        st.session_state.lab_quiz_index = max(0, index - 1)
        st.rerun()
    if next_col.button("다음 퀴즈", use_container_width=True, disabled=index >= len(ordered_quizzes) - 1):
        st.session_state.lab_quiz_index = min(len(ordered_quizzes) - 1, index + 1)
        st.rerun()


def _exam_elapsed_seconds(start_iso: str) -> int:
    try:
        start = datetime.fromisoformat(start_iso)
        return int((datetime.now() - start).total_seconds())
    except Exception:
        return 0


def render_exam_mode():
    st.subheader("시험 모드")
    session = st.session_state.get("exam_session")

    # ── 결과 화면 ─────────────────────────────────────────────────────────────
    if session and session.get("status") == "finished":
        answers = session.get("answers", [])
        total = len(answers)
        correct_count = sum(1 for a in answers if a.get("correct"))
        score = int(correct_count / total * 100) if total else 0
        elapsed = _exam_elapsed_seconds(session["start_time"])
        elapsed_str = f"{elapsed // 60}분 {elapsed % 60}초"

        pass_line = 70
        passed = score >= pass_line
        result_emoji = "합격" if passed else "불합격"
        st.markdown(f"## 모의시험 완료 — {result_emoji}")
        m1, m2, m3 = st.columns(3)
        m1.metric("점수", f"{score}점")
        m2.metric("정답", f"{correct_count}/{total}")
        m3.metric("소요 시간", elapsed_str)
        if passed:
            st.success(f"합격선({pass_line}점) 이상입니다.")
        else:
            st.warning(f"합격선({pass_line}점)에 {pass_line - score}점 부족합니다.")

        wrong_answers = [a for a in answers if not a.get("correct")]
        if wrong_answers:
            st.markdown(f"### 틀린 문제 ({len(wrong_answers)}개)")
            for i, a in enumerate(wrong_answers):
                with st.expander(f"Q{i+1}. {a['question'][:60]}"):
                    st.write(a["question"])
                    st.markdown(f"**내 답:** {a['user_answer']}")
                    st.markdown(f"**정답:** {a['correct_answer']}")
                    if a.get("explanation"):
                        st.info(a["explanation"])
                    # 오답노트에 저장
                    note_key = a.get("quiz_id", "")
                    wrong_ids = {n["id"] for n in st.session_state.lab_wrong_notes}
                    if note_key and note_key not in wrong_ids:
                        if st.button("오답노트에 추가", key=f"exam_wrong_{i}_{note_key}"):
                            st.session_state.lab_wrong_notes.append({
                                "id": note_key,
                                "item_type": "quiz",
                                "track": session.get("track", "linux"),
                                "question": a["question"],
                                "user_answer": a["user_answer"],
                                "correct_answer": a["correct_answer"],
                                "explanation": a.get("explanation", ""),
                            })
                            save_wrong_notes(st.session_state.lab_wrong_notes)
                            st.success("저장되었습니다.")

        if st.button("다시 시험", type="primary", use_container_width=True):
            st.session_state.exam_session = None
            st.rerun()
        return

    # ── 진행 중 화면 ──────────────────────────────────────────────────────────
    if session and session.get("status") == "running":
        questions = session["questions"]
        cur_idx = session["current_index"]
        duration_min = session["duration_minutes"]
        elapsed = _exam_elapsed_seconds(session["start_time"])
        remaining = max(0, duration_min * 60 - elapsed)
        remaining_str = f"{remaining // 60}분 {remaining % 60}초"

        progress_val = cur_idx / len(questions) if questions else 0
        st.progress(progress_val, text=f"문제 {cur_idx + 1}/{len(questions)}")

        time_col, _ = st.columns([1, 3])
        if remaining == 0:
            time_col.error("⏰ 시간 종료")
        else:
            time_col.info(f"⏱ 남은 시간: {remaining_str}")

        q = questions[cur_idx]
        with st.container(border=True):
            st.markdown(f"### Q{cur_idx + 1}. {q['question']}")
            if q["question_type"] == "multiple_choice":
                user_ans = st.radio("답 선택", q["options"], key=f"exam_q_{cur_idx}")
            else:
                user_ans = st.text_input("명령어 입력", key=f"exam_q_{cur_idx}", placeholder="명령어를 입력하세요")

        submit_disabled = remaining == 0 and cur_idx < len(questions) - 1
        btn_label = "제출 후 다음" if cur_idx < len(questions) - 1 else "제출 후 결과 보기"
        if st.button(btn_label, type="primary", use_container_width=True):
            from cert_study_app.services.learning_lab_service import LabQuiz
            fake_quiz = LabQuiz(
                id=q["quiz_id"],
                lesson_id=q.get("lesson_id", ""),
                track=session.get("track", "linux"),
                question_type=q["question_type"],
                question=q["question"],
                options=q.get("options", []),
                answer=q["answer"],
                explanation=q.get("explanation", ""),
            )
            correct = evaluate_lab_quiz(fake_quiz, str(user_ans))
            session["answers"].append({
                "quiz_id": q["quiz_id"],
                "question": q["question"],
                "user_answer": str(user_ans),
                "correct_answer": q["answer"],
                "correct": correct,
                "explanation": q.get("explanation", ""),
            })
            if cur_idx + 1 >= len(questions) or remaining == 0:
                session["status"] = "finished"
            else:
                session["current_index"] = cur_idx + 1
            st.rerun()
        return

    # ── 설정 화면 ─────────────────────────────────────────────────────────────
    st.caption("트랙과 문제 수, 제한 시간을 설정하고 시험을 시작합니다.")
    track_options = {t["name"]: t["id"] for t in active_tracks()}
    selected_track_name = st.selectbox("트랙", list(track_options.keys()))
    selected_track_id = track_options[selected_track_name]

    question_count = st.selectbox("문제 수", [5, 10, 20], index=1)
    duration_minutes = st.selectbox("제한 시간(분)", [10, 20, 40], index=1)
    difficulty_filter = st.multiselect("난이도", ["easy", "medium", "hard"], default=["easy", "medium", "hard"])

    all_quizzes = quizzes_for_track(selected_track_id)
    pool = [q for q in all_quizzes if q.difficulty in difficulty_filter]

    with st.container(border=True):
        st.write(f"- 트랙: **{selected_track_name}**")
        st.write(f"- 출제 가능: {len(pool)}문제 중 {min(question_count, len(pool))}문제 랜덤 출제")
        st.write(f"- 제한 시간: {duration_minutes}분")

    start_disabled = len(pool) == 0
    if start_disabled:
        st.warning("선택한 조건에 맞는 문제가 없습니다.")
    if st.button("시험 시작", type="primary", use_container_width=True, disabled=start_disabled):
        chosen = random.sample(pool, min(question_count, len(pool)))
        st.session_state.exam_session = {
            "status": "running",
            "track": selected_track_id,
            "questions": [
                {
                    "quiz_id": q.id,
                    "lesson_id": q.lesson_id,
                    "question_type": q.question_type,
                    "question": q.question,
                    "options": list(q.options),
                    "answer": q.answer,
                    "explanation": q.explanation,
                }
                for q in chosen
            ],
            "current_index": 0,
            "start_time": datetime.now().isoformat(),
            "duration_minutes": duration_minutes,
            "answers": [],
        }
        st.rerun()


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

    # 전체 실습 진도 표시
    completed_practices = st.session_state.lab_completed_practices
    done_p = len([t for t in tasks if t.id in completed_practices])
    st.progress(done_p / len(tasks) if tasks else 0, text=f"실습 {done_p}/{len(tasks)} 완료")

    with st.container(border=True):
        st.caption(f"{task.track} · {task.difficulty} · {task.status}")
        st.markdown(f"### {task.title}")
        st.write(task.task_description)
        command = st.text_input("터미널 입력", key=f"practice_command_{task.id}", placeholder=task.expected_command)
        with st.expander("힌트", expanded=False):
            st.write(task.hint)

    if st.button("실습 채점", type="primary", use_container_width=True):
        all_pass, condition_results = evaluate_practice_detail(task, command)
        if all_pass:
            st.session_state.lab_completed_practices.add(task.id)
            save_completed_items(
                st.session_state.lab_completed_lessons,
                st.session_state.lab_completed_quizzes,
                st.session_state.lab_completed_practices,
            )
            mark_learning_step(track_id, "apply")
            record_activity(track_id, "practice", 1)
            st.success(f"✅ 정답입니다. 오늘 활동 {study_units():.1f}단위")
            if task.takeaway:
                st.info(f"핵심 포인트: {task.takeaway}")
        else:
            st.error("아직 조건을 만족하지 못했습니다.")
            for cond, ok in condition_results:
                icon = "✅" if ok else "❌"
                st.markdown(f"{icon} `{cond}`")
        st.markdown('<div class="answer-explanation">', unsafe_allow_html=True)
        st.markdown(task.explanation)
        st.markdown("</div>", unsafe_allow_html=True)

        # 오답 시 관련 레슨 바로가기 (lesson.related_practices 역방향 매핑)
        if not all_pass:
            all_lessons = lessons_for_track(track_id)
            related_lessons = [l for l in all_lessons if task.id in l.related_practices]
            if related_lessons:
                lesson_ids = [l.id for l in all_lessons]
                matched = related_lessons[0]
                if st.button(f"관련 이론 다시 보기 — {matched.title}", key=f"goto_lesson_from_practice_{task.id}"):
                    st.session_state.lab_lesson_index = lesson_ids.index(matched.id)
                    go_to("이론 학습")

        # 채점 후 다음 실습 바로 이동
        is_last_task = index >= len(tasks) - 1
        if not is_last_task:
            if st.button("다음 실습 →", type="primary", use_container_width=True, key=f"next_practice_inline_{task.id}"):
                st.session_state.lab_practice_index = index + 1
                st.rerun()
        else:
            if all_pass:
                st.info("🎉 모든 실습을 완료했습니다! 홈에서 다음 단계(오답 복습)로 이어가세요.")

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
                result = service.answer(question["id"], chosen, DEFAULT_USER)
                st.session_state.last_result = result
                update_spaced_review(question["id"], result["correct"])
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
                result = service.answer(question["id"], chosen, DEFAULT_USER)
                st.session_state.last_result = result
                update_spaced_review(question["id"], result["correct"])
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


def render_vector_index():
    st.subheader("AI 색인")
    embedding_model = st.selectbox(
        "임베딩 모델",
        EMBEDDING_MODEL_OPTIONS,
        index=EMBEDDING_MODEL_OPTIONS.index(DEFAULT_EMBEDDING_MODEL)
        if DEFAULT_EMBEDDING_MODEL in EMBEDDING_MODEL_OPTIONS
        else 0,
        help="한국어 질문과 영어 공식 Docs를 같이 검색하려면 BAAI/bge-m3를 추천합니다.",
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
        st.markdown("#### 공식 Docs")
        source_options = docs_source_options()
        source_labels = [label for _, label in source_options]
        selected_label = st.selectbox("Docs 범위", source_labels)
        selected_track = source_options[source_labels.index(selected_label)][0]
        selected_track_id = None if selected_track == "all" else selected_track
        sources = active_docs_sources(selected_track_id)
        st.caption(f"선택된 공식 문서 {len(sources)}개")
        with st.expander("색인 대상 URL", expanded=False):
            for source in sources:
                st.markdown(f"- `{source.role}` · [{source.provider} · {source.title}]({source.url})")

        docs_service = OfficialDocsService(db, embedding_model=embedding_model, sources=sources)
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
            st.caption("아직 공식 Docs 색인이 없습니다.")
        st.caption("권장 주기: 분기 1회 · 시험 직전에는 수동 동기화를 한 번 실행하세요.")
        max_docs = max(1, len(sources))
        default_docs = min(12, max_docs)
        docs_limit = st.number_input("동기화할 Docs URL 수", min_value=1, max_value=max_docs, value=default_docs, step=1)
        if st.button("공식 Docs 벡터 색인", use_container_width=True):
            with st.spinner("공식 Docs를 가져와 Chroma에 색인하는 중입니다. 첫 실행은 모델 다운로드 때문에 오래 걸릴 수 있습니다."):
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


def learning_landing_routes():
    return {
        "개념공부": render_concept_mode_home,
        "개념 공부": render_concept_mode_home,
        "실습": render_practice_mode_home,
        "시험준비": render_exam_prep_home,
        "시험 준비": render_exam_prep_home,
    }


def main():
    ensure_runtime_dirs()
    init_db(verbose=False)
    db = SessionLocal()
    try:
        seed_demo_questions_if_empty(db)
        seed_concept_questions(db)
    finally:
        db.close()
    init_state()
    inject_pwa_assets()
    apply_mobile_styles()

    render_top_bar()
    exams = get_exams()
    page = st.session_state.page

    if page == "홈":
        render_home(exams)
        return

    render_back_home()
    if page == "개념공부":
        render_concept_mode_home()
        return
    if page == "실습":
        render_practice_mode_home()
        return
    if page == "시험준비":
        render_exam_prep_home(exams)
        return
    if page == "대시보드":
        render_dashboard(exams)
        return
    if page in {"Daily", "이어서 공부", "Daily Mode", "오늘 학습 세션"}:
        render_continue_study()
        return
    if page in {"Focus", "Focus Mode"}:
        render_focus_mode()
        return
    if page in {"Exam", "Exam Mode"}:
        render_exam_study_mode()
        return
    if page in learning_landing_routes():
        route = learning_landing_routes()[page]
        if page in {"시험준비", "시험 준비"}:
            route(exams)
        else:
            route()
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

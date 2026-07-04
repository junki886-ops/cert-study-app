import os
import re

import streamlit as st
import streamlit.components.v1 as components

from cert_study_app.config import DEFAULT_USER, ensure_runtime_dirs
from cert_study_app.db import SessionLocal
from cert_study_app.services.quiz_service import QuizService
from cert_study_app.services.learning_lab_service import (
    active_tracks,
    certification_for_track,
    certifications_for_track,
    normalize_track_id,
)
from cert_study_app.services.learning_progress_service import (
    load_completed_items,
    load_wrong_notes,
    preferred_track,
    save_preferred_track,
)

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


def go_to(page: str):
    st.session_state.page = page
    st.rerun()


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
        .cert-hero {
            background: linear-gradient(135deg, #1e40af 0%, #2563eb 60%, #3b82f6 100%);
            color: #fff;
            border-radius: 16px;
            padding: 1.1rem 1.25rem 0.9rem;
            margin-bottom: 0.5rem;
        }
        .cert-hero-track {
            font-size: 0.78rem;
            opacity: 0.8;
            margin-bottom: 0.15rem;
        }
        .cert-hero-streak {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .cert-hero-bar-wrap {
            background: rgba(255,255,255,0.25);
            border-radius: 999px;
            height: 6px;
            margin-bottom: 0.3rem;
        }
        .cert-hero-bar-fill {
            background: #fff;
            border-radius: 999px;
            height: 6px;
            transition: width 0.4s;
        }
        .cert-hero-bar-label {
            font-size: 0.78rem;
            opacity: 0.85;
        }
        .cert-stats-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
            margin: 0.5rem 0;
        }
        .cert-stat-card {
            border: 1px solid var(--cert-border);
            border-radius: 10px;
            padding: 0.6rem 0.7rem;
            text-align: center;
        }
        .cert-stat-card.alert {
            border-color: #f59e0b;
            background: rgba(245,158,11,0.07);
        }
        .cert-stat-value {
            font-size: 1.35rem;
            font-weight: 700;
            line-height: 1.1;
        }
        .cert-stat-label {
            font-size: 0.7rem;
            color: rgba(15,23,42,0.55);
            margin-top: 0.1rem;
        }
        .cert-chip {
            display: inline-block;
            font-size: 0.7rem;
            padding: 0.1rem 0.45rem;
            border-radius: 999px;
            font-weight: 600;
            vertical-align: middle;
        }
        .cert-chip-done {
            background: rgba(34,197,94,0.15);
            color: #16a34a;
        }
        div.answer-explanation {
            margin-top: 0.5rem;
            padding: 0.6rem 0.8rem;
            background: rgba(37,99,235,0.06);
            border-left: 3px solid #2563eb;
            border-radius: 0 6px 6px 0;
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


def render_back_home():
    if st.button("처음으로", use_container_width=True):
        go_to("홈")


def track_for_question_source(source):
    normalized = (source or "").strip().lower()
    if normalized.startswith("az-104") or "azure" in normalized:
        return "azure"
    if "linux" in normalized or "lfcs" in normalized:
        return "linux"
    return normalize_track_id(st.session_state.get("lab_track", "linux"))


def selected_lab_track() -> str:
    tracks = active_tracks()
    labels = []
    for track in tracks:
        certification_names = " / ".join(
            certification["name"] for certification in certifications_for_track(track["id"])
        )
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

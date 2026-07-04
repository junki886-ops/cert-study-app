from datetime import date

import streamlit as st
from sqlalchemy import func

from cert_study_app.config import DEFAULT_USER
from cert_study_app.db import SessionLocal
from cert_study_app.models import Attempt, Question
from cert_study_app.services.learning_lab_service import (
    PRACTICE_TASKS,
    active_tracks,
    certification_for_track,
    certifications_for_track,
    lessons_for_track,
    normalize_track_id,
    quizzes_for_track,
    track_by_id,
    track_progress,
)
from cert_study_app.services.learning_progress_service import (
    completed_steps,
    mark_learning_step,
    next_day_recommendation,
    save_preferred_track,
    spaced_review_count,
    spaced_review_due_today,
    streak_days,
    study_units,
    weekly_summary,
    record_activity,
)
from cert_study_app.services.question_concept_service import concept_label

from cert_study_app.ui.common import go_to, selected_lab_track


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


def render_home(exams):
    tracks = active_tracks()
    track_ids = [t["id"] for t in tracks]
    track_labels = [t["name"] for t in tracks]
    from cert_study_app.services.learning_progress_service import preferred_track
    current_track_id = normalize_track_id(st.session_state.get("lab_track", preferred_track()))
    current_idx = track_ids.index(current_track_id) if current_track_id in track_ids else 0
    selected_label = st.radio("", track_labels, index=current_idx, horizontal=True)
    track_id = track_ids[track_labels.index(selected_label)]
    if track_id != st.session_state.get("lab_track"):
        save_preferred_track(track_id)
        st.session_state.lab_track = track_id

    certification = certification_for_track(track_id)
    session_done = completed_steps(track_id)
    streak = streak_days()
    units = study_units()
    due_count = spaced_review_count()

    _, _, apply_action_label, apply_target = focus_apply_step(track_id)

    concept_done = {"lesson", "quiz"} <= session_done
    practice_done = "apply" in session_done
    review_done = "review" in session_done
    done_count = sum([concept_done, practice_done, review_done])
    all_done = done_count == 3

    if not concept_done:
        next_label = "개념 공부 시작하기 →" if "lesson" not in session_done else "확인 퀴즈 이어가기 →"
        next_page = "개념공부"
    elif not practice_done:
        next_label = f"{apply_action_label} →"
        next_page = "실습" if track_id != "azure" else "시험준비"
    elif not review_done:
        next_label = "오답 복습하기 →"
        next_page = "오답노트"
    else:
        next_label = "시험 문제 더 풀기 →"
        next_page = "시험준비"

    celebrate_key = f"_celebrated_{track_id}_{date.today().isoformat()}"
    if all_done and not st.session_state.get(celebrate_key):
        st.session_state[celebrate_key] = True
        st.balloons()

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

    if all_done:
        if st.button("🎉 오늘 완료! 추가 문제 더 풀기", type="primary", use_container_width=True):
            go_to("자격증 문제")
    else:
        if st.button(next_label, type="primary", use_container_width=True):
            if next_page == apply_target and track_id == "azure":
                st.session_state.exam_source = "AZ-104"
            go_to(next_page)

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
            <div class="cert-stat-card">
                <div class="cert-stat-value">{streak}</div>
                <div class="cert-stat-label">연속 학습일</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="cert-section-title">바로 가기</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    if col1.button("📖 개념 공부", use_container_width=True):
        go_to("개념공부")
    if col2.button("🖥 실습", use_container_width=True):
        go_to("실습")
    col3, col4 = st.columns(2)
    if col3.button("📋 시험 준비", use_container_width=True):
        go_to("시험준비")
    if col4.button("학습 현황", use_container_width=True):
        go_to("대시보드")

    render_spaced_review_panel()


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

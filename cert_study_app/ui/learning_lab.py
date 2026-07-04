import streamlit as st
from sqlalchemy import func

from cert_study_app.config import DEFAULT_USER
from cert_study_app.db import SessionLocal
from cert_study_app.models import Question
from cert_study_app.services.docs_source_service import doc_source_by_id
from cert_study_app.services.learning_lab_service import (
    PRACTICE_TASKS,
    active_tracks,
    certification_for_track,
    evaluate_lab_quiz_detail,
    evaluate_practice_detail,
    lessons_for_track,
    quizzes_for_track,
    roadmap_for_track,
    track_by_id,
    track_progress,
)
from cert_study_app.services.learning_progress_service import (
    lab_spaced_review_due_today,
    mark_learning_step,
    record_activity,
    save_completed_items,
    save_wrong_notes,
    study_units,
    update_lab_spaced_review,
    update_spaced_review,
)
from cert_study_app.services.quiz_service import QuizService
from cert_study_app.services.question_concept_service import concept_label

from cert_study_app.ui.common import go_to, selected_lab_track


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

    raw_index = st.session_state.lab_lesson_index
    index = min(raw_index, len(lessons) - 1)
    lesson = lessons[index]

    with st.container(border=True):
        _level_badge = {"입문": "🟢 입문", "중급": "🟡 중급", "고급": "🔴 고급"}.get(lesson.level, lesson.level)
        done_chip = "<span class='cert-chip cert-chip-done'>✓ 완료</span>" if lesson.id in completed_lessons else ""
        st.caption(_level_badge)
        st.markdown(f"### {done_chip} {lesson.title}", unsafe_allow_html=True)
        st.caption(f"카드 {index + 1}/{len(lessons)} · {lesson.track}")
        st.write(lesson.summary)
        if lesson.details:
            with st.expander("자세히 보기", expanded=False):
                for detail in lesson.details:
                    st.write(detail)
        if lesson.example:
            with st.expander("예시", expanded=False):
                st.code(lesson.example)
        if lesson.common_mistake:
            with st.expander("자주 틀리는 포인트", expanded=False):
                st.warning(lesson.common_mistake)
        if lesson.keywords:
            st.caption("키워드: " + " · ".join(lesson.keywords))

    if st.button("이 레슨 완료 체크", type="primary", use_container_width=True):
        st.session_state.lab_completed_lessons.add(lesson.id)
        save_completed_items(
            st.session_state.lab_completed_lessons,
            st.session_state.lab_completed_quizzes,
            st.session_state.lab_completed_practices,
        )
        mark_learning_step(track_id, "lesson")
        record_activity(track_id, "lesson", 1)
        st.session_state.lab_lesson_just_completed = lesson.id
        st.success(f"완료 체크! 오늘 활동 {study_units():.1f}단위")

    if st.session_state.get("lab_lesson_just_completed") == lesson.id and lesson.related_practices:
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
    if prev_col.button("이전 레슨", use_container_width=True, disabled=index == 0):
        st.session_state.lab_lesson_index = max(0, index - 1)
        st.rerun()
    if next_col.button("다음 레슨", use_container_width=True, disabled=index >= len(lessons) - 1):
        st.session_state.lab_lesson_index = min(len(lessons) - 1, index + 1)
        st.rerun()

    if index == len(lessons) - 1 and len(lessons) > 1:
        if st.button("확인 퀴즈로 이동", use_container_width=True):
            go_to("확인 퀴즈")


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

    due_ids = set(lab_spaced_review_due_today())
    due_quizzes = [q for q in quizzes if q.id in due_ids]
    other_quizzes = [q for q in quizzes if q.id not in due_ids]
    ordered_quizzes = due_quizzes + other_quizzes
    if due_quizzes:
        st.info(f"오늘 복습 예정 퀴즈 {len(due_quizzes)}개가 앞에 배치되었습니다.")

    index = min(st.session_state.lab_quiz_index, len(ordered_quizzes) - 1)
    quiz = ordered_quizzes[index]
    is_due = quiz.id in due_ids

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

        update_lab_spaced_review(quiz.id, correct)

        if quiz.question_type == "multiple_choice" and quiz.options:
            try:
                _db = SessionLocal()
                try:
                    db_q = _db.query(Question).filter(Question.chunk_key == quiz.id).first()
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

        if not correct and quiz.lesson_id:
            all_lessons = lessons_for_track(track_id)
            lesson_ids = [l.id for l in all_lessons]
            if quiz.lesson_id in lesson_ids:
                if st.button("이 레슨 다시 보기", key=f"goto_lesson_{quiz.id}"):
                    st.session_state.lab_lesson_index = lesson_ids.index(quiz.lesson_id)
                    go_to("이론 학습")

    prev_col, next_col = st.columns(2)
    if prev_col.button("이전 퀴즈", use_container_width=True, disabled=index == 0):
        st.session_state.lab_quiz_index = max(0, index - 1)
        st.rerun()
    if next_col.button("다음 퀴즈", use_container_width=True, disabled=index >= len(ordered_quizzes) - 1):
        st.session_state.lab_quiz_index = min(len(ordered_quizzes) - 1, index + 1)
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
            st.success(f"정답입니다. 오늘 활동 {study_units():.1f}단위")
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

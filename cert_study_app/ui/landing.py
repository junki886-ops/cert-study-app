import streamlit as st

from cert_study_app.services.learning_lab_service import (
    PRACTICE_TASKS,
    certification_for_track,
    lessons_for_track,
    quizzes_for_track,
    certifications_for_track,
    active_tracks,
    normalize_track_id,
)
from cert_study_app.services.learning_progress_service import (
    completed_steps,
    save_preferred_track,
    spaced_review_count,
    spaced_review_due_today,
)

from cert_study_app.ui.common import go_to, selected_lab_track


def render_concept_mode_home():
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
    st.subheader("📋 시험 준비")
    st.caption("덤프 문제로 실전 감각을 익히고, 틀린 문제는 간격 반복으로 완전히 내 것으로 만듭니다.")
    st.info("💡 여기는 **실제 시험 형식 문제 풀이** 공간입니다. 개념이 아직 익숙하지 않다면 '개념 공부'를 먼저 하세요.", icon=None)

    due_count = spaced_review_count()

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

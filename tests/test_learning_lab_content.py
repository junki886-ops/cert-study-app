from collections import Counter

from cert_study_app.services.docs_source_service import active_docs_sources, doc_source_by_id
from cert_study_app.services.learning_lab_service import PRACTICE_TASKS, lessons_for_track, quizzes_for_track


ACTIVE_TRACKS = ("linux", "azure", "tool_docs")


def test_learning_lab_content_has_no_duplicate_ids():
    lesson_ids = [lesson.id for track in ACTIVE_TRACKS for lesson in lessons_for_track(track)]
    quiz_ids = [quiz.id for track in ACTIVE_TRACKS for quiz in quizzes_for_track(track)]
    practice_ids = [task.id for task in PRACTICE_TASKS]

    assert [item_id for item_id, count in Counter(lesson_ids).items() if count > 1] == []
    assert [item_id for item_id, count in Counter(quiz_ids).items() if count > 1] == []
    assert [item_id for item_id, count in Counter(practice_ids).items() if count > 1] == []


def test_learning_lab_content_sources_are_registered():
    source_ids = {
        item.source_id
        for track in ACTIVE_TRACKS
        for item in [*lessons_for_track(track), *quizzes_for_track(track)]
    }

    assert sorted(source_id for source_id in source_ids if not doc_source_by_id(source_id)) == []


def test_learning_lab_quizzes_point_to_existing_lessons():
    lesson_ids = {lesson.id for track in ACTIVE_TRACKS for lesson in lessons_for_track(track)}

    assert sorted(
        quiz.lesson_id
        for track in ACTIVE_TRACKS
        for quiz in quizzes_for_track(track)
        if quiz.lesson_id not in lesson_ids
    ) == []


def test_learning_lab_has_exam_ready_content_volume():
    assert len(lessons_for_track("linux")) >= 50
    assert len(quizzes_for_track("linux")) >= 25
    assert len([task for task in PRACTICE_TASKS if task.track == "linux"]) >= 30

    assert len(lessons_for_track("azure")) >= 50
    assert len(quizzes_for_track("azure")) >= 25

    assert len(lessons_for_track("tool_docs")) >= 10
    assert len(quizzes_for_track("tool_docs")) >= 7


def test_docs_sources_cover_active_tracks():
    assert len(active_docs_sources("azure")) >= 20
    assert len(active_docs_sources("linux")) >= 10
    assert len(active_docs_sources("tool_docs")) >= 4

from cert_study_app.services.question_type_metadata_service import (
    is_ordered_answer_type,
    is_visual_question_type,
    normalize_question_type,
)


def test_normalize_question_type_aliases():
    assert normalize_question_type("Hotspot (True/False)") == "yes_no"
    assert normalize_question_type("True/False (In-Context)") == "yes_no"
    assert normalize_question_type("Hotspot (Drag and Drop)") == "matching"
    assert normalize_question_type("Multiple Select") == "multi_select"


def test_visual_question_type_detection_uses_normalized_type():
    assert is_visual_question_type("Hotspot (True/False)") is True
    assert is_visual_question_type("MCQ") is False


def test_ordered_answer_type_detection_uses_normalized_type():
    assert is_ordered_answer_type("Hotspot (Drag and Drop)") is True
    assert is_ordered_answer_type("Multiple Select") is False

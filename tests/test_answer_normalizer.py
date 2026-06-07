from cert_study_app.services.answer_normalizer import evaluate_answer, normalize_answer, yes_no_labels


def test_yes_no_labels_from_letters():
    assert yes_no_labels("Y,N,Y") == ["Y", "N", "Y"]


def test_yes_no_labels_from_words():
    assert yes_no_labels("Yes, No, Selected") == ["Y", "N", "Y"]


def test_yes_no_labels_from_structured_list():
    raw = [
        {"statement": "A", "selected_answer": "Yes"},
        {"statement": "B", "selected_answer": "No"},
        {"statement": "C", "selected_answer": "Yes"},
    ]
    assert yes_no_labels(raw) == ["Y", "N", "Y"]


def test_multi_choice_answer_is_sorted_when_unordered():
    assert normalize_answer("C,A") == "A,C"


def test_ordered_answer_preserves_order():
    assert normalize_answer("C,A", ordered=True) == "C,A"


def test_evaluate_answer_handles_yes_no_matrix():
    result = evaluate_answer("예, 아니오, 예", "Y,N,Y", ordered=True)
    assert result.correct is True
    assert result.normalized_chosen == "Y,N,Y"


def test_evaluate_answer_handles_unordered_multi_select():
    assert evaluate_answer("C,A", "A,C").correct is True

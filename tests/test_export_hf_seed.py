from pathlib import Path

from scripts.export_hf_seed import build_seed_report


def test_build_seed_report_flags_duplicates_and_missing_answer():
    rows = [
        {
            "question_number": 1,
            "question_type": "MCQ",
            "answer": "A",
            "options": ["A. One", "B. Two"],
            "parent_stem": "Common passage",
        },
        {
            "question_number": 1,
            "question_type": "Hotspot (True/False)",
            "answer": "",
            "options": [],
        },
    ]

    report = build_seed_report(rows, Path("cert_study_app/demo_data/questions_seed.json"))

    assert report["question_count"] == 2
    assert report["common_passage_count"] == 1
    assert report["duplicate_numbers"] == [1]
    assert report["missing_answers"] == [1]
    assert report["ready"] is False

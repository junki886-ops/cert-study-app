from __future__ import annotations

import subprocess
import sys


PYTHON_FILES = [
    "streamlit_app.py",
    "cert_study_app/services/answer_normalizer.py",
    "cert_study_app/services/demo_seed_service.py",
    "cert_study_app/services/parse_quality_service.py",
    "cert_study_app/services/question_review_service.py",
    "cert_study_app/services/question_type_metadata_service.py",
    "cert_study_app/services/quiz_service.py",
    "scripts/export_hf_seed.py",
]

TEST_FILES = [
    "tests/test_answer_normalizer.py",
    "tests/test_question_type_metadata_service.py",
    "tests/test_export_hf_seed.py",
]


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def main() -> int:
    run([sys.executable, "-m", "py_compile", *PYTHON_FILES])
    run([sys.executable, "-m", "pytest", *TEST_FILES])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


VISUAL_TYPES = {"hotspot", "yes_no", "ordering", "table_choice", "matching"}
ISSUE_WEIGHTS = {
    "missing_stem": 18,
    "short_stem": 8,
    "missing_answer": 10,
    "missing_options": 8,
    "option_label_gap": 8,
    "answer_not_in_options": 8,
    "duplicate_raw_text": 10,
    "number_gap": 12,
    "number_duplicate": 12,
    "page_regression": 10,
    "chunk_too_short": 8,
    "chunk_too_long": 6,
    "answer_leaked_to_stem": 8,
    "embedded_next_question": 14,
    "image_missing": 6,
}


def default_quality_report_path(output_json: str | Path) -> str:
    path = Path(output_json)
    return path.with_name(f"{path.stem}.quality.json").as_posix()


def load_parsed_questions(json_path: str | Path) -> list[dict[str, Any]]:
    with Path(json_path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        data = data["questions"]
    if not isinstance(data, list):
        raise ValueError("parsed JSON must be a list or an object with a questions list")
    return [item for item in data if isinstance(item, dict)]


def build_parse_quality_report(
    json_path: str | Path,
    *,
    output_path: str | Path | None = None,
    expected_count: int | None = None,
) -> dict[str, Any]:
    questions = load_parsed_questions(json_path)
    issues_by_index: dict[int, list[dict[str, Any]]] = defaultdict(list)

    numbers = [_as_int(_first_present(item, "number", "question_number")) for item in questions]
    pages = [_as_int(item.get("page")) for item in questions]
    raw_fingerprints: dict[str, list[int]] = defaultdict(list)
    chunk_lengths = []

    for index, item in enumerate(questions):
        raw_text = _text(item.get("raw_text") or item.get("ocr_text") or item.get("stem") or item.get("question"))
        stem = _text(item.get("stem") or item.get("question") or item.get("q_text"))
        answer = item.get("answer")
        options = _normal_options(item.get("options"))
        question_type = _text(item.get("question_type") or "mcq").lower()
        raw_fingerprints[_fingerprint(raw_text)].append(index)
        chunk_lengths.append(len(raw_text))

        if not stem:
            _add_issue(issues_by_index, index, "missing_stem", "문제 본문이 비어 있습니다.")
        elif len(stem) < 30:
            _add_issue(issues_by_index, index, "short_stem", "문제 본문이 너무 짧습니다.", length=len(stem))
        if not _has_answer(answer):
            _add_issue(issues_by_index, index, "missing_answer", "정답이 비어 있습니다.")
        if question_type not in VISUAL_TYPES and len(options) < 2:
            _add_issue(issues_by_index, index, "missing_options", "객관식/선택형으로 보이지만 보기가 2개 미만입니다.", option_count=len(options))
        if len(options) >= 2:
            expected_labels = [chr(ord("A") + offset) for offset in range(len(options))]
            labels = [label for label, _body in options]
            if labels != expected_labels:
                _add_issue(
                    issues_by_index,
                    index,
                    "option_label_gap",
                    "보기 라벨이 A부터 연속되지 않습니다.",
                    labels=labels,
                    expected=expected_labels,
                )
            if _answer_labels(answer) and not set(_answer_labels(answer)).issubset(set(labels)):
                _add_issue(
                    issues_by_index,
                    index,
                    "answer_not_in_options",
                    "정답 라벨이 보기 라벨 안에 없습니다.",
                    answer_labels=_answer_labels(answer),
                    option_labels=labels,
                )
        if re.search(r"(?im)^\s*(?:Answer|정답)\s*:", stem):
            _add_issue(issues_by_index, index, "answer_leaked_to_stem", "본문에 정답 라인이 섞여 있습니다.")
        if re.search(r"(?m)\n\s*\d{1,3}\s*[.)]\s+\S+", stem):
            _add_issue(issues_by_index, index, "embedded_next_question", "청크 안에 다음 문제 시작처럼 보이는 줄이 있습니다.")
        if question_type in VISUAL_TYPES and item.get("image_path") and not Path(str(item.get("image_path"))).exists():
            _add_issue(issues_by_index, index, "image_missing", "이미지 기반 문제의 원문 이미지 파일을 찾을 수 없습니다.")

    nonzero_numbers = [number for number in numbers if number is not None]
    duplicates = [number for number, count in Counter(nonzero_numbers).items() if count > 1]
    if duplicates:
        for index, number in enumerate(numbers):
            if number in duplicates:
                _add_issue(issues_by_index, index, "number_duplicate", "문제 번호가 중복되었습니다.", number=number)

    gaps = _number_gaps(nonzero_numbers)
    if gaps:
        gap_numbers = set()
        for start, end in gaps:
            gap_numbers.update({start - 1, end + 1})
        for index, number in enumerate(numbers):
            if number in gap_numbers:
                _add_issue(issues_by_index, index, "number_gap", "문제 번호 연속성이 깨진 지점 근처입니다.", gaps=gaps[:10])

    previous_page = None
    for index, page in enumerate(pages):
        if page is None:
            continue
        if previous_page is not None and page < previous_page:
            _add_issue(issues_by_index, index, "page_regression", "페이지 번호가 이전 문항보다 작습니다.", previous_page=previous_page, page=page)
        previous_page = page

    repeated_fingerprints = {fp: indexes for fp, indexes in raw_fingerprints.items() if fp and len(indexes) > 1}
    for indexes in repeated_fingerprints.values():
        for index in indexes:
            _add_issue(issues_by_index, index, "duplicate_raw_text", "같은 원문 청크가 중복 파싱되었습니다.", duplicate_indexes=indexes)

    length_stats = _length_stats(chunk_lengths)
    short_cutoff = 50
    long_cutoff = max(2500, int((length_stats.get("median") or 0) * 4))
    for index, length in enumerate(chunk_lengths):
        if length and length < short_cutoff:
            _add_issue(issues_by_index, index, "chunk_too_short", "원문 청크가 너무 짧습니다.", length=length)
        elif long_cutoff and length > long_cutoff:
            _add_issue(issues_by_index, index, "chunk_too_long", "원문 청크가 비정상적으로 깁니다.", length=length, cutoff=long_cutoff)

    issue_counts = Counter(issue["code"] for issues in issues_by_index.values() for issue in issues)
    total_penalty = sum(ISSUE_WEIGHTS.get(code, 5) * count for code, count in issue_counts.items())
    count_penalty = 0
    if expected_count is not None and expected_count >= 0:
        count_delta = abs(len(questions) - expected_count)
        count_penalty = min(20, count_delta * 2)
    score = max(0, min(100, 100 - total_penalty - count_penalty))

    samples = []
    for index, issues in sorted(issues_by_index.items(), key=lambda row: (-_issue_weight_sum(row[1]), row[0]))[:30]:
        item = questions[index]
        samples.append(
            {
                "index": index,
                "number": _first_present(item, "number", "question_number"),
                "page": item.get("page"),
                "question_type": item.get("question_type"),
                "issues": issues,
                "stem_preview": _preview(item.get("stem") or item.get("question") or ""),
                "raw_preview": _preview(item.get("raw_text") or item.get("ocr_text") or ""),
            }
        )

    report = {
        "schema_version": 1,
        "source_json": Path(json_path).as_posix(),
        "score": score,
        "status": _status_for_score(score, issue_counts),
        "question_count": len(questions),
        "expected_count": expected_count,
        "issue_counts": dict(sorted(issue_counts.items())),
        "question_issues": [
            {
                "index": index,
                "number": _first_present(questions[index], "number", "question_number"),
                "page": questions[index].get("page"),
                "issues": issues,
            }
            for index, issues in sorted(issues_by_index.items())
        ],
        "metrics": {
            "missing_answer": issue_counts.get("missing_answer", 0),
            "missing_options": issue_counts.get("missing_options", 0),
            "needs_review_estimate": len(issues_by_index),
            "numbers": {
                "first": min(nonzero_numbers) if nonzero_numbers else None,
                "last": max(nonzero_numbers) if nonzero_numbers else None,
                "duplicates": duplicates[:30],
                "gaps": gaps[:30],
            },
            "pages": {
                "first": next((page for page in pages if page is not None), None),
                "last": next((page for page in reversed(pages) if page is not None), None),
                "regressions": issue_counts.get("page_regression", 0),
            },
            "chunk_lengths": length_stats,
        },
        "samples": samples,
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def summarize_quality_report(report: dict[str, Any]) -> str:
    counts = report.get("issue_counts") or {}
    top = ", ".join(f"{key} {value}" for key, value in sorted(counts.items(), key=lambda row: (-row[1], row[0]))[:4])
    return f"품질 점수 {report.get('score', 0)}점 · {report.get('question_count', 0)}문항" + (f" · {top}" if top else "")


def _add_issue(target: dict[int, list[dict[str, Any]]], index: int, code: str, message: str, **details: Any) -> None:
    target[index].append({"code": code, "message": message, "severity": _severity(code), "details": details})


def _severity(code: str) -> str:
    weight = ISSUE_WEIGHTS.get(code, 5)
    if weight >= 12:
        return "high"
    if weight >= 8:
        return "medium"
    return "low"


def _issue_weight_sum(issues: list[dict[str, Any]]) -> int:
    return sum(ISSUE_WEIGHTS.get(str(issue.get("code")), 5) for issue in issues)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_present(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if item.get(key) not in {None, ""}:
            return item.get(key)
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _normal_options(raw: Any) -> list[tuple[str, str]]:
    if isinstance(raw, dict):
        rows = [(str(key).strip().upper(), str(value).strip()) for key, value in raw.items()]
    elif isinstance(raw, list):
        rows = []
        for index, value in enumerate(raw):
            text = str(value or "").strip()
            match = re.match(r"^([A-Za-z])[\.\)]\s*(.+)$", text, re.S)
            if match:
                rows.append((match.group(1).upper(), match.group(2).strip()))
            else:
                rows.append((chr(ord("A") + index), text))
    else:
        rows = []
    return [(label, body) for label, body in rows if label or body]


def _has_answer(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    text = str(value or "").strip()
    return bool(text and text not in {"[]", "{}"})


def _answer_labels(value: Any) -> list[str]:
    if isinstance(value, list):
        text = " ".join(str(item) for item in value)
    elif isinstance(value, dict):
        text = " ".join(str(item) for item in value.values())
    else:
        text = str(value or "")
    text = text.upper()
    if re.fullmatch(r"[A-H]{2,8}", text.strip()):
        return list(text.strip())
    labels = []
    for token in re.findall(r"\b[A-H]\b|\b[1-8]\b", text):
        labels.append(chr(ord("A") + int(token) - 1) if token.isdigit() else token)
    return labels


def _fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip().lower()
    if len(normalized) < 80:
        return ""
    return normalized[:500]


def _number_gaps(numbers: list[int]) -> list[tuple[int, int]]:
    if len(numbers) < 2:
        return []
    unique_sorted = sorted(set(numbers))
    gaps = []
    for previous, current in zip(unique_sorted, unique_sorted[1:]):
        if current > previous + 1:
            gaps.append((previous + 1, current - 1))
    return gaps


def _length_stats(lengths: list[int]) -> dict[str, Any]:
    if not lengths:
        return {"min": 0, "median": 0, "max": 0}
    return {"min": min(lengths), "median": int(median(lengths)), "max": max(lengths)}


def _preview(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _status_for_score(score: int, issue_counts: Counter) -> str:
    if issue_counts.get("number_gap") or issue_counts.get("embedded_next_question"):
        return "needs_chunk_review"
    if score >= 85:
        return "pass"
    if score >= 65:
        return "needs_sampling"
    return "needs_reparse"

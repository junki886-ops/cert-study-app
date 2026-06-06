from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cert_study_app.services.parse_quality_service import load_parsed_questions


BLOCKING_ISSUES = {
    "missing_stem",
    "number_duplicate",
    "embedded_next_question",
    "page_regression",
    "duplicate_raw_text",
}
REPARSE_ISSUES = {"number_gap", "embedded_next_question", "chunk_too_long", "duplicate_raw_text"}
REVIEW_ISSUES = {
    "short_stem",
    "missing_answer",
    "missing_options",
    "option_label_gap",
    "answer_not_in_options",
    "answer_leaked_to_stem",
    "chunk_too_short",
    "image_missing",
}


def default_gate_report_path(output_json: str | Path) -> str:
    path = Path(output_json)
    return path.with_name(f"{path.stem}.gate.json").as_posix()


def default_quarantine_path(output_json: str | Path) -> str:
    path = Path(output_json)
    return path.with_name(f"{path.stem}.quarantine.json").as_posix()


def apply_quality_gate(
    parsed_json_path: str | Path,
    quality_report: dict[str, Any],
    *,
    gate_report_path: str | Path | None = None,
    quarantine_path: str | Path | None = None,
    pass_score: int = 85,
    warn_score: int = 70,
) -> dict[str, Any]:
    questions = load_parsed_questions(parsed_json_path)
    issues_by_index = {
        int(row["index"]): row.get("issues") or []
        for row in quality_report.get("question_issues") or []
        if isinstance(row, dict) and str(row.get("index", "")).isdigit()
    }
    issue_counts = quality_report.get("issue_counts") or {}
    blocking_count = sum(int(issue_counts.get(code, 0) or 0) for code in BLOCKING_ISSUES)
    reparse_count = sum(int(issue_counts.get(code, 0) or 0) for code in REPARSE_ISSUES)
    score = int(quality_report.get("score") or 0)
    question_count = int(quality_report.get("question_count") or len(questions))

    if question_count <= 0:
        action = "hold"
        status = "empty"
        reason = "파싱된 문항이 없습니다."
    elif blocking_count:
        action = "hold"
        status = "reparse_needed"
        reason = "청킹/번호/중복 관련 차단 이슈가 있습니다."
    elif score >= pass_score:
        action = "proceed"
        status = "pass"
        reason = "자동 적재 가능한 품질입니다."
    elif score >= warn_score:
        action = "proceed_with_review"
        status = "warning"
        reason = "적재는 가능하지만 일부 문항은 자동 검수 대상으로 표시합니다."
    else:
        action = "hold"
        status = "low_quality"
        reason = "품질 점수가 낮아 DB 적재를 보류합니다."

    annotated = []
    status_counts: dict[str, int] = {}
    for index, item in enumerate(questions):
        row = dict(item)
        issues = issues_by_index.get(index, [])
        codes = [str(issue.get("code")) for issue in issues if isinstance(issue, dict)]
        if action == "hold":
            parse_status = "needs_reparse" if set(codes) & REPARSE_ISSUES else "needs_review"
            quality_status = "blocked"
        elif set(codes) & REPARSE_ISSUES:
            parse_status = "needs_reparse"
            quality_status = "reparse_candidate"
        elif set(codes) & REVIEW_ISSUES:
            parse_status = "needs_review"
            quality_status = "review"
        else:
            parse_status = row.get("parse_status") or "draft"
            quality_status = "pass"

        row["parse_status"] = parse_status
        row["quality_status"] = quality_status
        row["quality_issues"] = issues
        row["quality_score"] = score
        annotated.append(row)
        status_counts[quality_status] = status_counts.get(quality_status, 0) + 1

    Path(parsed_json_path).write_text(json.dumps(annotated, ensure_ascii=False, indent=2), encoding="utf-8")

    quarantine = None
    if action == "hold":
        quarantine = str(quarantine_path or default_quarantine_path(parsed_json_path))
        Path(quarantine).parent.mkdir(parents=True, exist_ok=True)
        Path(quarantine).write_text(json.dumps(annotated, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = {
        "schema_version": 1,
        "source_json": Path(parsed_json_path).as_posix(),
        "action": action,
        "status": status,
        "reason": reason,
        "score": score,
        "pass_score": pass_score,
        "warn_score": warn_score,
        "question_count": question_count,
        "blocking_count": blocking_count,
        "reparse_count": reparse_count,
        "status_counts": status_counts,
        "quarantine_json": quarantine,
        "llm_review_policy": {
            "enabled_by_default": False,
            "recommended_only_for": sorted(REPARSE_ISSUES | {"answer_not_in_options", "missing_answer"}),
        },
    }

    if gate_report_path:
        Path(gate_report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(gate_report_path).write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    return gate


def summarize_quality_gate(gate: dict[str, Any]) -> str:
    return (
        f"품질 게이트 {gate.get('status')} · {gate.get('action')} · "
        f"차단 {gate.get('blocking_count', 0)}개 · 재파싱 후보 {gate.get('reparse_count', 0)}개"
    )

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_JSON = ROOT / "data" / "Json" / "questions.json"
DEFAULT_PARENT_SOURCE_JSON = ROOT / "data" / "parsed_json" / "reparsed_multipage_images_20260601_205501.json"
DEFAULT_IMAGE_ROOT = ROOT / "data" / "images"
DEFAULT_SEED_PATH = ROOT / "cert_study_app" / "demo_data" / "questions_seed.json"
DEFAULT_ASSET_ROOT = ROOT / "static" / "question_assets"
DEFAULT_REPORT_PATH = ROOT / "cert_study_app" / "demo_data" / "questions_seed.report.json"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, dict):
        payload = payload.get("questions", [])
    return [row for row in payload if isinstance(row, dict)]


def _option_text(option: Any, fallback_key: str) -> str:
    if isinstance(option, dict):
        key = str(option.get("key") or fallback_key).strip()
        text = str(option.get("text") or option.get("value") or "").strip()
        return f"{key}. {text}".strip()
    return str(option).strip()


def _normalize_options(options: Any) -> list[str] | dict[str, str]:
    if isinstance(options, list):
        normalized = []
        for index, option in enumerate(options):
            normalized.append(_option_text(option, chr(65 + index)))
        return normalized
    if isinstance(options, dict):
        return {str(key): str(value) for key, value in options.items()}
    return []


def _first_existing_page_image(source_pages: list[Any], image_root: Path) -> Path | None:
    for page in source_pages:
        try:
            page_number = int(page)
        except Exception:
            continue
        matches = sorted(image_root.glob(f"*/page_{page_number}.jpg"))
        if matches:
            return matches[0]
    return None


def _copy_image(source_path: Path, asset_root: Path) -> str:
    relative_parent = source_path.parent.name
    target_dir = asset_root / relative_parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    if not target_path.exists() or source_path.stat().st_size != target_path.stat().st_size:
        shutil.copy2(source_path, target_path)
    return target_path.relative_to(ROOT).as_posix()


def _copy_image_reference(image_path: Any, asset_root: Path) -> str | None:
    if not image_path:
        return None
    source_path = Path(str(image_path))
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    if not source_path.exists():
        return str(image_path)
    return _copy_image(source_path, asset_root)


def _asset_exists(path: Any) -> bool:
    if not path:
        return False
    asset_path = Path(str(path))
    if not asset_path.is_absolute():
        asset_path = ROOT / asset_path
    return asset_path.exists()


def _question_number(row: dict[str, Any]) -> Any:
    return row.get("question_number") or row.get("question_id") or row.get("number")


def _parent_context_by_number(parent_rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    contexts = {}
    for row in parent_rows:
        number = _question_number(row)
        try:
            number = int(number)
        except Exception:
            continue
        if not row.get("parent_stem"):
            continue
        contexts[number] = row
    return contexts


def _parent_context_by_scenario(
    rows: list[dict[str, Any]], parent_contexts: dict[int, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    contexts = {}
    for row in rows:
        scenario = row.get("scenario")
        if not scenario or scenario == "단일문제" or scenario in contexts:
            continue
        try:
            number = int(_question_number(row))
        except Exception:
            continue
        parent_context = parent_contexts.get(number)
        if parent_context:
            contexts[str(scenario)] = parent_context
    return contexts


def _meaningful_parent_stem(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text == "단일문제":
        return None
    if len(text) < 40 and not re.search(r"[\n:]", text):
        return None
    return text


def _export_row(
    row: dict[str, Any],
    image_root: Path,
    asset_root: Path,
    parent_contexts: dict[int, dict[str, Any]],
    scenario_contexts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_pages = row.get("source_pages") or []
    if not isinstance(source_pages, list):
        source_pages = [source_pages]

    image_path = _copy_image_reference(row.get("image_path"), asset_root)
    if not image_path:
        source_image = _first_existing_page_image(source_pages, image_root)
        if source_image:
            image_path = _copy_image(source_image, asset_root)

    question_number = _question_number(row)
    page = source_pages[0] if source_pages else row.get("page")
    try:
        parent_context = parent_contexts.get(int(question_number)) or {}
    except Exception:
        parent_context = {}
    if not parent_context and row.get("scenario"):
        parent_context = scenario_contexts.get(str(row.get("scenario"))) or {}

    parent_image_paths = []
    for parent_image_path in parent_context.get("parent_image_paths") or row.get("parent_image_paths") or []:
        copied_path = _copy_image_reference(parent_image_path, asset_root)
        if copied_path:
            parent_image_paths.append(copied_path)

    parent_stem = (
        _meaningful_parent_stem(parent_context.get("parent_stem"))
        or _meaningful_parent_stem(row.get("parent_stem"))
    )

    return {
        "question_number": question_number,
        "stem": row.get("stem") or row.get("question") or "",
        "options": _normalize_options(row.get("options")),
        "answer": row.get("answer"),
        "explanation": row.get("explanation"),
        "question_type": row.get("question_type") or "MCQ",
        "category": row.get("category"),
        "subcategory": row.get("subcategory"),
        "source": row.get("source") or "AZ-104 imported seed",
        "page": page,
        "image_path": image_path,
        "raw_text": row.get("raw_text") or row.get("stem") or row.get("question") or "",
        "group_id": parent_context.get("group_id") or row.get("group_id"),
        "parent_stem": parent_stem,
        "parent_image_paths": parent_image_paths,
        "concept_tags": row.get("concept_tags") or [],
        "parse_status": row.get("parse_status") or "approved",
        "quality_score": row.get("quality_score") or 100,
        "quality_status": row.get("quality_status") or "seed",
        "quality_issues": row.get("quality_issues") or [],
        "chunk_key": row.get("chunk_key"),
        "chunk_index": row.get("chunk_index"),
        "parser_version": row.get("parser_version") or "hf-seed-export-v1",
        "source_pages": source_pages,
}


def export_seed(
    source_json: Path,
    parent_source_json: Path,
    image_root: Path,
    seed_path: Path,
    asset_root: Path,
    report_path: Path | None = DEFAULT_REPORT_PATH,
) -> int:
    rows = _load_rows(source_json)
    parent_rows = _load_rows(parent_source_json) if parent_source_json.exists() else []
    parent_contexts = _parent_context_by_number(parent_rows)
    scenario_contexts = _parent_context_by_scenario(rows, parent_contexts)
    asset_root.mkdir(parents=True, exist_ok=True)
    seed_path.parent.mkdir(parents=True, exist_ok=True)

    exported = [
        _export_row(row, image_root, asset_root, parent_contexts, scenario_contexts)
        for row in rows
    ]
    with seed_path.open("w", encoding="utf-8") as file:
        json.dump(exported, file, ensure_ascii=False, indent=2)
        file.write("\n")
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as file:
            json.dump(build_seed_report(exported, seed_path), file, ensure_ascii=False, indent=2)
            file.write("\n")
    return len(exported)


def build_seed_report(rows: list[dict[str, Any]], seed_path: Path) -> dict[str, Any]:
    numbers = []
    duplicate_numbers = []
    seen_numbers = set()
    type_counts: dict[str, int] = {}
    missing_images = []
    missing_answers = []
    missing_options = []
    common_passage_count = 0

    for row in rows:
        number = row.get("question_number")
        if number in seen_numbers:
            duplicate_numbers.append(number)
        seen_numbers.add(number)
        numbers.append(number)
        question_type = str(row.get("question_type") or "unparsed")
        type_counts[question_type] = type_counts.get(question_type, 0) + 1
        if row.get("parent_stem"):
            common_passage_count += 1
        if not row.get("answer"):
            missing_answers.append(number)
        if not row.get("options"):
            missing_options.append(number)
        image_paths = [row.get("image_path")] + list(row.get("parent_image_paths") or [])
        for image_path in image_paths:
            if image_path and not _asset_exists(image_path):
                missing_images.append({"question_number": number, "image_path": image_path})

    numeric_numbers = []
    for number in numbers:
        try:
            numeric_numbers.append(int(number))
        except Exception:
            continue

    return {
        "schema_version": 1,
        "seed_path": _display_path(seed_path),
        "question_count": len(rows),
        "first_question_number": min(numeric_numbers) if numeric_numbers else None,
        "last_question_number": max(numeric_numbers) if numeric_numbers else None,
        "common_passage_count": common_passage_count,
        "type_counts": dict(sorted(type_counts.items())),
        "duplicate_numbers": duplicate_numbers,
        "missing_answers": missing_answers,
        "missing_options": missing_options,
        "missing_images": missing_images,
        "ready": not duplicate_numbers and not missing_answers and not missing_images,
    }


def _display_path(path: Path) -> str:
    try:
        resolved = path.resolve()
        return resolved.relative_to(ROOT).as_posix()
    except Exception:
        return path.as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deployable question seed data for Hugging Face Space.")
    parser.add_argument("--source-json", type=Path, default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--parent-source-json", type=Path, default=DEFAULT_PARENT_SOURCE_JSON)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--seed-path", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--asset-root", type=Path, default=DEFAULT_ASSET_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()

    count = export_seed(
        source_json=args.source_json,
        parent_source_json=args.parent_source_json,
        image_root=args.image_root,
        seed_path=args.seed_path,
        asset_root=args.asset_root,
        report_path=args.report_path,
    )
    print(f"Exported {count} questions to {args.seed_path}")
    print(f"Wrote seed report to {args.report_path}")


if __name__ == "__main__":
    main()

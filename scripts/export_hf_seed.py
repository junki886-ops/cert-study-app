from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_JSON = ROOT / "data" / "Json" / "questions.json"
DEFAULT_IMAGE_ROOT = ROOT / "data" / "images"
DEFAULT_SEED_PATH = ROOT / "cert_study_app" / "demo_data" / "questions_seed.json"
DEFAULT_ASSET_ROOT = ROOT / "static" / "question_assets"


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


def _export_row(row: dict[str, Any], image_root: Path, asset_root: Path) -> dict[str, Any]:
    source_pages = row.get("source_pages") or []
    if not isinstance(source_pages, list):
        source_pages = [source_pages]

    image_path = row.get("image_path")
    if not image_path:
        source_image = _first_existing_page_image(source_pages, image_root)
        if source_image:
            image_path = _copy_image(source_image, asset_root)

    question_number = row.get("question_number") or row.get("question_id") or row.get("number")
    page = source_pages[0] if source_pages else row.get("page")

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
        "parent_stem": row.get("parent_stem") or row.get("scenario"),
        "parent_image_paths": row.get("parent_image_paths") or [],
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


def export_seed(source_json: Path, image_root: Path, seed_path: Path, asset_root: Path) -> int:
    rows = _load_rows(source_json)
    asset_root.mkdir(parents=True, exist_ok=True)
    seed_path.parent.mkdir(parents=True, exist_ok=True)

    exported = [_export_row(row, image_root, asset_root) for row in rows]
    with seed_path.open("w", encoding="utf-8") as file:
        json.dump(exported, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return len(exported)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deployable question seed data for Hugging Face Space.")
    parser.add_argument("--source-json", type=Path, default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--seed-path", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--asset-root", type=Path, default=DEFAULT_ASSET_ROOT)
    args = parser.parse_args()

    count = export_seed(
        source_json=args.source_json,
        image_root=args.image_root,
        seed_path=args.seed_path,
        asset_root=args.asset_root,
    )
    print(f"Exported {count} questions to {args.seed_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PIL import Image

from cert_study_app.db import SessionLocal, init_db
from cert_study_app.models import Question


def backfill_question_images(
    page_image_dir: str = "data/images/AZ-104_dump_ad31e61b",
    output_dir: str = "data/question_images/AZ-104_dump_ad31e61b",
) -> int:
    init_db(verbose=False)
    db = SessionLocal()
    page_dir = Path(page_image_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    updated = 0
    try:
        questions = db.query(Question).order_by(Question.page.asc(), Question.id.asc()).all()
        by_page = defaultdict(list)
        for question in questions:
            if question.page:
                by_page[question.page].append(question)

        for page, page_questions in by_page.items():
            page_image = page_dir / f"page_{page}.jpg"
            if not page_image.exists():
                continue

            with Image.open(page_image) as img:
                width, height = img.size
                count = len(page_questions)
                for index, question in enumerate(page_questions):
                    top = max(0, int(height * index / count) - 80)
                    bottom = min(height, int(height * (index + 1) / count) + 80)
                    crop = img.crop((0, top, width, bottom))
                    crop_path = out_dir / f"q_{question.id}_page_{page}.jpg"
                    crop.save(crop_path, "JPEG", quality=88)
                    question.image_path = crop_path.as_posix()
                    updated += 1

        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print(backfill_question_images())

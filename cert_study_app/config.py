import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PARSED_DIR = DATA_DIR / "parsed_json"
IMAGE_DIR = DATA_DIR / "images"
OCR_LOG_DIR = DATA_DIR / "ocr_logs"
RUN_LOG_DIR = DATA_DIR / "run_logs"

DB_PATH = DATA_DIR / "questions.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL

DEFAULT_USER = "default"


def ensure_runtime_dirs() -> None:
    for path in [DATA_DIR, UPLOAD_DIR, PARSED_DIR, IMAGE_DIR, OCR_LOG_DIR, RUN_LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)

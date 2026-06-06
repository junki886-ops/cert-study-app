import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from cert_study_app.config import DATABASE_URL, DB_PATH, DEFAULT_DATABASE_URL, ensure_runtime_dirs


ensure_runtime_dirs()

_active_database_url = DATABASE_URL


def _make_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(
        database_url,
        connect_args=connect_args,
        echo=False,
        future=True,
    )


def _is_connection_error(exc: SQLAlchemyError) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in [
            "connection refused",
            "can't create a connection",
            "could not connect",
            "connection timed out",
            "network is unreachable",
        ]
    )


engine = _make_engine(_active_database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db(verbose: bool = True) -> None:
    from cert_study_app.models import Attempt, AzureDocsSync, ConceptNote, IngestionJob, Question  # noqa: F401

    global engine, _active_database_url

    try:
        Base.metadata.create_all(bind=engine)
        _ensure_lightweight_columns(verbose=verbose)
    except SQLAlchemyError as exc:
        fallback_enabled = os.getenv("CERT_STUDY_DB_FALLBACK", "0") == "1"
        if _active_database_url.startswith("sqlite") or not fallback_enabled or not _is_connection_error(exc):
            raise
        engine = _make_engine(DEFAULT_DATABASE_URL)
        SessionLocal.configure(bind=engine)
        _active_database_url = DEFAULT_DATABASE_URL
        Base.metadata.create_all(bind=engine)
        _ensure_lightweight_columns(verbose=verbose)
        if verbose:
            print(f"[WARN] Primary DB unavailable, using SQLite fallback: {exc}")

    if not verbose:
        return

    target = DB_PATH if _active_database_url.startswith("sqlite") else _active_database_url
    print(f"\n[INFO] Database Initialized: {target}")
    print("-" * 46)


def _ensure_lightweight_columns(verbose: bool = True) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "questions" in tables:
        _add_missing_columns(
            "questions",
            {
                "image_path": "ALTER TABLE questions ADD COLUMN image_path VARCHAR(500)",
                "raw_text": "ALTER TABLE questions ADD COLUMN raw_text TEXT",
                "structured_data_json": "ALTER TABLE questions ADD COLUMN structured_data_json TEXT",
                "parse_status": "ALTER TABLE questions ADD COLUMN parse_status VARCHAR(30)",
                "quality_score": "ALTER TABLE questions ADD COLUMN quality_score INTEGER",
                "quality_status": "ALTER TABLE questions ADD COLUMN quality_status VARCHAR(50)",
                "quality_issues": "ALTER TABLE questions ADD COLUMN quality_issues TEXT",
                "chunk_key": "ALTER TABLE questions ADD COLUMN chunk_key VARCHAR(80)",
                "chunk_index": "ALTER TABLE questions ADD COLUMN chunk_index INTEGER",
                "parser_version": "ALTER TABLE questions ADD COLUMN parser_version VARCHAR(50)",
                "review_note": "ALTER TABLE questions ADD COLUMN review_note TEXT",
                "question_number": "ALTER TABLE questions ADD COLUMN question_number INTEGER",
                "group_id": "ALTER TABLE questions ADD COLUMN group_id VARCHAR(100)",
                "parent_stem": "ALTER TABLE questions ADD COLUMN parent_stem TEXT",
                "parent_image_paths": "ALTER TABLE questions ADD COLUMN parent_image_paths TEXT",
                "concept_tags": "ALTER TABLE questions ADD COLUMN concept_tags TEXT",
                "review_score": "ALTER TABLE questions ADD COLUMN review_score INTEGER",
                "review_issues": "ALTER TABLE questions ADD COLUMN review_issues TEXT",
                "visual_analysis_json": "ALTER TABLE questions ADD COLUMN visual_analysis_json TEXT",
                "visual_reviewed_at": "ALTER TABLE questions ADD COLUMN visual_reviewed_at DATETIME",
                "reviewed_at": "ALTER TABLE questions ADD COLUMN reviewed_at DATETIME",
                "auto_reviewed_at": "ALTER TABLE questions ADD COLUMN auto_reviewed_at DATETIME",
            },
        )
    if verbose:
        _print_schema()
    if "ingestion_jobs" in tables:
        _add_missing_columns(
            "ingestion_jobs",
            {
                "auto_visual_analysis": "ALTER TABLE ingestion_jobs ADD COLUMN auto_visual_analysis BOOLEAN DEFAULT 1",
                "visual_batch_size": "ALTER TABLE ingestion_jobs ADD COLUMN visual_batch_size INTEGER DEFAULT 5",
                "quality_score": "ALTER TABLE ingestion_jobs ADD COLUMN quality_score INTEGER",
                "quality_status": "ALTER TABLE ingestion_jobs ADD COLUMN quality_status VARCHAR(50)",
                "quality_report_json": "ALTER TABLE ingestion_jobs ADD COLUMN quality_report_json VARCHAR(500)",
                "quality_gate_json": "ALTER TABLE ingestion_jobs ADD COLUMN quality_gate_json VARCHAR(500)",
            },
        )


def _add_missing_columns(table_name: str, ddl_by_column: dict[str, str]) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    for name, ddl in ddl_by_column.items():
        if name not in columns:
            with engine.begin() as conn:
                conn.execute(text(ddl))


def _print_schema() -> None:
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        print(f"\nTable: {table}")
        for col in inspector.get_columns(table):
            print(f"  - {col['name']:<18} {str(col['type'])}")
    print("-" * 46)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

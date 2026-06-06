from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, inspect, select, text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cert_study_app.config import DB_PATH
from cert_study_app.db import Base
from cert_study_app.models import Attempt, ConceptNote, IngestionJob, Question  # noqa: F401


DEFAULT_TARGET_URL = "postgresql+pg8000://cert_study:cert_study@localhost:5432/cert_study"


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.expanduser().resolve().as_posix()}"


def table_exists(engine, table_name: str) -> bool:
    return table_name in inspect(engine).get_table_names()


def reset_postgres_sequence(conn, table_name: str, pk_name: str) -> None:
    sequence = conn.execute(
        text("SELECT pg_get_serial_sequence(:table_name, :pk_name)"),
        {"table_name": table_name, "pk_name": pk_name},
    ).scalar()
    if not sequence:
        return
    max_id = conn.execute(text(f'SELECT COALESCE(MAX("{pk_name}"), 0) FROM "{table_name}"')).scalar()
    conn.execute(text("SELECT setval(:sequence, :value, :called)"), {"sequence": sequence, "value": max_id or 1, "called": bool(max_id)})


def migrate(source_path: Path, target_url: str, replace: bool = False) -> dict:
    source_engine = create_engine(sqlite_url(source_path), future=True)
    target_engine = create_engine(target_url, future=True)

    if replace:
        Base.metadata.drop_all(bind=target_engine)
    Base.metadata.create_all(bind=target_engine)

    source_meta = MetaData()
    source_meta.reflect(bind=source_engine)

    summary = {}
    with target_engine.begin() as target_conn:
        with source_engine.connect() as source_conn:
            for table in Base.metadata.sorted_tables:
                source_table = source_meta.tables.get(table.name)
                if source_table is None:
                    continue

                source_columns = {column.name for column in source_table.columns}
                target_columns = [column.name for column in table.columns if column.name in source_columns]
                rows = [
                    {column: row._mapping[column] for column in target_columns}
                    for row in source_conn.execute(select(*[source_table.c[column] for column in target_columns]))
                ]
                if rows:
                    target_conn.execute(table.insert(), rows)
                summary[table.name] = len(rows)

        for table in Base.metadata.sorted_tables:
            pk_columns = list(table.primary_key.columns)
            if len(pk_columns) == 1 and target_url.startswith("postgres"):
                reset_postgres_sequence(target_conn, table.name, pk_columns[0].name)

    with target_engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            if table_exists(target_engine, table.name):
                summary[f"{table.name}_target_count"] = conn.execute(select(func.count()).select_from(table)).scalar()

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate cert-study SQLite data to PostgreSQL.")
    parser.add_argument("--source", default=str(DB_PATH), help="SQLite DB path. Default: data/questions.db")
    parser.add_argument("--target", default=os.getenv("DATABASE_URL") or DEFAULT_TARGET_URL, help="PostgreSQL SQLAlchemy URL.")
    parser.add_argument("--replace", action="store_true", help="Delete target table rows before copying.")
    args = parser.parse_args()

    summary = migrate(Path(args.source), args.target, replace=args.replace)
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

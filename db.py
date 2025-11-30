# ==============================================
# db.py (v2025-final)
# ==============================================

import os
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

# ----------------------------------------------
# 경로 설정
# ----------------------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "questions.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# ----------------------------------------------
# SQLAlchemy Engine
# ----------------------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,   # 필요하면 .env 로 True/False 변경 가능
    future=True
)

# ----------------------------------------------
# Session
# ----------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ----------------------------------------------
# Base (ORM 공통)
# ----------------------------------------------
Base = declarative_base()

# ----------------------------------------------
# DB 초기화
# ----------------------------------------------
def init_db():
    from models import Question, Attempt  # Base 로 묶인 모델 불러오기
    Base.metadata.create_all(bind=engine)

    print(f"\n[INFO] ✅ Database Initialized: {DB_PATH}")
    print("──────────────────────────────────────────────")

    inspector = inspect(engine)
    for table in inspector.get_table_names():
        print(f"\n📘 Table: {table}")
        for col in inspector.get_columns(table):
            print(f"  • {col['name']:<18} {str(col['type'])}")

    print("──────────────────────────────────────────────\n")

# ----------------------------------------------
# 요청 단위 DB 세션
# ----------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================================
# db.py
# ==============================================

import os
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

# ----------------------------------------------
# 1. 경로 및 DB 설정
# ----------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "questions.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# ----------------------------------------------
# 2. SQLAlchemy Engine 생성
# ----------------------------------------------
# check_same_thread=False: SQLite를 멀티 스레드 환경(FastAPI 등)에서 쓸 때 필수
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # SQL 로그가 필요하면 True로 변경
    future=True
)

# ----------------------------------------------
# 3. Session 설정
# ----------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ----------------------------------------------
# 4. Base 모델 (ORM 공통 부모)
# ----------------------------------------------
Base = declarative_base()

# ----------------------------------------------
# 5. DB 초기화 함수 (테이블 생성 및 확인)
# ----------------------------------------------
def init_db():
    # 모델들을 여기서 import 해야 Base.metadata에 등록됨
    # (순환 참조 방지를 위해 함수 내부 import 권장)
    from models import Question, Attempt 
    
    # 테이블 생성 (이미 있으면 무시함)
    Base.metadata.create_all(bind=engine)

    print(f"\n[INFO] ✅ Database Connected: {DB_PATH}")
    print("──────────────────────────────────────────────")

    # 생성된 테이블 구조 확인 (디버깅용)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    if not table_names:
        print("⚠️  No tables found. Did you define classes in models.py?")
    
    for table in table_names:
        print(f"📘 Table: {table}")
        for col in inspector.get_columns(table):
            # 컬럼명, 타입 출력
            print(f"  • {col['name']:<15} {str(col['type'])}")
    
    print("──────────────────────────────────────────────\n")

# ----------------------------------------------
# 6. Dependency (FastAPI 등에서 사용)
# ----------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
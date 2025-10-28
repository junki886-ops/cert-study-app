from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# -----------------------
# DB 설정
# -----------------------
# data/questions.db 파일을 SQLite 데이터베이스로 사용
DATABASE_URL = "sqlite:///./data/questions.db"

# SQLite 전용 옵션 (스레드 충돌 방지)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # True로 하면 SQL 실행 로그가 콘솔에 출력됨
)

# 세션팩토리
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

# Base 선언 (모든 모델의 부모 클래스)
Base = declarative_base()

# -----------------------
# DB 초기화 함수
# -----------------------
def init_db():
    """
    모델에서 정의한 테이블을 실제 DB에 생성합니다.
    (이미 존재하는 테이블은 무시됨)
    """
    from models import Question, Attempt  # 순환 참조 방지용 import
    Base.metadata.create_all(bind=engine)


# -----------------------
# DB 세션 의존성 함수 (예: FastAPI/Flask에서 활용)
# -----------------------
def get_db():
    """
    요청 단위 세션을 생성/종료하는 generator.
    Flask/FastAPI 라우트에서 `db = next(get_db())` 식으로 사용 가능.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

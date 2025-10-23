from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, create_engine, func, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    qno = Column(String(50))              # 문제 번호
    stem = Column(Text, nullable=False)   # 문제 본문
    options = Column(Text)                # 보기 (JSON string)
    answer = Column(String(50))           # 정답
    explanation = Column(Text)            # 해설
    category = Column(String(50))         # 카테고리
    subcategory = Column(String(50))      # 서브카테고리
    source_name = Column(String(200))     # 업로드 파일명

class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50))
    question_id = Column(Integer, ForeignKey("questions.id"))
    chosen = Column(String(50))
    correct = Column(Boolean)
    created_at = Column(DateTime, server_default=func.now())

    question = relationship("Question")

engine = create_engine("sqlite:///data/questions.db", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

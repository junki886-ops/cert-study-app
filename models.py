from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from db import Base

# -----------------------
# 문제 테이블
# -----------------------
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    stem = Column(Text, nullable=False)                  # 문제 본문
    options = Column(JSON, nullable=True)                # 보기 (JSON 객체: {"A": "...", "B": "..."} )
    answer = Column(String(20), nullable=True)           # 정답 (예: "A", "B")
    explanation = Column(Text, nullable=True)            # 해설
    category = Column(String(100), nullable=True)        # 대분류
    subcategory = Column(String(100), nullable=True)     # 소분류
    source = Column(String(255), nullable=True)          # 출처 (파일명/페이지 등)

    # 관계 (시도 기록)
    attempts = relationship("Attempt", back_populates="question", cascade="all, delete-orphan")


# -----------------------
# 시도 기록 테이블
# -----------------------
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)        # 사용자 구분 (로그인 ID 등)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"))
    chosen = Column(String(20), nullable=True)           # 사용자가 고른 답 (예: "A")
    correct = Column(Boolean, default=False)             # 정답 여부
    note_type = Column(String(50), default="wrong")      # wrong / review 등 구분

    # 관계 (양방향)
    question = relationship("Question", back_populates="attempts")

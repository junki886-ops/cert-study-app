from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, func, Index
from sqlalchemy.orm import relationship
from db import Base
import json

# -----------------------
# 문제 테이블
# -----------------------
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    stem = Column(Text, nullable=False)                  # 문제 본문
    options = Column(Text, nullable=True)                # 보기 (JSON 문자열: {"A":"...", "B":"..."})
    answer = Column(String(20), nullable=True)           # 정답 (예: "A", "B")
    explanation = Column(Text, nullable=True)            # 해설
    category = Column(String(100), nullable=True, index=True)        # 대분류
    subcategory = Column(String(100), nullable=True, index=True)     # 소분류
    source = Column(String(255), nullable=True)          # 출처 (파일명/페이지 등)

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 생성 시각
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())        # 수정 시각

    # 관계 (시도 기록)
    attempts = relationship("Attempt", back_populates="question", cascade="all, delete-orphan")

    # JSON 변환 헬퍼
    def get_options(self):
        return json.loads(self.options) if self.options else {}

    def set_options(self, opts: dict):
        self.options = json.dumps(opts, ensure_ascii=False)

    # 인덱스
    __table_args__ = (
        Index("idx_question_category", "category"),
        Index("idx_question_subcategory", "subcategory"),
    )


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

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 (양방향)
    question = relationship("Question", back_populates="attempts")

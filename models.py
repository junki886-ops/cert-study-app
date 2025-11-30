# ==============================================
# models.py (v2025-final)
# ==============================================

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import json

from db import Base   # ✅ Base 는 db.py 의 Base 를 사용

# ----------------------------------------------
# Question
# ----------------------------------------------
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    stem = Column(Text, nullable=False)
    answer = Column(String(255))
    explanation = Column(Text)
    question_type = Column(String(50), default="MCQ")

    page = Column(Integer)
    category = Column(String(100))
    subcategory = Column(String(100))
    code = Column(Text)
    source = Column(String(255))

    # JSON 문자열 저장
    options_json = Column(Text)
    pairs = Column(Text)
    sequence = Column(Text)

    # 보기 저장
    def set_options(self, options):
        try:
            self.options_json = (
                json.dumps(options, ensure_ascii=False)
                if isinstance(options, (list, dict))
                else options
            )
        except Exception:
            self.options_json = "[]"

    # 보기 가져오기
    def get_options(self):
        try:
            return json.loads(self.options_json) if self.options_json else []
        except:
            return []

    def get_pairs(self):
        try:
            return json.loads(self.pairs) if self.pairs else {}
        except:
            return {}

    def get_sequence(self):
        try:
            return json.loads(self.sequence) if self.sequence else []
        except:
            return []

    def __repr__(self):
        return f"<Question id={self.id} type={self.question_type}>"

# ----------------------------------------------
# Attempt
# ----------------------------------------------
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, default="guest")
    question_id = Column(Integer, ForeignKey("questions.id"))
    chosen = Column(String(10))
    correct = Column(Boolean, default=False)
    note_type = Column(String(20), default="wrong")

    question = relationship("Question", backref="attempts")

    def __repr__(self):
        return f"<Attempt q={self.question_id}, user={self.user_id}, correct={self.correct}>"

# ==============================================
# models.py (v2025-final)
# ==============================================

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import json

# db.py에서 생성한 Base 객체를 가져옵니다.
from db import Base   

# ----------------------------------------------
# Question 모델
# ----------------------------------------------
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 문제 질문 (기존 이름 유지)
    stem = Column(Text, nullable=False)
    
    # 정답 (단순 리스트로 변경되어도 "A", "B" 또는 "1", "2" 같은 인덱스 키 저장)
    answer = Column(String(255))
    
    # 해설
    explanation = Column(Text)
    
    # 문제 유형 (MCQ: 객관식)
    question_type = Column(String(50), default="MCQ")

    # 메타 데이터
    page = Column(Integer)
    category = Column(String(100))
    subcategory = Column(String(100))
    code = Column(Text)
    source = Column(String(255))

    # -------------------------------------------------------
    # [데이터 구조 변경 핵심]
    # 기존: [{"key": "A", "text": "내용"}]
    # 변경: ["내용1", "내용2", "내용3"] (단순 문자열 리스트)
    # -------------------------------------------------------
    options_json = Column(Text, default="[]") 
    pairs = Column(Text, default="{}")
    sequence = Column(Text, default="[]")

    # -------------------------------------------------------
    # Helper Methods (JSON 직렬화/역직렬화)
    # -------------------------------------------------------

    def set_options(self, options):
        """
        리스트 데이터를 받아 JSON 문자열로 변환하여 저장합니다.
        Input 예시: ["EC2", "S3", "Lambda"]
        """
        try:
            if options is None:
                self.options_json = "[]"
            elif isinstance(options, (list, dict)):
                # ensure_ascii=False: 한글 깨짐 방지
                self.options_json = json.dumps(options, ensure_ascii=False)
            else:
                # 문자열로 들어오면 그대로 저장 시도 혹은 리스트로 감싸기
                self.options_json = json.dumps([str(options)], ensure_ascii=False)
        except Exception as e:
            print(f"Error setting options: {e}")
            self.options_json = "[]"

    def get_options(self):
        """
        저장된 JSON 문자열을 파이썬 리스트로 반환합니다.
        Return 예시: ["EC2", "S3", "Lambda"]
        """
        try:
            if not self.options_json:
                return []
            return json.loads(self.options_json)
        except Exception:
            return []

    # (추가) pairs, sequence 처리도 동일한 방식으로 안정성 확보
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
        return f"<Question id={self.id} type={self.question_type} stem={self.stem[:20]}...>"


# ----------------------------------------------
# Attempt 모델 (사용자 풀이 기록)
# ----------------------------------------------
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 사용자 ID (로그인 기능이 없다면 guest 혹은 브라우저 지문 등 사용)
    user_id = Column(String(100), nullable=False, default="guest")
    
    # 문제 ID (FK)
    question_id = Column(Integer, ForeignKey("questions.id"))
    
    # 사용자가 선택한 답 (프론트엔드에서 생성한 Key: "A", "B", "1" 등)
    chosen = Column(String(10))
    
    # 정답 여부
    correct = Column(Boolean, default=False)
    
    # 오답 노트 유형 (wrong: 틀림, bookmark: 중요 표시 등)
    note_type = Column(String(20), default="wrong")

    # 관계 설정 (Attempt.question 으로 문제 정보 접근 가능)
    question = relationship("Question", backref="attempts")

    def __repr__(self):
        return f"<Attempt q={self.question_id}, user={self.user_id}, correct={self.correct}>"
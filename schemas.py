# ==============================================
# schemas.py
# Adaptive PDF Parser 전용 데이터 스키마
# ==============================================

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union

# -----------------------------
# 단일 문항 구조
# -----------------------------
class QuestionItem(BaseModel):
    stem: str = Field(..., description="문제 본문")
    options: Optional[List[str]] = Field(default_factory=list, description="선택지 목록 (A~D 등)")
    answer: Optional[str] = Field(default="", description="정답 (예: A, 1, ②)")
    explanation: Optional[str] = Field(default="", description="해설")
    question_type: Optional[str] = Field(default="MCQ_SHORT", description="문제 유형 (MCQ_CASE / MCQ_SHORT / HOTSPOT)")
    pairs: Optional[Dict[str, str]] = Field(default_factory=dict, description="HOTSPOT 문제용 (상자 매칭 구조)")

# -----------------------------
# 페이지 단위 추출 결과 (LLM용)
# -----------------------------
class PageExtraction(BaseModel):
    items: List[QuestionItem] = Field(default_factory=list, description="페이지 내 추출된 문항 목록")

# -----------------------------
# 예시 JSON 구조
# -----------------------------
"""
[
  {
    "stem": "Litware는 App1과 App2를 사용합니다...",
    "options": ["A. ExpressRoute 배포", "B. Azure AD 동기화"],
    "answer": "A",
    "explanation": "ExpressRoute는 하이브리드 연결을 제공합니다.",
    "question_type": "MCQ_CASE"
  },
  {
    "stem": "해결 방법: 인바운드 보안 규칙을 만듭니다. 이것이 목표를 달성합니까?",
    "options": ["A. 예", "B. 아니오"],
    "answer": "A",
    "question_type": "MCQ_SHORT"
  },
  {
    "stem": "Azure Network Watcher를 사용하여...",
    "pairs": {"상자1": "IP 흐름 확인", "상자2": "연결 문제 해결"},
    "question_type": "HOTSPOT"
  }
]
"""

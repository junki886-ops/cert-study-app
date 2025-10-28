from pydantic import BaseModel, Field
from typing import List, Dict

class Question(BaseModel):
    stem: str = Field(..., description="문제 본문")
    options: Dict[str, str] = Field(..., description="선택지 (예: {'A':'...', 'B':'...'})")
    answer: str = Field(..., description="정답 (예: A, B, C, D)")
    explanation: str = Field(..., description="해설")

class PageExtraction(BaseModel):
    items: List[Question] = Field(..., description="OCR 텍스트에서 추출된 문제 리스트")

from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class QAItem(BaseModel):
    stem: str = Field(..., description="문제 본문")
    options: Dict[str, str] = Field(..., description='보기 (A,B,C,D)')
    answer: str = Field(..., description="정답 (options 중 하나)")
    explanation: Optional[str] = Field(None, description="해설")

class PageExtraction(BaseModel):
    items: List[QAItem]

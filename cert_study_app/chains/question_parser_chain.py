import json
import time
from typing import List, Optional

from pydantic import BaseModel, Field
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser


class QuestionParsedResult(BaseModel):
    stem: str = Field(description="문제 본문", default="")
    options: List[str] = Field(description="보기 목록 (객관식일 경우)", default_factory=list)
    answer: List[str] = Field(description="정답 또는 선택결과", default_factory=list)
    explanation: str = Field(description="간단한 해설", default="")
    question_type: str = Field(description="문제 유형 (mcq, yes_no, sequence, code, scenario)")
    code: Optional[str] = Field(description="코드가 있다면 포함", default="")
    sequence: Optional[List[str]] = Field(description="순서형일 경우 항목", default_factory=list)

parser = PydanticOutputParser(pydantic_object=QuestionParsedResult)

QUESTION_PARSE_PROMPT = ChatPromptTemplate.from_template(
    """
너는 OCR로 인식된 시험 문제를 분석하여 구조화하는 전문 파서이다.
문제 유형은 다음 중 하나일 수 있다:
- mcq: 객관식
- yes_no: 참/거짓 또는 예/아니오
- sequence: 순서형 문제
- code: 코드 기반 문제
- scenario: 시나리오 기반 문제

이 문제는 주로 '{question_type}' 유형으로 추정된다.

{format_instructions}

문제 원문:
{ocr_text}
"""
)


def detect_question_type(text: str) -> str:
    lowered = text.lower()
    if any(k in lowered for k in ["예", "아니오", "yes", "no", "true", "false"]):
        return "yes_no"
    if any(k in lowered for k in ["순서", "정렬", "drag", "drop", "순서대로"]):
        return "sequence"
    if any(k in lowered for k in ["json", "{", "}", "az ", "set-az", "cli", "powershell", "bash", "cmd", "코드"]):
        return "code"
    if any(k in lowered for k in ["시나리오", "case", "contoso", "litware", "fabrikam", "조건", "상황"]):
        return "scenario"
    return "mcq"


def build_question_parser_chain(llm):
    # LCEL: Prompt -> LLM -> Pydantic Parser
    return QUESTION_PARSE_PROMPT | llm | parser


def parse_question_with_chain(llm, page: int, text: str) -> dict:
    question_type = detect_question_type(text)
    chain = build_question_parser_chain(llm)

    try:
        started_at = time.time()
        # parser.get_format_instructions()를 통해 프롬프트에 JSON 스키마를 주입합니다.
        parsed_result = chain.invoke(
            {
                "question_type": question_type,
                "ocr_text": text[:1800],
                "format_instructions": parser.get_format_instructions(),
            }
        )
        
        # Pydantic 모델을 dict로 변환 (Pydantic v1/v2 호환성을 위해 dict() 사용)
        parsed = parsed_result.dict()
        parsed["page"] = page
        
        print(f"[LLM] p{page} ({question_type}) parsed in {time.time() - started_at:.1f}s")
        return parsed
        
    except Exception as exc:
        print(f"[WARN] LLM parse failed (p{page}): {exc}")
        return {
            "page": page,
            "stem": text[:400],
            "options": [],
            "answer": [],
            "explanation": f"오류: {exc}",
            "question_type": question_type,
            "code": "",
            "sequence": [],
        }

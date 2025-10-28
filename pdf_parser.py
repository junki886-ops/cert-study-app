from pathlib import Path
from pdf2image import convert_from_path
import pytesseract, json

# LangChain + HuggingFace
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from pydantic import BaseModel, Field
from typing import List

# -------------------------
# 1. 문제 JSON 스키마
# -------------------------
class Question(BaseModel):
    stem: str = Field(..., description="문제 본문")
    options: List[str] = Field(..., description="선택지 목록 (예: ['A. ...', 'B. ...'])")
    answer: str = Field(..., description="정답 (예: A, B, 1, ② 등)")
    explanation: str = Field(..., description="해설")

# -------------------------
# 2. Phi-3-mini LLM 로드 (CPU)
# -------------------------
def load_llm(model_name="microsoft/Phi-3-mini-4k-instruct", device=-1):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    hf_pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device=device,        # -1이면 CPU
        max_new_tokens=1024,
        temperature=0
    )
    return HuggingFacePipeline(pipeline=hf_pipeline)

# -------------------------
# 3. OCR + 문자 기준 청킹 + LLM 구조화
# -------------------------
def chunk_text(text: str, max_chars: int = 2000):
    """문자 기준으로 텍스트 청킹"""
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

def parse_pdf(pdf_path, output_json, max_chars=2000, model_name="microsoft/Phi-3-mini-4k-instruct", lang="kor+eng", poppler_path=None):
    # (1) PDF → 이미지 → OCR
    pages = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
    ocr_text = ""
    for idx, page in enumerate(pages, start=1):
        txt = pytesseract.image_to_string(page, lang=lang)
        ocr_text += f"\n\n--- page {idx} ---\n{txt}"

    # (2) 문자 기준 청킹
    text_chunks = chunk_text(ocr_text, max_chars=max_chars)

    # (3) LangChain 파이프라인
    parser = PydanticOutputParser(pydantic_object=List[Question])
    format_instructions = parser.get_format_instructions()

    prompt = ChatPromptTemplate.from_template("""
    아래는 OCR로 추출한 시험 문제 텍스트 일부입니다.
    문제/보기/정답/해설을 JSON 형식으로 변환하세요.

    {format_instructions}

    OCR 텍스트:
    {ocr_text}
    """)

    llm = load_llm(model_name=model_name)
    chain = prompt | llm | parser

    # (4) 청킹 단위로 실행
    all_results = []
    for i, chunk in enumerate(text_chunks, start=1):
        print(f"[INFO] LLM 파싱 중... (청크 {i}/{len(text_chunks)})")
        result = chain.invoke({
            "ocr_text": chunk,
            "format_instructions": format_instructions
        })
        all_results.extend(result)

    # (5) 저장
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(
        json.dumps([q.dict() for q in all_results], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[INFO] 전체 파싱된 문항 수: {len(all_results)}")
    return all_results

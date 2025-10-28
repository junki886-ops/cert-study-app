from pathlib import Path
from pdf2image import convert_from_path
import pytesseract, json

from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from schemas import PageExtraction

# -------------------------
# LLM 로드 (Phi-3-mini)
# -------------------------
def load_llm(model_name="microsoft/Phi-3-mini-4k-instruct", device=-1):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    hf_pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device=device,   # -1 = CPU, 0 = GPU
        max_new_tokens=1024,
        temperature=0.0
    )
    return HuggingFacePipeline(pipeline=hf_pipeline)

# -------------------------
# OCR + 청킹
# -------------------------
def chunk_text(text: str, max_chars: int = 2000):
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

def parse_pdf(pdf_path, output_json, max_chars=2000, model_name="microsoft/Phi-3-mini-4k-instruct", lang="kor+eng", poppler_path=None):
    # (1) OCR
    pages = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
    ocr_text = ""
    for idx, page in enumerate(pages, start=1):
        txt = pytesseract.image_to_string(page, lang=lang)
        ocr_text += f"\n\n--- page {idx} ---\n{txt}"

    # (2) 청킹
    text_chunks = chunk_text(ocr_text, max_chars=max_chars)

    # (3) LangChain 체인 준비
    parser = PydanticOutputParser(pydantic_object=PageExtraction)
    format_instructions = parser.get_format_instructions()

    prompt = ChatPromptTemplate.from_template("""
    아래는 OCR로 추출한 시험 문제 텍스트입니다.
    문제/보기/정답/해설을 JSON 형식으로 변환하세요.

    {format_instructions}

    OCR 텍스트:
    {ocr_text}
    """)

    llm = load_llm(model_name=model_name)
    chain = prompt | llm | parser

    # (4) 청킹 단위 실행
    all_results = []
    for i, chunk in enumerate(text_chunks, start=1):
        print(f"[INFO] LLM 파싱 중... (청크 {i}/{len(text_chunks)})")
        try:
            parsed: PageExtraction = chain.invoke({
                "ocr_text": chunk,
                "format_instructions": format_instructions
            })
            all_results.extend(parsed.items)
        except Exception as e:
            print(f"[WARN] 청크 {i} 파싱 실패: {e}")

    # (5) JSON 저장
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(
        json.dumps([q.dict() for q in all_results], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[INFO] 전체 파싱된 문항 수: {len(all_results)}")
    return all_results

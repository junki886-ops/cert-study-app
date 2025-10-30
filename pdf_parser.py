from pathlib import Path
from pdf2image import convert_from_path
import json, sqlite3
from paddleocr import PaddleOCR
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from schemas import PageExtraction

DB_PATH = "data/questions.db"

# -------------------------
# DB 초기화
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page INTEGER,
        stem TEXT,
        options TEXT,
        answer TEXT,
        explanation TEXT,
        image_path TEXT
    )
    """)
    conn.commit()
    conn.close()

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
        device=device,
        max_new_tokens=1024,
        temperature=0.0
    )
    return HuggingFacePipeline(pipeline=hf_pipeline)

# -------------------------
# 텍스트 청킹
# -------------------------
def chunk_text(text: str, max_chars: int = 2000):
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

# -------------------------
# 메인 파이프라인
# -------------------------
def parse_pdf(pdf_path, output_json,
              max_chars=2000,
              model_name="microsoft/Phi-3-mini-4k-instruct",
              lang="korean",
              poppler_path=None):

    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    pages = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
    ocr = PaddleOCR(use_angle_cls=True, lang=lang)

    Path("data/images").mkdir(parents=True, exist_ok=True)

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

    all_results = []

    # (페이지별 OCR + 청킹 + LLM)
    for page_idx, page in enumerate(pages, start=1):
        img_path = f"data/images/page_{page_idx}.png"
        page.save(img_path, "PNG")

        result = ocr.ocr(img_path, cls=True)
        page_text = "\n".join([line[1][0] for line in result[0]]) if result[0] else ""

        # 페이지 단위 텍스트를 청킹
        chunks = chunk_text(page_text, max_chars=max_chars)

        for i, chunk in enumerate(chunks, start=1):
            print(f"[INFO] LLM 파싱 중... (페이지 {page_idx}, 청크 {i}/{len(chunks)})")
            try:
                parsed: PageExtraction = chain.invoke({
                    "ocr_text": chunk,
                    "format_instructions": format_instructions
                })
                for q in parsed.items:
                    all_results.append(q)
                    cursor.execute("""
                        INSERT INTO questions (page, stem, options, answer, explanation, image_path)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        page_idx,
                        q.stem,
                        json.dumps(q.options, ensure_ascii=False),
                        q.answer,
                        q.explanation,
                        img_path
                    ))
            except Exception as e:
                print(f"[WARN] 페이지 {page_idx}, 청크 {i} 파싱 실패: {e}")

    conn.commit()
    conn.close()

    # JSON 저장
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(
        json.dumps([q.dict() for q in all_results], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[INFO] 전체 파싱된 문항 수: {len(all_results)}")
    return all_results

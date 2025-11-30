# ==============================================
# analyze_parser_log_ai.py
# Adaptive PDF Parser 로그 자동 분석 + LangChain AI 조언
# ==============================================

import re, os
from pathlib import Path
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage
from langchain_huggingface import HuggingFacePipeline
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# ----------------------------------------------
# CPU LLM 로드 (경량)
# ----------------------------------------------
def load_cpu_llm(model_name="microsoft/Phi-3-mini-4k-instruct"):
    print("[INFO] CPU 기반 LLM 로드 중...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=512,
        temperature=0.0,
        device=-1  # ✅ CPU 강제
    )
    return HuggingFacePipeline(pipeline=pipe)

# ----------------------------------------------
# 로그 분석 함수
# ----------------------------------------------
def analyze_log_text(log_text: str):
    summary = {}

    # 단계별 탐지
    summary["has_pdf2img"] = bool(re.search(r"\[STEP 1\]", log_text))
    summary["has_ocr"] = bool(re.search(r"\[STEP 2\]", log_text))
    summary["has_smart"] = bool(re.search(r"\[STEP 3-0\]", log_text))
    summary["has_llm"] = bool(re.search(r"\[STEP 3\]", log_text))
    summary["has_db"] = bool(re.search(r"\[STEP 4\]", log_text))
    summary["is_done"] = bool(re.search(r"\[✅ 전체 완료\]", log_text))

    # 오류 감지
    errors = re.findall(r"⚠️ \[오류\].+page.?≈?(\d+)?", log_text)
    summary["error_pages"] = [int(e) for e in errors if e.isdigit()]
    summary["error_count"] = len(summary["error_pages"])

    # OCR 진행률
    ocr_progress = re.findall(r"OCR\s+(\d+)\s*페이지까지 완료", log_text)
    summary["ocr_progress"] = int(ocr_progress[-1]) if ocr_progress else 0

    # Smart 병합 여부
    summary["smart_active"] = "Smart Parsing" in log_text

    # 총 문항/시간
    m = re.search(r"총\s*(\d+)\s*문항\s*/\s*소요시간\s*([\d\.]+)초", log_text)
    if m:
        summary["count"], summary["seconds"] = m.groups()
    else:
        summary["count"], summary["seconds"] = None, None

    return summary


# ----------------------------------------------
# LLM 조언 생성
# ----------------------------------------------
def generate_advice(summary, llm):
    prompt = ChatPromptTemplate.from_template("""
다음은 PDF 파서 실행 로그 요약입니다.
이 상황에서 사용자가 어떤 조치를 취해야 하는지 단계별로 한국어로 설명해 주세요.

요약:
{summary}

설명 방식:
- 어디서 멈췄는지 판단
- 필요한 재시작/복구 조치
- 주의할 점 (OCR 캐시, checkpoint, DB 등)
- 다음 실행 시 명령어 예시 (bash 형식)

짧고 명확하게, 실무 엔지니어에게 조언하듯 설명하세요.
    """)

    input_msg = prompt.format_messages(summary=str(summary))
    result = llm.invoke(input_msg)
    return result


# ----------------------------------------------
# 실행
# ----------------------------------------------
def analyze_parser_log_ai(log_path="parser_log.txt"):
    if not Path(log_path).exists():
        print(f"❌ 로그 파일을 찾을 수 없습니다: {log_path}")
        return

    log_text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
    summary = analyze_log_text(log_text)
    llm = load_cpu_llm()
    print("\n[INFO] LLM 분석 중... 🧠\n")
    advice = generate_advice(summary, llm)
    print("==============================================")
    print("📊 로그 요약:", summary)
    print("==============================================")
    print("🧭 AI 조언:\n")
    print(advice)
    print("==============================================")

if __name__ == "__main__":
    analyze_parser_log_ai()

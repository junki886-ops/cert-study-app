# ==============================================
# adaptive_parser_monitor.py
# Adaptive PDF Parser 자가진단 + 자동 복구 실행기
# (CPU LLM + LangChain 통합)
# ==============================================

import os, time, re, json
from pathlib import Path

from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langchain_huggingface import HuggingFacePipeline
from langchain.prompts import ChatPromptTemplate

from pdf_parser_adaptive import parse_pdf, resume_incomplete_parsing

# ----------------------------------------------
# 1️⃣ CPU 기반 LLM 로드
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
        device=-1
    )
    return HuggingFacePipeline(pipeline=pipe)

# ----------------------------------------------
# 2️⃣ 로그 상태 감지
# ----------------------------------------------
def detect_parser_state(log_path="parser_log.txt", timeout_min=10):
    state = {
        "status": "unknown",
        "last_step": None,
        "last_ocr_page": 0,
        "errors": [],
        "checkpoint_exists": Path("data/.parse_checkpoint.json").exists(),
        "ocr_cache_pages": len(list(Path("data/ocr_logs").glob("page_*.txt")))
    }

    if not Path(log_path).exists():
        state["status"] = "no_log"
        return state

    text = Path(log_path).read_text(encoding="utf-8", errors="ignore")

    # 마지막 수정 시간으로 멈춤 판단
    last_time = Path(log_path).stat().st_mtime
    idle_min = round((time.time() - last_time) / 60, 1)
    state["idle_min"] = idle_min

    if "[✅ 전체 완료]" in text:
        state["status"] = "done"
        state["last_step"] = "완료"
        return state

    # 단계 추적
    for step, name in [
        ("[STEP 4]", "DB 저장"),
        ("[STEP 3]", "LLM 파싱"),
        ("[STEP 2]", "OCR"),
        ("[STEP 1]", "PDF 변환")
    ]:
        if step in text:
            state["last_step"] = name
            break

    # OCR 진행률 감지
    match = re.findall(r"OCR\s+(\d+)\s*페이지까지 완료", text)
    if match:
        state["last_ocr_page"] = int(match[-1])

    # 오류 감지
    errors = re.findall(r"⚠️ \[오류\].+page.?≈?(\d+)?", text)
    state["errors"] = [int(e) for e in errors if e.isdigit()]

    # 멈춤 판단
    if idle_min >= timeout_min:
        state["status"] = "stuck"
    else:
        state["status"] = "running"

    return state

# ----------------------------------------------
# 3️⃣ LLM 조언 생성
# ----------------------------------------------
def llm_advice(llm, state: dict):
    prompt = ChatPromptTemplate.from_template("""
당신은 Adaptive PDF 파서의 유지보수 전문가입니다.
다음 상태를 분석하고, 사용자가 지금 무엇을 해야 할지 단계별로 한국어로 설명하세요.

상태 요약:
{state}

설명 방식:
- 현재 단계
- 멈춤 여부
- 어떤 조치를 취해야 하는지 (resume / 재시작 / 점검 등)
- 실행 명령어 예시 (bash 또는 python)
- 주의할 점 (checkpoint, OCR 캐시 등)
    """)
    messages = prompt.format_messages(state=str(state))
    return llm.invoke(messages)

# ----------------------------------------------
# 4️⃣ 메인 실행기
# ----------------------------------------------
def monitor_and_resume(pdf_path="data/uploads/dump.pdf", log_path="parser_log.txt"):
    print("\n[INFO] Adaptive Parser 모니터 시작...")
    state = detect_parser_state(log_path)
    llm = load_cpu_llm()
    print("\n🧠 LLM 상태 분석 중...\n")
    advice = llm_advice(llm, state)

    print("==============================================")
    print("📊 현재 파서 상태 요약:")
    for k,v in state.items():
        print(f"  - {k}: {v}")
    print("==============================================")
    print("🤖 AI 조언:")
    print(advice)
    print("==============================================")

    # 자동 복구 조건
    if state["status"] in ["stuck", "running"] and state["checkpoint_exists"]:
        print("\n[🪄 자동 복구 실행] checkpoint 감지됨 → resume_incomplete_parsing() 수행")
        resume_incomplete_parsing(pdf_path)
    elif state["status"] == "no_log":
        print("\n[INFO] 로그가 없어 새 작업으로 parse_pdf() 실행")
        parse_pdf(pdf_path)
    elif state["status"] == "done":
        print("\n✅ 이미 모든 작업이 완료되었습니다.")
    else:
        print("\n⚠️ 자동 재개 조건에 맞지 않습니다. AI 조언을 참고하세요.")

if __name__ == "__main__":
    monitor_and_resume()

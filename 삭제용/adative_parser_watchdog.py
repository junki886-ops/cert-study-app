# ==============================================
# adaptive_parser_watchdog_local.py
# Adaptive PDF Parser 실시간 감시 + 자동 복구
# (LangChain + CPU LLM + Local Popup Only)
# ==============================================

import os, time, re, json, platform
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
# 2️⃣ 로컬 알림 (Windows/macOS/Linux 자동 감지)
# ----------------------------------------------
def local_notify(title, msg):
    system = platform.system()
    try:
        if system == "Windows":
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(title, msg, duration=10)
        elif system == "Darwin":  # macOS
            os.system(f"osascript -e 'display notification \"{msg}\" with title \"{title}\"'")
        else:  # Linux
            os.system(f'notify-send "{title}" "{msg}"')
    except Exception as e:
        print(f"[WARN] 로컬 알림 실패: {e}")
    print(f"[LOCAL ALERT] {title} - {msg}")


# ----------------------------------------------
# 3️⃣ 로그 상태 감지
# ----------------------------------------------
def detect_parser_state(log_path="parser_log.txt"):
    state = {
        "status": "unknown",
        "last_step": None,
        "last_ocr_page": 0,
        "checkpoint_exists": Path("data/.parse_checkpoint.json").exists(),
        "ocr_cache_pages": len(list(Path("data/ocr_logs").glob("page_*.txt")))
    }

    if not Path(log_path).exists():
        state["status"] = "no_log"
        return state

    text = Path(log_path).read_text(encoding="utf-8", errors="ignore")

    # 완료 여부
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

    # OCR 진행률
    ocr_progress = re.findall(r"OCR\s+(\d+)\s*페이지까지 완료", text)
    if ocr_progress:
        state["last_ocr_page"] = int(ocr_progress[-1])

    # 시간 확인
    last_time = Path(log_path).stat().st_mtime
    state["idle_min"] = round((time.time() - last_time) / 60, 1)

    # 상태 결정
    if state["idle_min"] > 5:
        state["status"] = "stuck"
    else:
        state["status"] = "running"

    return state


# ----------------------------------------------
# 4️⃣ LLM 분석 및 조언
# ----------------------------------------------
def llm_advice(llm, state):
    prompt = ChatPromptTemplate.from_template("""
당신은 Adaptive PDF 파서의 유지보수 엔지니어입니다.
다음 상태를 분석하고, 사용자가 지금 어떤 조치를 취해야 하는지 단계별로 설명하세요.

상태:
{state}

응답 형식:
- 현재 상태
- 가능한 원인
- 복구 방법
- 주의사항
- 실행 예시
    """)
    return llm.invoke(prompt.format_messages(state=str(state)))


# ----------------------------------------------
# 5️⃣ 실시간 감시 루프
# ----------------------------------------------
def watch_and_resume(pdf_path="data/uploads/dump.pdf",
                     log_path="parser_log.txt",
                     check_interval=60):
    print("[INFO] Adaptive Parser 실시간 감시 (로컬 팝업 전용) 시작")

    llm = load_cpu_llm()
    while True:
        state = detect_parser_state(log_path)

        print(f"\n⏱️ 상태: {state['status']} | 단계: {state.get('last_step')} | "
              f"idle: {state.get('idle_min',0)}분 | OCR: {state.get('last_ocr_page')}p")

        # 1️⃣ 완료된 경우
        if state["status"] == "done":
            local_notify("✅ 파서 완료", "모든 페이지 파싱이 완료되었습니다.")
            break

        # 2️⃣ 멈춘 경우
        if state["status"] == "stuck":
            local_notify("⚠️ 파서 멈춤 감지", f"{state.get('last_step')} 단계에서 중단됨.")
            print("\n🚨 멈춤 감지됨 → LLM 분석 및 복구 중...")
            advice = llm_advice(llm, state)
            print("\n🤖 LLM 조언:\n", advice)

            if state["checkpoint_exists"]:
                local_notify("🪄 자동 복구 시작", "checkpoint 감지 → resume_incomplete_parsing 실행 중...")
                resume_incomplete_parsing(pdf_path)
            else:
                local_notify("🧩 전체 재시작", "checkpoint 없음 → parse_pdf 전체 재실행")
                parse_pdf(pdf_path)

        # 3️⃣ 진행 중인 경우
        if state["status"] == "running":
            print("[INFO] 파서 정상 진행 중...")

        time.sleep(check_interval)


# ----------------------------------------------
# 실행
# ----------------------------------------------
if __name__ == "__main__":
    watch_and_resume()

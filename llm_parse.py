# ==============================================
# llm_parse.py (v3.2 Adaptive-Compatible)
# OCR + LLM 시험문항 파서 (MCQ, Yes/No, Sequence, Code, Scenario)
# Compatible with pdf_parser_adaptive_v6 + app_v2025 + models_v2025
# ==============================================

import re, json, time

# ----------------------------------------------
# JSON 안전 복원 함수
# ----------------------------------------------
def safe_json_loads(text: str):
    """LLM 출력 문자열에서 JSON을 최대한 안전하게 복원"""
    if not text:
        return {}

    # 코드블록 제거
    if "```json" in text:
        text = text.split("```json", 1)[-1]
    if "```" in text:
        text = text.split("```", 1)[0]

    # JSON 중괄호 감지
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        text = m.group(0)

    # 따옴표 통일
    text = (
        text.replace("“", '"')
            .replace("”", '"')
            .replace("‘", '"')
            .replace("’", '"')
            .replace("'", '"')
    )

    # 안전 파싱 시도
    try:
        return json.loads(text)
    except Exception:
        # 부분 복구 fallback
        res = {}
        for key in ["stem", "options", "answer", "explanation", "question_type", "code", "sequence"]:
            m = re.search(rf'"?{key}"?\s*:\s*"?(.+?)"?(?:,|\}})', text, re.S)
            if m:
                res[key] = m.group(1).strip()
        return res

# ----------------------------------------------
# LLM 기반 문제 파서
# ----------------------------------------------
def llm_parse_v2(llm, page: int, text: str):
    """
    Adaptive PDF Parser용 LLM 기반 문제 파서
    (다양한 문제 유형 자동 감지)
    """

    # ---- 문제 유형 감지 ----
    lowered = text.lower()
    if any(k in lowered for k in ["예", "아니오", "yes", "no", "true", "false"]):
        q_type = "yes_no"
    elif any(k in lowered for k in ["순서", "정렬", "drag", "drop", "순서대로"]):
        q_type = "sequence"
    elif any(k in lowered for k in ["json", "{", "}", "az ", "set-az", "cli", "powershell", "bash", "cmd", "코드"]):
        q_type = "code"
    elif any(k in lowered for k in ["시나리오", "case", "contoso", "litware", "fabrikam", "조건", "상황"]):
        q_type = "scenario"
    else:
        q_type = "mcq"

    # ---- 프롬프트 구성 ----
    prompt = f"""
너는 OCR로 인식된 시험 문제를 분석하여 JSON으로 구조화하는 전문 파서이다.
문제 유형은 다음 중 하나일 수 있다:
- mcq: 객관식
- yes_no: 참/거짓 또는 예/아니오
- sequence: 순서형 문제
- code: 코드 기반 문제
- scenario: 시나리오 기반 문제

다음 형식의 JSON만 출력하라:
{{
  "stem": "문제 본문",
  "options": ["보기1", "보기2", "보기3"],
  "answer": ["정답 또는 선택결과"],
  "explanation": "간단한 해설",
  "question_type": "{q_type}",
  "code": "코드가 있다면 포함",
  "sequence": ["순서형일 경우 항목"]
}}

문제 원문:
{text[:1800]}
"""

    # ---- LLM 호출 및 파싱 ----
    try:
        start_time = time.time()
        raw_out = llm.invoke(prompt)

        # LLM 출력 정리
        if isinstance(raw_out, str):
            output = raw_out.strip()
        elif hasattr(raw_out, "content"):
            output = raw_out.content.strip()
        else:
            output = str(raw_out).strip()

        parsed = safe_json_loads(output)

        # 필수 필드 보정
        parsed.setdefault("page", page)
        parsed.setdefault("stem", text[:400])
        parsed.setdefault("options", [])
        parsed.setdefault("answer", [])
        parsed.setdefault("explanation", "")
        parsed.setdefault("question_type", q_type)
        parsed.setdefault("code", "")
        parsed.setdefault("sequence", [])

        # 타입 보정
        if isinstance(parsed.get("options"), str):
            try:
                parsed["options"] = json.loads(parsed["options"])
            except Exception:
                parsed["options"] = [parsed["options"]]
        if isinstance(parsed.get("answer"), str) and not parsed["answer"].startswith("["):
            parsed["answer"] = [parsed["answer"]]

        print(f"[LLM] ✅ p{page} ({q_type}) 완료 ({time.time() - start_time:.1f}s)")
        return parsed

    except Exception as e:
        print(f"[WARN] ⚠️ LLM 파싱 실패 (p{page}): {e}")
        return {
            "page": page,
            "stem": text[:400],
            "options": [],
            "answer": [],
            "explanation": f"오류: {str(e)}",
            "question_type": q_type,
            "code": "",
            "sequence": []
        }

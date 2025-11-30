# ==============================================
# ingest.py (v2025-UNIVERSAL)
# OCR JSON + 수동 JSON + Case Study JSON 완전 호환
# ==============================================

import json
from db import SessionLocal, init_db
from models import Question


def normalize(item: dict):
    """
    서로 다른 JSON 스키마를 하나의 표준 Question 구조로 정규화한다.
    """

    # 1) 문제(Stem)
    stem = (
        item.get("stem")
        or item.get("question")
        or item.get("q_text")
        or ""
    ).strip()

    # 2) 해설
    explanation = item.get("explanation", "").strip()

    # 3) 정답
    answer_raw = item.get("answer", "")
    answer = (
        json.dumps(answer_raw, ensure_ascii=False)
        if isinstance(answer_raw, list)
        else str(answer_raw).strip()
    )

    # 4) 보기 (list → dict 자동 변환)
    opts = item.get("options", {})
    if isinstance(opts, list):  # ["opt1","opt2",...]
        options = {chr(65 + i): opt for i, opt in enumerate(opts)}
    elif isinstance(opts, dict):
        options = opts
    else:
        options = {}

    # 5) Topic / Subtopic → category/subcategory 매핑
    category = item.get("category") or item.get("topic") or None
    subcategory = item.get("subcategory") or item.get("subtopic") or None

    # 6) OCR 기반 JSON 호환 필드
    page = item.get("page")
    qtype = item.get("question_type", "MCQ")
    code = item.get("code", "")

    # 7) 순서형 / 매칭형 문제도 그대로 pass (DB에서 JSON 형태로 저장)
    sequence = (
        json.dumps(item.get("sequence"), ensure_ascii=False)
        if isinstance(item.get("sequence"), list)
        else None
    )
    pairs = (
        json.dumps(item.get("pairs"), ensure_ascii=False)
        if isinstance(item.get("pairs"), dict)
        else None
    )

    return {
        "stem": stem,
        "explanation": explanation,
        "answer": answer,
        "options": options,
        "category": category,
        "subcategory": subcategory,
        "page": page,
        "question_type": qtype,
        "code": code,
        "sequence": sequence,
        "pairs": pairs,
    }


def ingest_questions(json_path: str, source_name: str = "imported"):
    """
    다양한 형태의 JSON 문제 파일을 DB에 넣는 통합 ingest 함수.
    """
    init_db()
    db = SessionLocal()
    count = 0

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Case Study 형태: {"questions":[...]} 지원
        if isinstance(data, dict) and "questions" in data:
            data = data["questions"]

        for raw in data:
            if not isinstance(raw, dict):
                continue

            qn = normalize(raw)

            q = Question(
                page=qn["page"],
                stem=qn["stem"],
                explanation=qn["explanation"],
                answer=qn["answer"],
                question_type=qn["question_type"],
                category=qn["category"],
                subcategory=qn["subcategory"],
                source=source_name,
                code=qn["code"],
                sequence=qn["sequence"],
                pairs=qn["pairs"],
            )

            q.set_options(qn["options"])
            db.add(q)
            count += 1

        db.commit()
        print(f"[INFO] ✅ {count} 문항 DB 적재 완료 ({source_name})")
        return count

    except Exception as e:
        db.rollback()
        print(f"[ERROR] DB 적재 중 오류 발생 → {e}")
        raise e

    finally:
        db.close()


if __name__ == "__main__":
    # 네가 실제로 둔 경로에 맞게 수정
    # 예: data/json/questions.json 에 있으면
    path = "data/json/questions.json"
    ingest_questions(path, "az104_dump")

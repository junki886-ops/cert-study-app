# ==============================================
# ingest.py (v2025-UNIVERSAL-COMPAT)
# ✅ 현재 db.py/init_db() (인자 없음)와 100% 호환
# ✅ 기존 questions 테이블 스키마( options_json / answer / pairs / sequence ) 기준으로 안전 동작
# ✅ 확장 모델( set_answer_keys / set_answer_steps / set_images / page_no 등 )이 있으면 자동 활용
# ✅ options는 항상 [{"key","text"}] 형태로 저장 → 웹 표기 안정화
# ✅ Steps/복수/중복 정답:
#    - 확장 모델이면 answer_json/answer_steps_json에 저장
#    - 구버전이면 answer="A,B" / sequence=["E","B","C"] 로 fallback
# ✅ rebuild_db=True: DB 파일 삭제 후 재생성
# ==============================================

import json
import os
from typing import Any, Dict, List

from db import SessionLocal, init_db, DB_PATH
from models import Question


# -----------------------------
# Helpers
# -----------------------------
def _to_list_answer_keys(v: Any) -> List[str]:
    """
    정답 입력을 key 리스트로 정규화.
    - ["A","C"] -> ["A","C"]
    - "A" -> ["A"]
    - "A,C" -> ["A","C"]
    - "BE" -> ["B","E"]  (전부 대문자 알파벳일 때만)
    - dict(steps 텍스트) -> [] (steps에서 처리)
    """
    if v is None:
        return []

    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]

    if isinstance(v, dict):
        return []

    s = str(v).strip()
    if not s:
        return []

    if "," in s:
        return [x.strip() for x in s.split(",") if x.strip()]

    if len(s) >= 2 and s.isalpha() and s.upper() == s:
        return list(s)

    return [s]


def _normalize_options(opts: Any) -> List[Dict[str, str]]:
    """
    options를 항상 표준 리스트 형태로:
      [{"key":"A","text":"..."}, ...]
    지원:
    - list[str]
    - dict{key:text}
    - list[dict] (이미 key/text)
    """
    if not opts:
        return []

    # list[dict]
    if isinstance(opts, list) and opts and all(isinstance(x, dict) for x in opts):
        out = []
        for o in opts:
            k = str(o.get("key", "")).strip()
            t = str(o.get("text", "")).strip()
            if k or t:
                out.append({"key": k, "text": t})
        return out

    # list[str]
    if isinstance(opts, list):
        return [{"key": chr(65 + i), "text": str(opt).strip()} for i, opt in enumerate(opts)]

    # dict{key:text}
    if isinstance(opts, dict):
        return [{"key": str(k).strip(), "text": str(v).strip()} for k, v in opts.items()]

    return []


def _infer_steps_answer_keys(item: Dict[str, Any], options_std: List[Dict[str, str]]) -> List[str]:
    """
    Steps 정답을 key 리스트로 뽑는다.
    우선순위:
    1) answer_steps(list)
    2) sequence(list)
    3) answer가 {"1":"텍스트", "2":"텍스트"} 형태면 options text 매칭으로 key 추정
    """
    if isinstance(item.get("answer_steps"), list):
        return [str(x).strip() for x in item["answer_steps"] if str(x).strip()]

    if isinstance(item.get("sequence"), list):
        return [str(x).strip() for x in item["sequence"] if str(x).strip()]

    ans = item.get("answer")
    if isinstance(ans, dict) and all(str(k).isdigit() for k in ans.keys()):
        text_to_key = {}
        for o in options_std:
            t = (o.get("text") or "").strip()
            if t and t not in text_to_key:
                text_to_key[t] = (o.get("key") or "").strip()

        keys = []
        for i in sorted(int(x) for x in ans.keys()):
            t = str(ans.get(str(i), "")).strip()
            keys.append(text_to_key.get(t, "__UNKNOWN__"))
        return keys

    return []


def _load_json(json_path: str) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Case Study: {"questions":[...]}
    if isinstance(data, dict) and "questions" in data:
        data = data["questions"]

    if not isinstance(data, list):
        raise ValueError("JSON root must be a list (or dict with 'questions').")

    # dict 아닌 것 제거
    return [x for x in data if isinstance(x, dict)]


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    # stem
    stem = (item.get("stem") or item.get("question") or item.get("q_text") or "")
    stem = str(stem).strip()

    explanation = str(item.get("explanation") or "").strip()
    qtype = item.get("question_type", "MCQ")
    code = item.get("code", "")

    category = item.get("category") or item.get("topic") or None
    subcategory = item.get("subcategory") or item.get("subtopic") or None

    # options 표준화
    options_std = _normalize_options(item.get("options"))

    # 정렬키 (있으면)
    source_pages = item.get("source_pages")
    page_no = source_pages[0] if isinstance(source_pages, list) and source_pages else None
    page_legacy = item.get("page")

    q_no_on_page = item.get("q_no_on_page")
    global_no = item.get("global_no") or item.get("question_id")

    # 이미지
    images = item.get("images") or item.get("image_urls") or []
    if not isinstance(images, list):
        images = []

    # steps 정답
    answer_steps = _infer_steps_answer_keys(item, options_std)

    # 일반 정답 key들
    answer_keys = []
    if not answer_steps:
        if isinstance(item.get("answer_keys"), list):
            answer_keys = [str(x).strip() for x in item["answer_keys"] if str(x).strip()]
        else:
            answer_keys = _to_list_answer_keys(item.get("answer"))

    return {
        "stem": stem,
        "explanation": explanation,
        "question_type": qtype,
        "category": category,
        "subcategory": subcategory,
        "code": code,

        "options_std": options_std,

        "page": page_legacy,
        "page_no": page_no,
        "q_no_on_page": q_no_on_page,
        "global_no": global_no,

        "answer_keys": answer_keys,
        "answer_steps": answer_steps,

        # 레거시 유지
        "pairs": item.get("pairs"),
        "sequence": item.get("sequence"),

        "images": images,
        "raw_answer": item.get("answer"),
    }


# -----------------------------
# Ingest
# -----------------------------
def ingest_questions(json_path: str, source_name: str = "imported", rebuild_db: bool = False) -> int:
    """
    ✅ 현재 db.py/init_db()와 호환되는 통합 ingest
    - rebuild_db=True: DB 파일 삭제 후 init_db()로 새로 생성
    """
    json_path = str(json_path)

    if rebuild_db and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"[INFO] 🧹 Deleted DB: {DB_PATH}")

    # ✅ 현재 db.py는 인자 없는 init_db()만 지원
    init_db()

    rows = _load_json(json_path)

    db = SessionLocal()
    try:
        count = 0

        for raw in rows:
            qn = _normalize_item(raw)

            q = Question(
                page=qn["page"],
                stem=qn["stem"],
                explanation=qn["explanation"],
                question_type=qn["question_type"],
                category=qn["category"],
                subcategory=qn["subcategory"],
                source=source_name,
                code=qn["code"],
            )

            # (확장 모델이면) 정렬키 저장
            if hasattr(q, "page_no"):
                q.page_no = qn["page_no"]
            if hasattr(q, "q_no_on_page"):
                q.q_no_on_page = qn["q_no_on_page"]
            if hasattr(q, "global_no"):
                q.global_no = qn["global_no"]

            # ✅ options는 표준 list[dict]로 저장 (web 표시 안정화)
            q.set_options(qn["options_std"])

            # ✅ Steps 정답 처리
            if qn["answer_steps"]:
                if hasattr(q, "set_answer_steps"):
                    q.set_answer_steps(qn["answer_steps"])
                    q.answer = ""  # 확장 컬럼 쓰는 경우 레거시 비워도 OK
                else:
                    # 구버전 fallback: sequence에 steps key 리스트 저장
                    q.sequence = json.dumps(qn["answer_steps"], ensure_ascii=False)
                    q.answer = ""  # steps는 answer 문자열 비교가 의미 없음

            else:
                # ✅ 일반 정답(복수/중복 포함)
                if qn["answer_keys"]:
                    if hasattr(q, "set_answer_keys"):
                        q.set_answer_keys(qn["answer_keys"])
                        q.answer = ""
                    else:
                        # 구버전 fallback: answer="A,B,C" (중복도 그대로)
                        q.answer = ",".join(qn["answer_keys"])
                else:
                    # 정답이 애매하면 원본 유지
                    q.answer = str(qn["raw_answer"] or "").strip()

                # 레거시 pairs/sequence 유지(있으면)
                if qn["sequence"] is not None:
                    q.sequence = json.dumps(qn["sequence"], ensure_ascii=False) if isinstance(qn["sequence"], list) else qn["sequence"]
                if qn["pairs"] is not None:
                    q.pairs = json.dumps(qn["pairs"], ensure_ascii=False) if isinstance(qn["pairs"], (dict, list)) else qn["pairs"]

            # ✅ images 저장(확장 모델이면)
            if hasattr(q, "set_images"):
                q.set_images(qn["images"])

            db.add(q)
            count += 1

        db.commit()
        print(f"[INFO] ✅ {count} 문항 DB 적재 완료 ({source_name})")
        return count

    except Exception as e:
        db.rollback()
        print(f"[ERROR] DB 적재 중 오류 발생 → {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    # 너가 말한 실제 경로: data/questions.json
    path = os.getenv("QUESTIONS_JSON", "data/questions.json")
    source = os.getenv("SOURCE_NAME", "az104_dump")
    rebuild = os.getenv("REBUILD_DB", "0") == "1"

    ingest_questions(path, source_name=source, rebuild_db=rebuild)

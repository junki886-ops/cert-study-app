# ==============================================
# app.py — CBT + REVIEW(⭐) + WRONG + 통합 노트 + OCR Parser (최적화 + 자동 DB화 완성본)
# ==============================================

import os
import json
from datetime import datetime

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

from db import init_db, SessionLocal
from models import Question, Attempt
from ingest import ingest_questions

try:
    from pdf_parser_adaptive import parse_pdf as _parse_pdf
except Exception:
    _parse_pdf = None

load_dotenv()
app = Flask(__name__)

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
PARSED_DIR = os.path.join(DATA_DIR, "parsed_json")
for d in [DATA_DIR, UPLOAD_DIR, PARSED_DIR]:
    os.makedirs(d, exist_ok=True)

DEFAULT_USER = "default"

# -----------------------------
# DB init (패치/구버전 모두 호환)
# -----------------------------
try:
    init_db(apply_light_migrations=True)
except TypeError:
    init_db()


# -----------------------------
# Utils
# -----------------------------
def normalize_options(raw):
    """
    어떤 형태로 저장되어 있어도 "표시용 문자열 리스트"로 변환.
    - 표준: [{"key":"A","text":"..."}] -> ["A. ...", ...]
    - 레거시: {"A":"..."} -> ["A. ...", ...]
    - 레거시: ["...","..."] -> 그대로
    """
    if not raw:
        return []

    # 표준: list[dict]
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        out = []
        for o in raw:
            k = str(o.get("key", "")).strip()
            t = str(o.get("text", "")).strip()
            if k and t:
                out.append(f"{k}. {t}")
            elif t:
                out.append(t)
            elif k:
                out.append(k)
        return out

    # 레거시: dict
    if isinstance(raw, dict):
        try:
            return [f"{k}. {v}" for k, v in sorted(raw.items(), key=lambda kv: kv[0])]
        except Exception:
            return [str(raw)]

    # 레거시: list[str]
    if isinstance(raw, list):
        return [str(x) for x in raw]

    return []


def parse_pdf_wrapper(pdf_path):
    if not _parse_pdf:
        raise RuntimeError("pdf_parser_adaptive 모듈이 없습니다.")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = os.path.join(PARSED_DIR, f"parsed_{ts}.json")
    _parse_pdf(pdf_path, out_json, use_llm=True, lang="korean", dpi=200)
    return out_json


def first_question(db):
    """
    첫 문제 선택:
    - page_no/q_no_on_page/global_no 컬럼이 있으면 PDF 순서로
    - 없으면 id로
    """
    q = db.query(Question)
    if hasattr(Question, "page_no") and hasattr(Question, "q_no_on_page"):
        return q.order_by(
            Question.page_no.asc().nulls_last(),
            Question.q_no_on_page.asc().nulls_last(),
            Question.id.asc()
        ).first()
    if hasattr(Question, "global_no"):
        return q.order_by(
            Question.global_no.asc().nulls_last(),
            Question.id.asc()
        ).first()
    return q.order_by(Question.id.asc()).first()


def api_payload(db, q: Question):
    """
    기존 프론트 호환 필드 유지 + 신규 필드(있으면)만 추가
    """
    total = db.query(Question).count()
    payload = {
        "id": q.id,
        "question": q.stem,
        "options": normalize_options(q.get_options()),
        "answer": q.answer,  # 레거시 유지
        "explanation": q.explanation,
        "total": total,
    }

    # 신규(모델이 지원할 때만)
    if hasattr(q, "get_answer_keys"):
        payload["answer_keys"] = q.get_answer_keys()
    if hasattr(q, "get_answer_steps"):
        payload["answer_steps"] = q.get_answer_steps()
    if hasattr(q, "get_images"):
        payload["images"] = q.get_images()

    # 순서 메타(있을 때만)
    if hasattr(q, "page_no"):
        payload["page_no"] = q.page_no
    if hasattr(q, "q_no_on_page"):
        payload["q_no_on_page"] = q.q_no_on_page
    if hasattr(q, "global_no"):
        payload["global_no"] = q.global_no

    return payload


def is_correct(q: Question, chosen):
    """
    최소 변경으로 정답 판정 개선:
    - models.py에 get_answer_keys/get_answer_steps 있으면 그걸 우선 사용
    - 없으면 레거시 answer(string)로 비교
    """
    # chosen 표준화 (string/list 모두 허용)
    if isinstance(chosen, list):
        chosen_list = [str(x).strip().upper() for x in chosen if str(x).strip()]
    else:
        s = str(chosen).strip()
        if "," in s:
            chosen_list = [x.strip().upper() for x in s.split(",") if x.strip()]
        else:
            chosen_list = [s.upper()] if s else []

    # Steps 우선
    if hasattr(q, "get_answer_steps"):
        ans_steps = [str(x).strip().upper() for x in (q.get_answer_steps() or [])]
        if ans_steps:
            return chosen_list == ans_steps  # 순서/중복까지 동일

    # 복수정답(중복 포함) 우선
    if hasattr(q, "get_answer_keys"):
        ans_keys = [str(x).strip().upper() for x in (q.get_answer_keys() or [])]
        if ans_keys:
            from collections import Counter
            return Counter(chosen_list) == Counter(ans_keys)

    # 레거시 단일 비교
    return str(chosen).strip().upper() == str(q.answer or "").strip().upper()


def auto_ingest_json_if_empty(json_path="data/questions.json", source_name="az104_dump"):
    """
    ✅ 서버 시작 시 자동 DB화:
    - DB에 문제가 0개면 json_path를 자동 ingest
    - DB 삭제 후 재실행해도 자동으로 다시 쌓임
    """
    # JSON 존재 확인
    abs_json = json_path if os.path.isabs(json_path) else os.path.join(BASE_DIR, json_path)
    if not os.path.exists(abs_json):
        print(f"[WARN] JSON not found: {abs_json}")
        return

    db = SessionLocal()
    try:
        n = db.query(Question).count()
    finally:
        db.close()

    if n > 0:
        print(f"[INFO] DB already has {n} questions. skip auto ingest.")
        return

    print(f"[INFO] AUTO INGEST start: {abs_json}")
    inserted = ingest_questions(abs_json, source_name=source_name)
    print(f"[INFO] AUTO INGEST done: inserted={inserted}")


# ✅ 여기서 자동 ingest 실행 (원하는 경로: data/questions.json)
auto_ingest_json_if_empty("data/questions.json", "az104_dump")


# -----------------------------
# Pages
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/quiz")
def quiz():
    return render_template("quiz.html")


@app.route("/review")
def review():
    return render_template("review.html")


@app.route("/wrong")
def wrong():
    return render_template("wrong.html")


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


# -----------------------------
# Admin: upload pdf -> parse -> ingest
# -----------------------------
@app.route("/admin/upload", methods=["GET", "POST"])
def upload_pdf():
    if request.method == "GET":
        return render_template("upload.html")

    f = request.files.get("file")
    if not f:
        return jsonify({"error": "file 누락"}), 400

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(UPLOAD_DIR, f"{ts}_{f.filename}")
    f.save(save_path)

    try:
        out_json = parse_pdf_wrapper(save_path)
        inserted = ingest_questions(out_json, source_name=f.filename)
        return jsonify({"ok": True, "inserted": inserted})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# -----------------------------
# API: question
# - ✅ id 없거나/없는 id면 첫 문제 fallback (DB 삭제 후 404 방지)
# -----------------------------
@app.route("/api/question", methods=["GET"])
def api_question():
    qid = request.args.get("id", type=int)
    db = SessionLocal()
    try:
        q = None
        if qid:
            q = db.query(Question).filter(Question.id == qid).first()

        if not q:
            q = first_question(db)

        if not q:
            return jsonify({"error": "문제 없음"}), 404

        return jsonify(api_payload(db, q))
    finally:
        db.close()


# -----------------------------
# API: answer
# - ✅ chosen list/string 둘 다 허용 + (가능하면) 복수/순서 정답 판정
# -----------------------------
@app.route("/api/answer", methods=["POST"])
def api_answer():
    data = request.get_json(force=True) or {}
    qid = data.get("question_id")
    chosen = data.get("chosen")
    user_id = str(data.get("user_id", DEFAULT_USER))

    if not qid or chosen is None:
        return jsonify({"error": "question_id 또는 chosen 누락"}), 400

    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == int(qid)).first()
        if not q:
            return jsonify({"error": "해당 문제 없음"}), 404

        correct = is_correct(q, chosen)

        chosen_store = json.dumps(chosen, ensure_ascii=False) if isinstance(chosen, list) else str(chosen)

        db.add(Attempt(
            user_id=user_id,
            question_id=q.id,
            chosen=chosen_store,
            correct=bool(correct),
            note_type="wrong" if not correct else None
        ))
        db.commit()

        return jsonify({"correct": bool(correct), "answer": q.answer, "explanation": q.explanation})
    finally:
        db.close()


# -----------------------------
# API: next
# - ✅ 최소 수정: current_id 없으면 첫 문제
# - (PDF 순서 next까지 완전 구현은 코드가 길어져서, 여기선 레거시 id-next 유지)
# -----------------------------
@app.route("/api/next", methods=["GET"])
def api_next():
    current_id = request.args.get("current_id", type=int, default=None)
    db = SessionLocal()
    try:
        if not current_id:
            q = first_question(db)
            if not q:
                return jsonify({"end": True})
            return jsonify(api_payload(db, q))

        nxt = (
            db.query(Question)
            .filter(Question.id > current_id)
            .order_by(Question.id.asc())
            .first()
        )
        if not nxt:
            return jsonify({"end": True})

        return jsonify(api_payload(db, nxt))
    finally:
        db.close()


# -----------------------------
# Review add/remove
# -----------------------------
@app.route("/api/review_add", methods=["POST"])
def review_add():
    data = request.get_json(force=True) or {}
    qid = data.get("question_id")
    user_id = str(data.get("user_id", DEFAULT_USER))
    db = SessionLocal()
    try:
        db.add(Attempt(user_id=user_id, question_id=int(qid), correct=False, note_type="review"))
        db.commit()
        return jsonify({"message": "⭐ 복습 목록에 추가됨"})
    finally:
        db.close()


@app.route("/api/review_remove", methods=["POST"])
def review_remove():
    data = request.get_json(force=True) or {}
    qid = data.get("question_id")
    user_id = str(data.get("user_id", DEFAULT_USER))
    db = SessionLocal()
    try:
        db.query(Attempt).filter(
            Attempt.user_id == user_id,
            Attempt.question_id == int(qid),
            Attempt.note_type == "review"
        ).delete()
        db.commit()
        return jsonify({"message": "🗑️ 복습에서 제거됨"})
    finally:
        db.close()


# ✅ 오답 + 복습 통합 조회 (기존 그대로 유지)
@app.route("/api/wrong_review", methods=["GET"])
def wrong_review():
    user_id = request.args.get("user_id", DEFAULT_USER)
    db = SessionLocal()
    try:
        rows = (
            db.query(Attempt, Question)
            .join(Question, Attempt.question_id == Question.id)
            .filter(Attempt.user_id == user_id, Attempt.note_type.in_(["wrong", "review"]))
            .order_by(Attempt.id.desc())
            .all()
        )

        seen = set()
        items = []
        for att, q in rows:
            if q.id in seen:
                continue
            seen.add(q.id)
            items.append({
                "question_id": q.id,
                "stem": q.stem,
                "options": q.get_options(),
                "answer": q.answer,
                "explanation": q.explanation,
                "chosen": att.chosen
            })

        return jsonify({"count": len(items), "items": items})
    finally:
        db.close()


# ✅ 오답에서 제거 (기존 그대로 유지)
@app.route("/api/wrong_remove", methods=["POST"])
def wrong_remove():
    data = request.get_json(force=True) or {}
    qid = data.get("question_id")
    user_id = str(data.get("user_id", DEFAULT_USER))
    db = SessionLocal()
    try:
        db.query(Attempt).filter(
            Attempt.user_id == user_id,
            Attempt.question_id == int(qid),
            Attempt.note_type == "wrong"
        ).delete()
        db.commit()
        return jsonify({"message": "🗑️ 오답에서 제거됨"})
    finally:
        db.close()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    print(f"[INFO] 서버 시작: 0.0.0.0:{port} (HF/로컬 공통)")
    app.run(host="0.0.0.0", port=port, debug=False)

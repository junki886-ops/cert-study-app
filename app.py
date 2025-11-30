# ==============================================
# app.py — CBT + REVIEW(⭐) + WRONG + 통합 노트 + OCR Parser (확정 안정 전체 버전)
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
except:
    _parse_pdf = None

load_dotenv()
app = Flask(__name__)
init_db()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
PARSED_DIR = os.path.join(DATA_DIR, "parsed_json")
for d in [DATA_DIR, UPLOAD_DIR, PARSED_DIR]:
    os.makedirs(d, exist_ok=True)

DEFAULT_USER = "default"


def normalize_options(raw):
    if not raw:
        return []
    try:
        if isinstance(raw, dict):
            return [f"{k}. {v}" for k, v in sorted(raw.items(), key=lambda kv: kv[0])]
        if isinstance(raw, list):
            return raw
    except:
        pass
    return []


def parse_pdf_wrapper(pdf_path):
    if not _parse_pdf:
        raise RuntimeError("pdf_parser_adaptive 모듈이 없습니다.")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = os.path.join(PARSED_DIR, f"parsed_{ts}.json")
    _parse_pdf(pdf_path, out_json, use_llm=True, lang="korean", dpi=200)
    return out_json


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


@app.route("/api/question", methods=["GET"])
def api_question():
    qid = request.args.get("id")
    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == int(qid)).first() if qid \
            else db.query(Question).order_by(Question.id.asc()).first()
        if not q:
            return jsonify({"error": "문제 없음"}), 404

        total = db.query(Question).count()
        return jsonify({
            "id": q.id,
            "question": q.stem,
            "options": normalize_options(q.get_options()),
            "answer": q.answer,
            "explanation": q.explanation,
            "total": total
        })
    finally:
        db.close()


@app.route("/api/answer", methods=["POST"])
def api_answer():
    data = request.get_json(force=True) or {}
    qid = data.get("question_id")
    chosen = data.get("chosen")
    user_id = str(data.get("user_id", DEFAULT_USER))

    if not qid or not chosen:
        return jsonify({"error": "question_id 또는 chosen 누락"}), 400

    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == int(qid)).first()
        correct = (str(chosen).upper() == str(q.answer).upper())

        db.add(Attempt(
            user_id=user_id,
            question_id=q.id,
            chosen=str(chosen),
            correct=bool(correct),
            note_type="wrong" if not correct else None
        ))
        db.commit()

        return jsonify({"correct": bool(correct), "answer": q.answer, "explanation": q.explanation})
    finally:
        db.close()


@app.route("/api/next", methods=["GET"])
def api_next():
    current_id = int(request.args.get("current_id", 1))
    db = SessionLocal()
    try:
        nxt = (
            db.query(Question)
            .filter(Question.id > current_id)
            .order_by(Question.id.asc())
            .first()
        )
        if not nxt:
            return jsonify({"end": True})

        total = db.query(Question).count()
        return jsonify({
            "id": nxt.id,
            "question": nxt.stem,
            "options": normalize_options(nxt.get_options()),
            "answer": nxt.answer,
            "explanation": nxt.explanation,
            "total": total
        })
    finally:
        db.close()


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


# ✅ 오답 + 복습 통합 조회
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


# ✅ 오답에서 제거 (복습에서도 제거)
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
    print("[INFO] http://127.0.0.1:5000 실행 중")
    app.run(host="0.0.0.0", port=5000, debug=True)

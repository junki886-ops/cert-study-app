import os, json
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# 내부 모듈
from db import init_db, SessionLocal
from models import Question, Attempt
from pdf_parser import parse_pdf
from ingest import ingest_questions
from similarity import similar_questions

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
init_db()

UPLOAD_DIR = "./data/uploads"
DATA_DIR = "./data"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------
# 홈
# -----------------------
@app.route("/")
def home():
    return render_template("index.html")


# -----------------------
# 관리자: PDF 업로드 → OCR+LLM 파싱 → JSON 저장 → DB 적재
# -----------------------
@app.route("/admin/upload", methods=["GET", "POST"])
def upload_pdf():
    if request.method == "GET":
        return render_template("upload.html")

    if "file" not in request.files:
        return jsonify({"error": "file form-data 누락"}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "PDF만 허용"}), 400

    save_path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(save_path)

    # (1) OCR+LLM 파싱 → JSON 생성
    output_json = os.path.join(DATA_DIR, "questions.json")
    items = parse_pdf(save_path, output_json)

    if not items:
        return jsonify({"message": "파싱된 문항 0건"}), 200

    # (2) JSON → DB 적재
    count = ingest_questions(output_json, source_name=f.filename)

    return jsonify({
        "message": "업로드/파싱/DB 저장 완료",
        "count": count,
        "filename": f.filename
    })


# -----------------------
# 문제풀이 UI
# -----------------------
@app.route("/quiz")
def quiz():
    return render_template("quiz.html")


# -----------------------
# 오답노트 UI
# -----------------------
@app.route("/wrong")
def wrong_page():
    return render_template("wrong.html")


# -----------------------
# 문제 조회 API
# -----------------------
@app.route("/api/question", methods=["GET"])
def get_question():
    qid = request.args.get("id", type=int)
    category = request.args.get("category")
    subcategory = request.args.get("subcategory")

    db = SessionLocal()
    try:
        q = None
        if qid:
            q = db.get(Question, qid)
        else:
            query = db.query(Question)
            if category:
                query = query.filter(Question.category == category)
            if subcategory:
                query = query.filter(Question.subcategory == subcategory)
            q = query.order_by(Question.id.asc()).first()

        if not q:
            return jsonify({"error": "문항 없음"}), 404

        return jsonify({
            "id": q.id,
            "question": q.stem,
            "options": q.get_options(),   # ✅ 보완
            "category": q.category,
            "subcategory": q.subcategory,
            "total": db.query(Question).count()
        })
    finally:
        db.close()


# -----------------------
# 다음 문제 API
# -----------------------
@app.route("/api/next", methods=["GET"])
def next_question():
    current_id = request.args.get("current_id", default=0, type=int)
    category = request.args.get("category")
    subcategory = request.args.get("subcategory")

    db = SessionLocal()
    try:
        query = db.query(Question).filter(Question.id > current_id)
        if category:
            query = query.filter(Question.category == category)
        if subcategory:
            query = query.filter(Question.subcategory == subcategory)
        q = query.order_by(Question.id.asc()).first()

        if not q:
            return jsonify({"end": True, "message": "마지막 문제"}), 200

        return jsonify({
            "id": q.id,
            "question": q.stem,
            "options": q.get_options(),   # ✅ 보완
            "category": q.category,
            "subcategory": q.subcategory
        })
    finally:
        db.close()


# -----------------------
# 채점 API
# -----------------------
@app.route("/api/answer", methods=["POST"])
def answer():
    data = request.get_json(force=True)
    qid = int(data["question_id"])
    chosen = str(data["chosen"]).strip()
    user_id = data.get("user_id", "default")
    note_type = data.get("note_type", "wrong")  # wrong / review

    db = SessionLocal()
    try:
        q = db.get(Question, qid)
        if not q:
            return jsonify({"error": "문항 없음"}), 404

        correct = (chosen == (q.answer or ""))

        # 시도 기록 저장
        attempt = Attempt(
            user_id=user_id,
            question_id=q.id,
            chosen=chosen,
            correct=correct,
            note_type=note_type
        )
        db.add(attempt)
        db.commit()

        # 유사 문제 추천
        base_text = (q.stem or "") + "\n" + (" ".join(q.get_options().values()))
        sims = similar_questions(
            base_text, k=3, exclude_db_id=q.id,
            category=q.category, subcategory=q.subcategory
        )

        return jsonify({
            "correct": correct,
            "answer": q.answer,
            "explanation": q.explanation,
            "category": q.category,
            "subcategory": q.subcategory,
            "note_type": note_type,
            "similar": sims
        })
    finally:
        db.close()


# -----------------------
# 오답노트 API
# -----------------------
@app.route("/api/wrong_only", methods=["GET"])
def wrong_only():
    """내 오답노트 가져오기"""
    user_id = request.args.get("user_id", "default")

    db = SessionLocal()
    try:
        attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()
        result = []
        for a in attempts:
            q = db.get(Question, a.question_id)
            if not q: 
                continue
            result.append({
                "question_id": q.id,
                "stem": q.stem,
                "options": q.get_options(),   # ✅ 보완
                "chosen": a.chosen,
                "answer": q.answer,
                "explanation": q.explanation,
                "note_type": a.note_type
            })
        return jsonify(result)
    finally:
        db.close()


# -----------------------
# 복습노트에 수동 추가 API
# -----------------------
@app.route("/api/review_add", methods=["POST"])
def review_add():
    data = request.get_json(force=True)
    qid = int(data["question_id"])
    user_id = data.get("user_id", "default")

    db = SessionLocal()
    try:
        q = db.get(Question, qid)
        if not q:
            return jsonify({"error": "문항 없음"}), 404

        attempt = Attempt(
            user_id=user_id,
            question_id=q.id,
            chosen="(복습 추가)",
            correct=True,
            note_type="review"
        )
        db.add(attempt)
        db.commit()
        return jsonify({"message": "복습노트에 추가 완료"})
    finally:
        db.close()


# -----------------------
# 실행
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)

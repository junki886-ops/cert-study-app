import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from db import init_db, SessionLocal, Question, Attempt
from ocr_parse import parse_pdf
from ingest import ingest_questions
from similarity import similar_questions

load_dotenv()
app = Flask(__name__)
init_db()

UPLOAD_DIR = "./data/uploads"
IMAGE_DIR = "./data/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

@app.route("/")
def home():
    return render_template("index.html")

# --- 관리자: PDF 업로드 (GET: 업로드 페이지, POST: 업로드 처리) ---
@app.route("/admin/upload", methods=["GET","POST"])
def upload_pdf():
    print(">>> 요청 방식:", request.method)  # 디버깅용 출력

    if request.method == "GET":
        # 업로드 페이지 렌더링
        return render_template("upload.html")

    # POST 처리 (파일 업로드)
    if "file" not in request.files:
        return jsonify({"error": "file form-data 누락"}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "PDF만 허용"}), 400

    save_path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(save_path)

    items = parse_pdf(save_path, IMAGE_DIR)
    if not items:
        return jsonify({"message": "파싱된 문항 0건"}), 200

    ingest_questions(items, source_name=f.filename)
    return jsonify({"message": "업로드/파싱/적재 완료", "count": len(items)})

# --- 조건부 문항 조회 ---
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
            "id": q.id, "qno": q.qno, "stem": q.stem, "options": q.options,
            "category": q.category, "subcategory": q.subcategory
        })
    finally:
        db.close()

# --- 다음 문제 ---
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
            "id": q.id, "qno": q.qno, "stem": q.stem, "options": q.options,
            "category": q.category, "subcategory": q.subcategory
        })
    finally:
        db.close()

# --- 채점 ---
@app.route("/api/answer", methods=["POST"])
def answer():
    data = request.get_json(force=True)
    qid = int(data["question_id"])
    chosen = str(data["chosen"]).strip()
    user_id = data.get("user_id", "default")

    db = SessionLocal()
    try:
        q = db.get(Question, qid)
        if not q:
            return jsonify({"error": "문항 없음"}), 404
        correct = (chosen == (q.answer or ""))

        db.add(Attempt(user_id=user_id, question_id=q.id, chosen=chosen, correct=correct))
        db.commit()

        base_text = (q.stem or "") + "\n" + (" ".join(q.options) if q.options else "")
        sims = similar_questions(
            base_text, k=3, exclude_db_id=q.id,
            category=q.category, subcategory=q.subcategory
        )
        return jsonify({
            "correct": correct,
            "answer": q.answer,
            "category": q.category,
            "subcategory": q.subcategory,
            "similar": sims
        })
    finally:
        db.close()

# --- 오답노트 ---
@app.route("/api/wrong_only", methods=["GET"])
def wrong_only():
    user_id = request.args.get("user_id", "default")
    category = request.args.get("category")
    subcategory = request.args.get("subcategory")

    db = SessionLocal()
    try:
        subq = """
            SELECT a1.question_id, a1.correct
            FROM attempts a1
            JOIN (
                SELECT question_id, MAX(created_at) AS max_time
                FROM attempts
                WHERE user_id = :uid
                GROUP BY question_id
            ) latest
              ON a1.question_id = latest.question_id AND a1.created_at = latest.max_time
            WHERE a1.user_id = :uid AND a1.correct = 0
        """
        ids = [row[0] for row in db.execute(subq, {"uid": user_id}).fetchall()]
        if not ids:
            return jsonify({"count": 0, "items": []})

        q = db.query(Question).filter(Question.id.in_(ids))
        if category:
            q = q.filter(Question.category == category)
        if subcategory:
            q = q.filter(Question.subcategory == subcategory)
        rows = q.order_by(Question.id.asc()).all()

        items = [{
            "id": r.id, "qno": r.qno, "stem": r.stem, "options": r.options,
            "category": r.category, "subcategory": r.subcategory
        } for r in rows]
        return jsonify({"count": len(items), "items": items})
    finally:
        db.close()


if __name__ == "__main__":
    app.run(debug=True)

# 실제 서비스는 embedding + vector DB (예: Chroma, FAISS) 추천
# 여기서는 단순 stem 텍스트 길이 유사도로 흉내만 냄

from db import SessionLocal, Question

def similar_questions(base_text, k=3, exclude_db_id=None, category=None, subcategory=None):
    db = SessionLocal()
    query = db.query(Question)
    if category:
        query = query.filter(Question.category == category)
    if subcategory:
        query = query.filter(Question.subcategory == subcategory)
    rows = query.all()
    db.close()

    scored = []
    for q in rows:
        if q.id == exclude_db_id:
            continue
        score = abs(len(base_text) - len((q.stem or "")))
        scored.append((score, q))

    scored.sort(key=lambda x: x[0])
    result = [{
        "id": r.id, "stem": r.stem, "options": r.options
    } for _, r in scored[:k]]
    return result

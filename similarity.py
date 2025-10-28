from db import SessionLocal
from models import Question

def similar_questions(base_text, k=3, exclude_db_id=None, category=None, subcategory=None):
    """간단히 같은 카테고리에서 몇 개 추천"""
    db = SessionLocal()
    try:
        query = db.query(Question)
        if category:
            query = query.filter(Question.category == category)
        if subcategory:
            query = query.filter(Question.subcategory == subcategory)
        if exclude_db_id:
            query = query.filter(Question.id != exclude_db_id)
        return [
            {"id": q.id, "stem": q.stem[:50]}
            for q in query.limit(k).all()
        ]
    finally:
        db.close()

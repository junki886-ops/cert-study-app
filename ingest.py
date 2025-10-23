import json
from db import SessionLocal, Question

def ingest_questions(items, source_name="manual"):
    """ OCR 파싱된 문제들을 DB에 적재 """
    db = SessionLocal()
    for item in items:
        q = Question(
            qno=item.get("qno"),
            stem=item.get("stem"),
            options=json.dumps(item.get("options"), ensure_ascii=False),
            answer=item.get("answer"),
            explanation=item.get("explanation"),
            category=item.get("category"),
            subcategory=item.get("subcategory"),
            source_name=source_name
        )
        db.add(q)
    db.commit()
    db.close()

import json
from db import SessionLocal
from models import Question

def ingest_questions(items, source_name="upload"):
    db = SessionLocal()
    try:
        for item in items:
            q = Question(
                stem=item.get("stem", ""),
                options=json.dumps(item.get("options", []), ensure_ascii=False),
                answer=item.get("answer"),
                explanation=item.get("explanation", "")
            )
            db.add(q)
        db.commit()
    finally:
        db.close()

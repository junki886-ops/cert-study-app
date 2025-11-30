from db import SessionLocal, Question

db = SessionLocal()
print("총 문항 수:", db.query(Question).count())
q = db.query(Question).first()
if q:
    print("첫 문제:", q.id, q.stem, q.options, q.answer)
db.close()

import json
from db import SessionLocal
from models import Question

def ingest_questions(json_path, source_name="upload"):
    """JSON 파일을 읽어와 DB에 적재"""
    db = SessionLocal()
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for item in data:
            q = Question(
                stem=item["stem"],
                answer=item.get("answer", ""),
                explanation=item.get("explanation", ""),
                category=item.get("category"),
                subcategory=item.get("subcategory"),
                source=source_name
            )
            # options 설정 (dict → JSON 문자열 변환)
            if isinstance(item.get("options"), dict):
                q.set_options(item["options"])
            elif isinstance(item.get("options"), list):
                # 만약 OCR/LLM에서 리스트로 뽑혔다면, A/B/C/D 키 매핑
                q.set_options({chr(65+i): opt for i, opt in enumerate(item["options"])})
            else:
                q.set_options({})

            db.add(q)
            count += 1

        db.commit()
        print(f"[INFO] DB 적재 완료: {count} 문항")
        return count
    finally:
        db.close()


if __name__ == "__main__":
    # 기본 실행 예시
    json_path = "data/questions.json"
    ingest_questions(json_path, source_name="sample.pdf")

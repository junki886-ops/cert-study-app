import json
from pathlib import Path

# 새 파트 파일
NEW_PART = Path("data/parsed_json/networking_final.json")

# 기존 통합본
QUESTIONS = Path("data/questions/questions.json")

# 폴더 자동 생성
QUESTIONS.parent.mkdir(parents=True, exist_ok=True)

# 기존 questions.json 읽기
if QUESTIONS.exists():
    with open(QUESTIONS, "r", encoding="utf-8") as f:
        existing = json.load(f)
else:
    existing = []

# 새 파트 로드
with open(NEW_PART, "r", encoding="utf-8") as f:
    new_data = json.load(f)

# append
existing.extend(new_data)

# 저장
with open(QUESTIONS, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print(f"✔ Append 완료 → 새 문제 {len(new_data)}개 추가됨")
print(f"✔ 전체 문제 수: {len(existing)}개")

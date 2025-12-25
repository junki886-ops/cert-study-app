# seed.py
import os, sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "cert_study.db")
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

schema_questions = """
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer   TEXT NOT NULL
);
"""

with sqlite3.connect(DB_PATH) as conn:
    c = conn.cursor()
    c.execute(schema_questions)
    data = [
        ("Azure VM의 OS 디스크 기본 유형은 무엇인가?", "Managed Disk"),
        ("AZ-104에서 IAM의 핵심 리소스(두 단어)는?", "Role Assignment"),
        ("VNet 간 통신 기능 이름은?", "VNet Peering"),
        ("객체 스토리지 서비스 이름은?", "Blob Storage"),
        ("리소스를 논리적으로 묶는 단위는?", "Resource Group"),
    ]
    c.executemany("INSERT INTO questions (question, answer) VALUES (?, ?)", data)
    conn.commit()

print("Seed 완료: instance/cert_study.db 에 샘플 문제 5개 삽입")

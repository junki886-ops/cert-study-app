---
title: Cert Study App
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8501
pinned: false
---

# Cert Study App

PDF 기반 자격증 문제를 파싱하고, 품질 검증을 거쳐 학습/오답/개념 정리를 돕는 Streamlit 앱입니다.

## 주요 기능

- PDF 문제 파싱 및 OCR/LLM 보조 파싱
- 파싱/청킹 품질 리포트 생성
- 품질 게이트 기반 DB 적재 보류/진행 판정
- 문제 풀이, 오답 복습, 취약 개념 학습
- 개념 분류와 개념 노트 관리
- Azure Docs 및 문제 벡터 색인
- Airflow 기반 백그라운드 파싱/이미지 분석 워크플로

## 실행

### Docker Compose

```bash
docker compose up --build
```

앱:

```text
http://localhost:8501
```

Airflow:

```text
http://localhost:8080
```

### 로컬 Streamlit

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/torch_stable.html
streamlit run streamlit_app.py
```

## 환경 변수

PostgreSQL 사용을 권장합니다.

```env
DATABASE_URL=postgresql+pg8000://USER:PASSWORD@HOST:5432/DB
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
OLLAMA_FAST_MODEL=qwen3.5:9b
OLLAMA_VISUAL_MODEL=qwen3-vl:8b-instruct-q4_K_M
EMBEDDING_MODEL=BAAI/bge-m3
```

SQLite fallback은 개발/데모 전용입니다. PostgreSQL 장애를 조용히 숨기지 않기 위해 기본값은 꺼져 있습니다.

```env
CERT_STUDY_DB_FALLBACK=1
```

## 배포 메모

GitHub/Hugging Face에는 소스 코드만 배포합니다. PDF, OCR 로그, 파싱 결과, SQLite DB, Chroma 인덱스, 이미지 crop은 런타임 산출물이므로 저장소에 포함하지 않습니다.


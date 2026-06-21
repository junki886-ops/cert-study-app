---
title: Cert Study Lab
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8501
pinned: false
---

# Cert Study Lab

자격증 시험 문제 PDF를 업로드하고, 파싱된 문제를 웹에서 풀 수 있도록 만드는 개인 개발 프로젝트입니다.

현재는 PDF 처리 파이프라인, 문제 저장, 문제 풀이 화면, 오답/복습 흐름, 개념 정리, 유사 문제 검색 구조를 함께 실험하고 있습니다. 최근에는 기존 문제풀이 기능 위에 `이어서 공부`, `집중 학습`, `시험 대비`, 로드맵, 이론 학습, 확인 퀴즈, 실습하기, 진도율 화면을 얹어 학습 플랫폼 형태로 확장하고 있습니다. MVP의 상위 Track은 `Azure`와 `Linux`이며, 각 Track 아래에 `AZ-104`, `LFCS` 같은 목표 자격증을 연결합니다. 기본 집중 Track은 `Linux · LFCS`입니다.

## 프로젝트 목적

자격증 문제 PDF는 사람이 직접 정리하기 번거롭습니다. 이 프로젝트는 PDF 안의 문제를 최대한 자동으로 구조화하고, 사용자가 웹에서 바로 풀고 복습할 수 있는 학습 환경을 만드는 것을 목표로 합니다.

## 주요 기능

- 시험별 PDF 업로드
- PDF 텍스트 파싱 및 일부 OCR/LLM 기반 보정 흐름
- 파싱 품질 검증 및 품질 게이트
- 문제, 정답, 해설, 풀이 기록 저장
- Streamlit 기반 문제풀이 화면
- 공통 지문, 원문 이미지, Yes/No 진술형 문제풀이 UI
- 문제 유형 표준화 및 정답 정규화 로직
- 오답/복습 화면
- 개념 정리 화면
- 단순 시작 홈과 별도 대시보드 화면
- 이어서 공부 / 집중 학습 / 시험 대비 모드 분리
- Azure / Linux 로드맵
- Azure 하위 AZ-104, Linux 하위 LFCS 계위
- AZ-104 대분류/세부개념 필터 기반 반복 풀이
- Git, Python, SQL, Docker, Kubernetes 확장 Track 구조
- Tool Docs Track: Ollama, LangChain, Streamlit, Hugging Face 공식 문서 학습
- 체크리스트형 기본 학습 흐름
- 일별 학습 기록, 연속 학습일, 주간 학습량 표시
- 마지막으로 선택한 Track 저장 및 재사용
- 이론, 퀴즈, 실습, 문제풀이, 오답 복습을 `오늘 누적 n단위`로 기록
- 세부개념 오답 기반 오늘 추천 복습
- 관리자 화면 안쪽 AZ-104 분류 검수
- 이론 카드와 확인 퀴즈 샘플
- Linux fake terminal 실습 샘플
- 시험 모드와 Track 진도율 기본 화면
- Chroma 기반 유사 문제 검색 구조
- Airflow 기반 PDF 처리 작업 관리
- Docker Compose 기반 로컬 실행 환경

## 기술 스택

| 영역 | 사용 기술 | 역할 |
| --- | --- | --- |
| 웹 UI | Streamlit | 문제 풀이, PDF 업로드, 처리 현황 확인 |
| 관계형 DB | PostgreSQL | 문제, 정답, 풀이 기록, 처리 작업 저장 |
| 벡터 DB | Chroma | 유사 문제 검색, 문서 검색용 임베딩 저장 |
| 워크플로 | Airflow | PDF 처리 파이프라인 실행과 추적 |
| 실행 환경 | Docker / Docker Compose | 앱, DB, Airflow 실행 환경 통일 |
| PDF 처리 | PyMuPDF, Parser, 선택적 LLM | PDF에서 문제 텍스트와 구조 추출 |

## 문서

처음 보는 사람은 아래 순서로 읽으면 전체 구조를 이해하기 쉽습니다.

1. [프로젝트 개요](docs/01_overview.md)
2. [전체 아키텍처](docs/02_architecture.md)
3. [데이터 파이프라인](docs/03_data_pipeline.md)
4. [데이터베이스 구조](docs/04_database.md)
5. [배포 계획](docs/05_deployment.md)
6. [의사결정 기록](docs/06_decision_log.md)
7. [트러블슈팅](docs/07_troubleshooting.md)
8. [GitHub / Hugging Face 배포 자동화](docs/08_publish_automation.md)
9. [모바일 앱처럼 사용하기](docs/09_mobile_pwa.md)
10. [Cert Study Lab 확장 프롬프트](docs/10_cert_study_lab_prompt.md)
11. [개발일지](docs/devlog/2026-06-07.md)
12. [변경 이력](CHANGELOG.md)

## 실행 방법

Docker가 설치되어 있다면 아래 명령으로 실행합니다.

```bash
cp .env.example .env
docker compose up --build
```

실행 후 접속 주소:

- Streamlit 앱: `http://localhost:8501`
- Airflow 웹서버: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

로컬에서 Streamlit만 빠르게 확인할 때는 임시 SQLite DB를 사용할 수 있습니다.

```bash
DATABASE_URL=sqlite:////tmp/cert-study-local-check.db \
  python -m streamlit run streamlit_app.py
```

## 배포용 문제 데이터

Hugging Face Space에는 로컬 DB나 PDF 원본을 올리지 않고, `cert_study_app/demo_data/questions_seed.json`과 `static/question_assets/`의 참조 이미지를 사용합니다.

현재 배포용 seed는 321문항, 공통 지문 포함 36문항, 원문 이미지, Yes/No 진술형 문제 UI에 필요한 구조를 포함합니다. seed는 아래 명령으로 다시 만들 수 있습니다.

```bash
python scripts/export_hf_seed.py
```

## 변경 이력 확인

Git 커밋은 날짜와 함께 남기 때문에 일자별 변경 내용을 확인할 수 있습니다.

```bash
scripts/git_daily_changes.sh 2026-06-07
```

## 테스트

문제 유형이 다양하기 때문에 정답 처리 로직은 별도 테스트로 확인합니다.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests
```

배포 전에 핵심 품질 검사를 한 번에 실행할 수도 있습니다.

```bash
python scripts/check_quality.py
```

현재 우선 확인하는 범위:

- Yes/No 진술형 정답 정규화
- 복수 선택 정답 정렬
- 순서가 중요한 답안 보존
- `Hotspot (True/False)`, `Hotspot (Drag and Drop)` 같은 문제 유형 alias 표준화

## 환경 변수

기본 데이터베이스는 PostgreSQL입니다.

```env
DATABASE_URL=postgresql+pg8000://cert_study:cert_study@postgres:5432/cert_study
```

개발 중 임시로 SQLite fallback을 허용해야 할 때만 아래 값을 사용합니다.

```env
CERT_STUDY_DB_FALLBACK=1
```

## 현재 개발 상태

이 프로젝트는 개인 학습과 포트폴리오 기록을 겸한 개발 중 프로젝트입니다. 핵심 구조는 잡혀 있지만, 파싱 정확도 개선, 북마크, 시험별 통계, 안정적인 배포, 테스트 자동화는 계속 개선할 예정입니다.

## 향후 개선할 기능

- 북마크 기능
- 시험별 진도율과 정답률 통계
- 파싱 실패 문제의 검수 화면 개선
- 문제 중복 감지 및 재업로드 처리
- Oracle Cloud Ubuntu 서버 배포
- 배포용 환경 변수와 비밀값 관리 정리
- 테스트 범위 확대와 CI/CD 추가

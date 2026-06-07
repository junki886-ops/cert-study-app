# 04. 데이터베이스 구조

## 데이터 저장 방식

이 프로젝트는 PostgreSQL과 Chroma를 함께 사용합니다.

두 저장소는 목적이 다릅니다.

| 저장소 | 역할 |
| --- | --- |
| PostgreSQL | 문제, 정답, 해설, 풀이 기록처럼 정확히 보관해야 하는 데이터 저장 |
| Chroma | 유사 문제 검색을 위한 벡터 데이터 저장 |

## PostgreSQL을 쓰는 이유

PostgreSQL은 관계형 데이터베이스입니다. 정해진 테이블에 데이터를 저장하고, 필요한 데이터를 정확하게 조회하는 데 적합합니다.

이 프로젝트에서는 아래 데이터를 PostgreSQL에 저장합니다.

- 문제 본문
- 보기
- 정답
- 해설
- 문제 유형
- 시험명 또는 출처
- 풀이 기록
- 개념 정리
- PDF 처리 작업 상태

문제풀이 웹에서는 “정답이 무엇인지”, “사용자가 어떤 문제를 틀렸는지” 같은 정보가 정확해야 합니다. 이런 데이터는 Chroma보다 PostgreSQL에 저장하는 것이 적합합니다.

## 주요 테이블

현재 모델은 `cert_study_app/models.py`에 정의되어 있습니다.

### questions

문제 정보를 저장하는 핵심 테이블입니다.

주요 컬럼:

- `stem`: 문제 본문
- `answer`: 정답
- `explanation`: 해설
- `question_type`: 문제 유형
- `question_number`: 문제 번호
- `source`: 시험명 또는 파일 출처
- `raw_text`: 원본 파싱 텍스트
- `options_json`: 보기 데이터
- `quality_score`: 파싱 품질 점수
- `quality_status`: 파싱 품질 상태
- `chunk_key`: 청킹 식별자

PDF 파싱 결과가 문제 단위로 정리되면 이 테이블에 저장됩니다.

### attempts

사용자의 풀이 기록을 저장합니다.

주요 컬럼:

- `user_id`: 사용자 식별자
- `question_id`: 어떤 문제를 풀었는지
- `chosen`: 사용자가 고른 답
- `correct`: 정답 여부
- `note_type`: 오답노트 등 복습 상태

현재는 개인 프로젝트이므로 기본 사용자 흐름을 기준으로 구성되어 있습니다.

### concept_notes

개념 정리 데이터를 저장합니다.

주요 컬럼:

- `concept_name`: 개념 이름
- `summary`: 개념 요약
- `exam_point`: 시험에서 중요한 포인트
- `trap_point`: 헷갈리기 쉬운 포인트
- `keywords`: 관련 키워드
- `source_question_id`: 어떤 문제에서 나온 개념인지

### ingestion_jobs

PDF 처리 작업 상태를 저장합니다.

주요 컬럼:

- `exam_name`: 시험명
- `pdf_path`: PDF 경로
- `status`: 작업 상태
- `stage`: 현재 처리 단계
- `current`, `total`: 진행률 계산용 값
- `inserted`: 저장된 문제 수
- `quality_score`: 품질 점수
- `quality_report_json`: 품질 리포트 경로
- `quality_gate_json`: 품질 게이트 결과 경로
- `error_message`: 오류 메시지

이 테이블 덕분에 PDF 처리 현황 화면을 만들 수 있습니다.

### azure_docs_syncs

외부 문서 색인 상태를 기록하기 위한 테이블입니다.

주요 컬럼:

- `embedding_model`
- `status`
- `urls_checked`
- `documents_indexed`
- `chunks_indexed`

## Chroma를 쓰는 이유

Chroma는 벡터 데이터베이스입니다. 텍스트를 숫자 벡터로 바꾼 뒤, 의미가 비슷한 데이터를 찾는 데 사용합니다.

예를 들어 사용자가 어떤 문제를 풀고 있을 때, Chroma를 이용하면 다음과 같은 기능을 만들 수 있습니다.

- 현재 문제와 비슷한 문제 찾기
- 같은 개념을 묻는 문제 찾기
- 공식 문서나 설명 자료에서 관련 내용 찾기

## PostgreSQL과 Chroma를 함께 쓰는 이유

PostgreSQL은 정확한 저장과 조회에 강하고, Chroma는 의미 기반 검색에 강합니다.

따라서 두 저장소를 이렇게 나눠 쓰는 것이 좋습니다.

- PostgreSQL: 원본 데이터의 기준 저장소
- Chroma: 검색을 빠르게 하기 위한 보조 색인

즉, Chroma는 PostgreSQL을 대체하는 저장소가 아닙니다. Chroma 검색 결과는 다시 PostgreSQL의 문제 ID와 연결되어 실제 문제 데이터를 보여주는 방식이 좋습니다.

## SQLite에 대한 정리

현재 프로젝트는 PostgreSQL 사용을 기본으로 합니다.

SQLite는 개발 초기에 간단히 테스트하기 좋지만, Docker Compose와 Airflow까지 함께 쓰는 구조에서는 PostgreSQL을 기준으로 맞추는 편이 더 안정적입니다.

필요한 경우에만 `CERT_STUDY_DB_FALLBACK=1`로 SQLite fallback을 허용하는 방향이 적합합니다.

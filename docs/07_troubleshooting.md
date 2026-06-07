# 07. 트러블슈팅

이 문서는 개발 중 자주 만날 수 있는 문제와 확인 방법을 정리합니다.

## Docker가 실행되지 않을 때

### 증상

`docker compose up --build` 실행 시 Docker daemon 관련 오류가 발생합니다.

### 확인할 것

Docker Desktop이 실행 중인지 확인합니다.

```bash
docker info
```

### 해결 방향

- Docker Desktop을 실행한다.
- Docker가 완전히 시작된 뒤 다시 명령을 실행한다.
- 기존 컨테이너가 꼬였으면 `docker compose down` 후 다시 실행한다.

## Streamlit 앱에 접속되지 않을 때

### 증상

`http://localhost:8501`에 접속해도 화면이 열리지 않습니다.

### 확인할 것

컨테이너가 실행 중인지 확인합니다.

```bash
docker compose ps
```

로그를 확인합니다.

```bash
docker compose logs cert-study-app
```

### 해결 방향

- 앱 컨테이너가 종료되었는지 확인한다.
- 8501 포트를 다른 프로그램이 사용 중인지 확인한다.
- 필요하면 `http://127.0.0.1:8501`로도 접속해 본다.

## PostgreSQL 연결 오류

### 증상

앱 실행 중 데이터베이스 연결 오류가 발생합니다.

### 확인할 것

PostgreSQL 컨테이너 상태를 확인합니다.

```bash
docker compose ps postgres
```

로그를 확인합니다.

```bash
docker compose logs postgres
```

### 해결 방향

- `postgres` 컨테이너가 healthy 상태인지 확인한다.
- `DATABASE_URL`이 Docker Compose 설정과 일치하는지 확인한다.
- 로컬에서 직접 실행할 때는 host가 `postgres`가 아니라 `localhost`여야 할 수 있다.

## SQLite fallback 관련 혼동

### 증상

PostgreSQL을 쓰려고 했는데 SQLite 파일이 생기거나, 반대로 SQLite fallback이 되지 않습니다.

### 설명

현재 프로젝트는 PostgreSQL 사용을 기본으로 합니다. SQLite는 개발 중 임시 fallback 용도입니다.

### 해결 방향

PostgreSQL을 사용할 때:

```env
DATABASE_URL=postgresql+pg8000://cert_study:cert_study@postgres:5432/cert_study
```

SQLite fallback을 꼭 허용해야 할 때:

```env
CERT_STUDY_DB_FALLBACK=1
```

운영 또는 배포 환경에서는 PostgreSQL을 기준으로 맞추는 것이 좋습니다.

## Airflow 화면에 접속되지 않을 때

### 증상

`http://localhost:8080`에 접속해도 Airflow 화면이 열리지 않습니다.

### 확인할 것

```bash
docker compose ps airflow-webserver airflow-scheduler
```

```bash
docker compose logs airflow-webserver
```

### 해결 방향

- `airflow-init`이 먼저 실행되었는지 확인한다.
- 8080 포트를 다른 프로그램이 사용 중인지 확인한다.
- Airflow DB 마이그레이션 오류가 있는지 로그를 확인한다.

## PDF 처리 작업이 멈춘 것처럼 보일 때

### 증상

PDF 업로드 후 처리 현황이 오래 바뀌지 않습니다.

### 확인할 것

- Airflow DAG가 실행 중인지 확인한다.
- `ingestion_jobs`의 `stage`, `message`, `current`, `total` 값이 바뀌는지 확인한다.
- Airflow 로그에서 실패 단계가 있는지 확인한다.

### 해결 방향

- 큰 PDF는 파싱 시간이 오래 걸릴 수 있다.
- LLM 또는 이미지 분석을 켜면 더 느려질 수 있다.
- 실패한 경우 해당 작업의 오류 메시지를 먼저 확인한다.

## 문제 파싱 결과가 이상할 때

### 증상

문제 본문이 잘리거나, 보기가 빠지거나, 정답이 비어 있습니다.

### 확인할 것

- 품질 리포트가 생성되었는지 확인한다.
- `quality_score`, `quality_status`, `quality_issues` 값을 확인한다.
- 원본 PDF 텍스트 추출이 가능한 PDF인지 확인한다.

### 해결 방향

- 파싱 규칙을 개선한다.
- OCR이 필요한 PDF인지 확인한다.
- 문제 번호 패턴과 보기 패턴을 더 명확히 처리한다.
- 모든 문제를 LLM으로 처리하기보다, 실패 가능성이 높은 문제만 보정하는 방향이 좋다.

## Chroma 검색 결과가 이상할 때

### 증상

유사 문제가 잘 나오지 않거나, 검색 결과가 비어 있습니다.

### 확인할 것

- 문제가 Chroma에 색인되었는지 확인한다.
- 사용 중인 임베딩 모델이 색인할 때의 모델과 같은지 확인한다.
- `chroma_db` 디렉터리가 유지되고 있는지 확인한다.

### 해결 방향

- 같은 임베딩 모델로 다시 색인한다.
- 임베딩 모델별로 컬렉션을 분리한다.
- PostgreSQL에는 문제가 있는데 Chroma에만 없다면 색인 작업을 다시 실행한다.

## Ollama 또는 LLM 관련 오류

### 증상

LLM 파싱, 설명 생성, 이미지 분석 단계에서 오류가 발생합니다.

### 확인할 것

```bash
ollama list
```

### 해결 방향

- 필요한 모델이 설치되어 있는지 확인한다.
- Docker 컨테이너에서 접근하는 `OLLAMA_BASE_URL`이 맞는지 확인한다.
- LLM을 끄고 규칙 기반 파싱만으로 먼저 실행해 본다.

## Git에 올리면 안 되는 데이터

다음 데이터는 실행 중 생성되는 런타임 데이터이므로 보통 Git에 올리지 않습니다.

- 업로드 PDF
- 파싱 결과 JSON
- Chroma 인덱스
- PostgreSQL 데이터 볼륨
- Airflow 로그
- Airflow DB
- 개인 `.env` 파일

GitHub에는 코드와 문서, 설정 예시 중심으로 올리는 것이 좋습니다.

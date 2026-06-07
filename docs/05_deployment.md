# 05. 배포 계획

## 현재 실행 방식

현재 프로젝트는 Docker Compose로 로컬 실행 환경을 맞추는 구조입니다.

주요 서비스는 다음과 같습니다.

- `postgres`: PostgreSQL 데이터베이스
- `cert-study-app`: Streamlit 웹 앱
- `airflow-init`: Airflow 초기화
- `airflow-webserver`: Airflow 웹 화면
- `airflow-scheduler`: Airflow 작업 스케줄러

## 로컬 실행

```bash
docker compose up --build
```

접속 주소:

- Streamlit 앱: `http://localhost:8501`
- Airflow: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

## Docker를 쓰는 이유

이 프로젝트는 Streamlit, PostgreSQL, Airflow, PDF 처리 라이브러리, Chroma 등 여러 구성 요소를 함께 사용합니다.

개발 PC에서 직접 모두 설치하면 버전 충돌이 생기기 쉽습니다. Docker를 사용하면 실행 환경을 코드로 정리할 수 있고, 다른 PC나 서버에서도 비슷한 방식으로 실행할 수 있습니다.

Docker를 쓰는 이유는 다음과 같습니다.

- 실행 환경을 통일할 수 있다.
- PostgreSQL과 Airflow를 함께 띄우기 쉽다.
- 로컬 개발 환경과 서버 환경 차이를 줄일 수 있다.
- 배포할 때 필요한 명령을 단순화할 수 있다.

## Docker Compose 볼륨

현재 Compose에서는 런타임 데이터를 유지하기 위해 볼륨과 디렉터리를 사용합니다.

예시:

- `postgres_data`: PostgreSQL 데이터
- `./data`: 업로드 PDF, 파싱 결과 등 런타임 데이터
- `./chroma_db`: Chroma 인덱스
- `./airflow_logs`: Airflow 로그
- `./airflow_db`: Airflow 메타데이터

이런 파일은 실행 중 생성되는 데이터이므로 보통 Git에 올리지 않습니다.

## 환경 변수

기본 데이터베이스 연결은 PostgreSQL을 사용합니다.

```env
DATABASE_URL=postgresql+pg8000://cert_study:cert_study@postgres:5432/cert_study
```

LLM과 임베딩 관련 환경 변수 예시:

```env
CERT_STUDY_LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:14b
OLLAMA_FAST_MODEL=qwen3.5:9b
OLLAMA_VISUAL_MODEL=qwen3-vl:8b-instruct-q4_K_M
EMBEDDING_MODEL=BAAI/bge-m3
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

운영 배포에서는 비밀번호와 API 정보가 코드에 직접 들어가지 않도록 `.env` 또는 서버 비밀값 관리 방식을 사용해야 합니다.

## Oracle Cloud Ubuntu에 배포하려는 이유

향후 배포 대상은 Oracle Cloud Ubuntu 서버를 계획하고 있습니다.

이유는 다음과 같습니다.

- 개인 프로젝트를 외부에서 접속 가능한 형태로 운영해 볼 수 있다.
- Ubuntu 서버는 Docker 기반 배포 자료가 많아 학습하기 좋다.
- Streamlit, PostgreSQL, Airflow 같은 구성 요소를 한 서버에서 실험하기 쉽다.
- 포트폴리오 프로젝트로 실제 배포 경험을 남길 수 있다.

## 예상 배포 흐름

1. Oracle Cloud에서 Ubuntu 인스턴스를 생성한다.
2. 서버에 Docker와 Docker Compose를 설치한다.
3. GitHub 저장소를 서버에 clone한다.
4. `.env` 파일을 서버 환경에 맞게 작성한다.
5. `docker compose up -d --build`로 실행한다.
6. 방화벽과 보안 목록에서 필요한 포트를 연다.
7. 접속 주소를 확인한다.
8. 필요하면 Nginx와 HTTPS를 추가한다.

## 배포 전에 정리할 것

- 운영용 비밀번호 분리
- `.env.example` 정리
- PostgreSQL 데이터 백업 방식
- Chroma 인덱스 재생성 방식
- Airflow 관리자 계정 설정
- 업로드 파일 저장 위치
- 로그 관리
- HTTPS 적용 여부

## 현재 상태

현재는 Docker Compose 기반 로컬 실행 구조가 중심입니다. Oracle Cloud 배포는 향후 진행할 계획이며, 배포 전에 환경 변수, 데이터 볼륨, 보안 설정을 더 정리해야 합니다.

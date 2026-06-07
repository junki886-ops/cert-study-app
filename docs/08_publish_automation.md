# 08. GitHub / Hugging Face 배포 자동화

이 문서는 현재 프로젝트를 GitHub와 Hugging Face Space에 올리는 방법을 정리합니다.

## 목표

기본 흐름은 다음과 같습니다.

1. 로컬에서 GitHub로 push한다.
2. GitHub Actions가 실행된다.
3. GitHub Actions가 현재 프로젝트 파일을 Hugging Face Space로 동기화한다.

이렇게 하면 평소에는 GitHub에만 push해도 Hugging Face Space가 자동으로 업데이트됩니다.

Hugging Face는 10MiB가 넘는 일반 Git 파일을 거절할 수 있습니다. 그래서 이 프로젝트의 자동화는 GitHub의 전체 Git 히스토리를 그대로 밀어 넣지 않고, 현재 파일 스냅샷만 Hugging Face Space에 동기화합니다.

## 현재 원격 저장소

현재 프로젝트는 아래 remote를 사용합니다.

```bash
origin  https://github.com/junki886-ops/cert-study-app.git
hf      https://huggingface.co/spaces/Kentlo/cert-study-app
```

확인은 아래 명령으로 할 수 있습니다.

```bash
git remote -v
```

## 자동 동기화 방식

자동 동기화 파일은 아래 위치에 있습니다.

```text
.github/workflows/sync-huggingface.yml
```

이 workflow는 `main` 브랜치에 push가 발생하면 Hugging Face Space의 `main` 브랜치로 현재 파일을 동기화합니다.

동기화에서 제외하는 항목:

- `.github/`
- `.env`
- `.venv/`
- `*.pdf`
- `data/`
- `instance/`
- `chroma_db/`
- `airflow_logs/`
- `airflow_db/`

즉, GitHub에는 개발 히스토리를 남기고 Hugging Face에는 실행에 필요한 현재 스냅샷을 전달합니다.

Hugging Face Space에는 로컬 PostgreSQL 데이터, Chroma 인덱스, 업로드 PDF 원본을 올리지 않습니다. 대신 배포용 seed 파일을 만들어 DB가 비어 있을 때 자동으로 문제를 넣습니다.

현재 seed 우선순위는 다음과 같습니다.

1. `cert_study_app/demo_data/questions_seed.json`
2. `cert_study_app/demo_data/demo_questions.json`

실제 문제를 Hugging Face에서 풀 수 있게 하려면 로컬 원본 데이터에서 배포용 seed를 생성합니다.

```bash
python scripts/export_hf_seed.py
```

이 스크립트는 `data/Json/questions.json`을 기준 문제 데이터로 사용하고, `data/parsed_json/reparsed_multipage_images_20260601_205501.json`에서 공통 지문과 공통 지문 원문 이미지 정보를 보강합니다.

생성 결과:

- `cert_study_app/demo_data/questions_seed.json`
- `cert_study_app/demo_data/questions_seed.report.json`
- `static/question_assets/`

`dump.pdf` 전체나 `data/images/` 전체를 올리지 않고, 문제풀이와 원문 확인에 필요한 참조 이미지만 복사합니다. 현재 seed에는 321문항, 공통 지문, 원문 이미지, Yes/No 진술형 문제 구조가 포함됩니다.

push 전에 핵심 검사를 실행하면 유형 처리나 seed 리포트 오류를 먼저 잡을 수 있습니다.

```bash
python scripts/check_quality.py
```

`main` 브랜치에 push하면 `Quality Check` GitHub Actions가 먼저 실행되고, 같은 push 이벤트에서 Hugging Face 동기화 workflow도 실행됩니다.

실제 기출/덤프 성격의 문제를 포함하는 경우 Hugging Face Space는 private로 운영하는 것을 권장합니다.

데모 seed를 끄고 싶다면 실행 환경에 아래 값을 설정합니다.

```env
CERT_STUDY_SEED_DEMO=0
```

수동 실행도 가능합니다.

GitHub 저장소 화면에서:

1. `Actions` 탭으로 이동
2. `Sync to Hugging Face Space` 선택
3. `Run workflow` 실행

## 사용자가 해야 할 설정

### 1. Hugging Face Access Token 만들기

Hugging Face에서 Access Token을 생성합니다.

권한은 Space 저장소에 push할 수 있어야 합니다.

### 2. GitHub Secrets에 HF_TOKEN 추가

GitHub 저장소에서 아래 경로로 이동합니다.

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

아래 값으로 Secret을 추가합니다.

```text
Name: HF_TOKEN
Value: Hugging Face Access Token
```

토큰 값은 코드나 문서에 직접 적지 않습니다.

### 3. GitHub push 인증 설정

로컬에서 GitHub에 push하려면 GitHub 인증이 필요합니다.

방법 1: GitHub CLI 사용

```bash
brew install gh
gh auth login
git push origin main
```

방법 2: HTTPS token 또는 SSH key 사용

GitHub 계정에 맞게 Personal Access Token 또는 SSH key를 설정한 뒤 push합니다.

## 로컬에서 한 번에 둘 다 push하기

GitHub와 Hugging Face 양쪽 인증이 로컬에 되어 있다면 아래 스크립트를 사용할 수 있습니다.

```bash
./scripts/push_all.sh
```

다른 브랜치를 push하려면 브랜치명을 넘깁니다.

```bash
./scripts/push_all.sh main
```

이 스크립트는 아래 명령을 순서대로 실행합니다.

```bash
git push origin main
git push hf main
```

## 추천 운영 방식

평소에는 아래 방식이 가장 단순합니다.

```bash
python scripts/check_quality.py
git push origin main
```

이후 Hugging Face 반영은 GitHub Actions에 맡깁니다.

로컬에서 Hugging Face까지 직접 push하는 방식은 GitHub Actions 설정 전 테스트용으로만 사용해도 충분합니다.

## 일자별 변경 확인

Git은 커밋마다 날짜와 변경 파일을 남깁니다. 따라서 일자별 변경 내역은 언제든 확인할 수 있습니다.

오늘 변경 내역:

```bash
git log --since=midnight --stat
```

특정 날짜 변경 내역:

```bash
scripts/git_daily_changes.sh 2026-06-07
```

더 자세히 보려면 특정 커밋을 확인합니다.

```bash
git show <commit-hash>
```

## 주의사항

- `HF_TOKEN`은 절대 Git에 커밋하지 않습니다.
- `.env` 파일도 Git에 올리지 않습니다.
- Hugging Face Space가 Docker SDK를 사용하려면 README 상단 metadata의 `sdk: docker` 설정이 필요합니다.
- 대용량 업로드 PDF, Chroma 인덱스, Airflow 로그, PostgreSQL 데이터는 Git에 올리지 않습니다.
- Hugging Face 동기화는 현재 파일 스냅샷 방식으로 동작하므로 GitHub의 과거 커밋 히스토리와 Hugging Face의 커밋 히스토리는 다를 수 있습니다.
- Hugging Face Space에서는 Docker 빌드 시간이 걸릴 수 있습니다.

## 문제가 생겼을 때

### GitHub Actions에서 `HF_TOKEN secret is not set.` 오류가 날 때

GitHub 저장소의 Actions secret에 `HF_TOKEN`이 등록되어 있는지 확인합니다.

### Hugging Face push 권한 오류가 날 때

토큰 권한이 Space에 write 가능한지 확인합니다.

### GitHub push가 안 될 때

로컬 GitHub 인증이 되어 있는지 확인합니다.

```bash
gh auth status
```

`gh`를 쓰지 않는다면 SSH key나 HTTPS token 설정을 확인합니다.

# 08. GitHub / Hugging Face 배포 자동화

이 문서는 현재 프로젝트를 GitHub와 Hugging Face Space에 올리는 방법을 정리합니다.

## 목표

기본 흐름은 다음과 같습니다.

1. 로컬에서 GitHub로 push한다.
2. GitHub Actions가 실행된다.
3. GitHub Actions가 같은 커밋을 Hugging Face Space로 push한다.

이렇게 하면 평소에는 GitHub에만 push해도 Hugging Face Space가 자동으로 업데이트됩니다.

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

이 workflow는 `main` 브랜치에 push가 발생하면 Hugging Face Space의 `main` 브랜치로 다시 push합니다.

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
git push origin main
```

이후 Hugging Face 반영은 GitHub Actions에 맡깁니다.

로컬에서 Hugging Face까지 직접 push하는 방식은 GitHub Actions 설정 전 테스트용으로만 사용해도 충분합니다.

## 주의사항

- `HF_TOKEN`은 절대 Git에 커밋하지 않습니다.
- `.env` 파일도 Git에 올리지 않습니다.
- Hugging Face Space가 Docker SDK를 사용하려면 README 상단 metadata의 `sdk: docker` 설정이 필요합니다.
- 대용량 업로드 PDF, Chroma 인덱스, Airflow 로그, PostgreSQL 데이터는 Git에 올리지 않습니다.
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

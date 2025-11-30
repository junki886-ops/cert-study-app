import os
import subprocess
import sys
from pathlib import Path

# .env 파일에서 환경변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv가 없으면 무시

# ======================================================
# 🧩 1️⃣ 사용자 설정 (직접 입력)
# ======================================================

HF_USERNAME = "Kentlo"          # ← 본인 Hugging Face ID
SPACE_NAME = "cert-study-app"   # ← 원하는 Spaces 이름

# Spaces 기본 URL (표시용)
REPO_URL = f"https://huggingface.co/spaces/{HF_USERNAME}/{SPACE_NAME}"

# ======================================================
# 🪪 2️⃣ Hugging Face Token 확인 (환경변수 방식)
# ======================================================

def get_hf_token():
    """환경변수에서 HF_TOKEN을 안전하게 가져옵니다."""
    token = os.getenv("HF_TOKEN")
    
    if not token:
        print("=" * 60)
        print("⚠️  HF_TOKEN 환경변수가 설정되지 않았습니다.")
        print("=" * 60)
        print("\n📝 토큰 설정 방법:\n")
        print("1️⃣  Hugging Face 토큰 발급:")
        print("   https://huggingface.co/settings/tokens")
        print("   (Write 권한 필요)\n")
        print("2️⃣  환경변수 설정:\n")
        print("   Windows (PowerShell - 현재 세션):")
        print("   $env:HF_TOKEN = \"your_token_here\"\n")
        print("   Windows (PowerShell - 영구 설정):")
        print("   setx HF_TOKEN \"your_token_here\"\n")
        print("   macOS/Linux (bash):")
        print("   export HF_TOKEN=\"your_token_here\"\n")
        print("   또는 .env 파일에 추가:")
        print("   HF_TOKEN=your_token_here\n")
        print("=" * 60)
        sys.exit(1)
    
    # 토큰 유효성 간단 체크 (형식만)
    if len(token) < 20 or not token.startswith(('hf_', 'api_')):
        print("⚠️  토큰 형식이 올바르지 않습니다.")
        print("   Hugging Face 토큰은 'hf_'로 시작해야 합니다.")
        sys.exit(1)
    
    return token

hf_token = get_hf_token()

# 인증용 Git remote URL (런타임에만 사용, 코드에 하드코딩 안됨)
AUTH_REPO_URL = f"https://{HF_USERNAME}:{hf_token}@huggingface.co/spaces/{HF_USERNAME}/{SPACE_NAME}"

# ======================================================
# 🧰 3️⃣ 필수 파일 생성 (requirements.txt, runtime.txt, README.md, .env)
# ======================================================
print("\n📦 필수 파일 생성 중...")

requirements = """flask==3.0.3
python-dotenv==1.0.1
SQLAlchemy==2.0.36
alembic==1.13.2
pdfplumber==0.11.0
pdf2image==1.17.0
Pillow==10.4.0
pytesseract==0.3.13
langchain==0.2.16
langchain-community==0.2.12
langchain-huggingface==0.1.0
chromadb==0.5.5
sentence-transformers==3.0.1
transformers==4.44.2
accelerate==0.34.0
huggingface-hub==0.24.6
tqdm==4.66.4
paddleocr==2.9.1
paddlepaddle
"""

runtime = "python-3.10\n"

readme = """---
title: Cert Study App
emoji: 📚
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
license: apache-2.0
---

# Cert Study App 📚

AI-powered certification exam study application with intelligent question generation and adaptive learning.

## Features

- 📄 PDF parsing with OCR support
- 🤖 AI-powered question generation
- 📊 Study progress tracking
- 🎯 Adaptive learning system
- 🔍 Semantic search for questions

## Usage

Upload your study materials and start practicing with AI-generated questions tailored to your learning needs.

## Tech Stack

- Flask
- LangChain
- ChromaDB
- PaddleOCR
- Hugging Face Transformers
"""

dockerfile = """FROM python:3.10-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \\
    git \\
    tesseract-ocr \\
    poppler-utils \\
    libgl1-mesa-glx \\
    libglib2.0-0 \\
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 파일 복사
COPY . .

# 환경변수 설정
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=7860

# 포트 노출
EXPOSE 7860

# Flask 실행
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=7860"]
"""

env_template = """# 로컬 실행용 환경 변수
# ⚠️ 이 파일은 절대 Git에 올리지 마세요!

HF_TOKEN=
FLASK_ENV=production
FLASK_SECRET_KEY=
"""

# requirements.txt 생성
Path("requirements.txt").write_text(requirements, encoding="utf-8")
print("✅ requirements.txt 생성 완료")

# runtime.txt 생성
Path("runtime.txt").write_text(runtime, encoding="utf-8")
print("✅ runtime.txt 생성 완료")

# Dockerfile 생성
dockerfile_path = Path("Dockerfile")
dockerfile_path.write_text(dockerfile, encoding="utf-8")
print("✅ Dockerfile 생성 완료")

# README.md 생성
readme_path = Path("README.md")
if not readme_path.exists():
    readme_path.write_text(readme, encoding="utf-8")
    print("✅ README.md 생성 완료")
else:
    # 기존 README가 있으면 frontmatter 확인
    content = readme_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        # frontmatter가 없으면 추가
        readme_path.write_text(readme + "\n\n" + content, encoding="utf-8")
        print("✅ README.md에 Hugging Face 설정 추가")
    else:
        print("ℹ️  README.md가 이미 존재합니다 (유지)")

# 🔐 .env가 이미 있으면 유지, 없을 때만 템플릿 생성
env_path = Path(".env")
if not env_path.exists():
    env_path.write_text(env_template, encoding="utf-8")
    print("✅ .env 템플릿 생성 완료")
    print("   → HF_TOKEN= 에 실제 토큰을 입력하세요")
else:
    print("ℹ️  .env 파일이 이미 존재합니다 (유지)")

# ======================================================
# 🚫 .gitignore 설정 (민감한 파일 + 대용량 파일 제외)
# ======================================================
print("\n🚫 .gitignore 설정 중...")

gitignore_entries = [
    "# Environment variables",
    ".env",
    ".env.local",
    ".env.*.local",
    "",
    "# Large files (Hugging Face limit: 10MB)",
    "*.pdf",
    "dump.pdf",
    "*.zip",
    "data/ocr_logs/*.zip",
    "",
    "# Python",
    "__pycache__/",
    "*.py[cod]",
    "*$py.class",
    "*.so",
    ".Python",
    "venv/",
    ".venv/",
    "env/",
    "ENV/",
    "",
    "# Secrets",
    "*.token",
    "*_token.txt",
    "secrets/",
    "",
    "# IDE",
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
    "",
    "# Database (large files)",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "chroma_db/",
    "",
    "# Uploads",
    "uploads/",
    "temp/",
    "",
    "# Logs (can be large)",
    "*.log",
    "logs/",
]

gitignore_path = Path(".gitignore")

if gitignore_path.exists():
    content = gitignore_path.read_text(encoding="utf-8")
    lines_to_add = [entry for entry in gitignore_entries if entry and entry not in content]
    
    if lines_to_add:
        gitignore_path.write_text(
            content.rstrip() + "\n\n" + "\n".join(lines_to_add) + "\n",
            encoding="utf-8"
        )
        print(f"✅ .gitignore 업데이트 완료 ({len(lines_to_add)}개 항목 추가)")
    else:
        print("ℹ️  .gitignore가 이미 최신 상태입니다")
else:
    gitignore_path.write_text("\n".join(gitignore_entries) + "\n", encoding="utf-8")
    print("✅ .gitignore 생성 완료")

# ======================================================
# 🧹 대용량 파일 제거 (Hugging Face 제한: 10MB)
# ======================================================
print("\n🧹 대용량 파일 정리 중...")

def remove_large_files():
    """Git에서 대용량 파일을 제거합니다."""
    large_files = [
        "dump.pdf",
        "*.pdf",
        "*.zip",
        "chroma_db/chroma.sqlite3",
        "data/ocr_logs/OCR_AZ-104.zip",
    ]
    
    removed = []
    for pattern in large_files:
        result = subprocess.run(
            ["git", "rm", "--cached", "-r", pattern],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        if result.returncode == 0:
            removed.append(pattern)
    
    return removed

removed_files = remove_large_files()
if removed_files:
    print(f"✅ {len(removed_files)}개 대용량 파일 제거됨")
    for f in removed_files:
        print(f"   - {f}")
else:
    print("ℹ️  제거할 대용량 파일 없음")

# ======================================================
# 📏 파일 크기 체크
# ======================================================
print("\n📏 파일 크기 체크 중...")

def check_file_sizes():
    """10MB 이상 파일을 찾습니다."""
    large_files = []
    
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    
    if result.returncode != 0:
        return large_files
    
    for filepath in result.stdout.strip().split('\n'):
        if not filepath:
            continue
        
        path = Path(filepath)
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > 10:
                large_files.append((filepath, size_mb))
    
    return large_files

large_files = check_file_sizes()

if large_files:
    print("⚠️  경고: 10MB 이상 파일 발견!")
    for filepath, size_mb in large_files:
        print(f"   - {filepath}: {size_mb:.2f} MB")
    print("\n💡 이 파일들은 Hugging Face에 푸시되지 않습니다.")
    print("   .gitignore에 추가하거나 Git LFS를 사용하세요.")
    
    response = input("\n계속하시겠습니까? (yes/no): ").strip().lower()
    if response != 'yes':
        print("\n❌ 배포가 취소되었습니다.")
        sys.exit(1)
else:
    print("✅ 모든 파일이 10MB 미만입니다")

# ======================================================
# 🔍 민감한 정보 스캔 (푸시 전 검증)
# ======================================================
print("\n🔍 민감한 정보 스캔 중...")

def scan_for_secrets():
    """커밋할 파일에서 민감한 정보를 찾습니다."""
    patterns = [
        (r'hf_[a-zA-Z0-9]{30,}', 'Hugging Face 토큰'),
        (r'api_[a-zA-Z0-9]{30,}', 'API 토큰'),
        (r'sk-[a-zA-Z0-9]{32,}', 'OpenAI API 키'),
        (r'ghp_[a-zA-Z0-9]{36,}', 'GitHub 토큰'),
    ]
    
    issues = []
    
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    
    if result.returncode != 0:
        return issues
    
    files = result.stdout.strip().split('\n')
    
    import re
    for filepath in files:
        if not filepath or filepath.startswith('.'):
            continue
        
        try:
            path = Path(filepath)
            if not path.exists() or path.suffix in ['.db', '.sqlite', '.pyc', '.pdf', '.zip']:
                continue
                
            content = path.read_text(encoding='utf-8', errors='ignore')
            
            for pattern, name in patterns:
                if re.search(pattern, content):
                    issues.append(f"   ⚠️  {filepath}: {name} 발견")
        except Exception:
            continue
    
    return issues

secrets_found = scan_for_secrets()

if secrets_found:
    print("=" * 60)
    print("🚨 경고: 민감한 정보가 발견되었습니다!")
    print("=" * 60)
    for issue in secrets_found:
        print(issue)
    print("\n⚠️  계속 진행하면 이 정보들이 공개됩니다.")
    response = input("\n계속하시겠습니까? (yes/no): ").strip().lower()
    if response != 'yes':
        print("\n❌ 배포가 취소되었습니다.")
        print("   → 민감한 정보를 제거한 후 다시 시도하세요.")
        sys.exit(1)
else:
    print("✅ 민감한 정보가 발견되지 않았습니다")

# ======================================================
# 🏗️ Hugging Face Spaces 생성 (없으면)
# ======================================================
print("\n🏗️ Hugging Face Spaces 확인 중...")

def create_space_if_not_exists():
    """Spaces가 없으면 생성합니다."""
    try:
        from huggingface_hub import HfApi, SpaceInfo
        
        api = HfApi(token=hf_token)
        
        # Space가 존재하는지 확인
        try:
            space_info = api.space_info(repo_id=f"{HF_USERNAME}/{SPACE_NAME}")
            print(f"✅ Space가 이미 존재합니다: {REPO_URL}")
            return True
        except Exception:
            # Space가 없으면 생성
            print(f"📝 Space를 생성합니다: {SPACE_NAME}")
            
            api.create_repo(
                repo_id=f"{HF_USERNAME}/{SPACE_NAME}",
                repo_type="space",
                space_sdk="gradio",
                private=False
            )
            
            print(f"✅ Space 생성 완료: {REPO_URL}")
            return True
            
    except ImportError:
        print("⚠️  huggingface_hub가 설치되지 않아 자동 생성을 건너뜁니다.")
        print(f"   수동으로 생성하세요: https://huggingface.co/new-space")
        return False
    except Exception as e:
        print(f"⚠️  Space 생성 실패: {e}")
        print(f"   수동으로 생성하세요: https://huggingface.co/new-space")
        return False

create_space_if_not_exists()

# ======================================================
# 🔧 Git Remote 설정
# ======================================================
print("\n🔧 Git 저장소 설정 중...")

if not Path(".git").exists():
    subprocess.run(["git", "init"], check=True)
    print("✅ Git 저장소 초기화 완료")

# Hugging Face Spaces 용 remote 추가
subprocess.run(
    ["git", "remote", "remove", "spaces"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
subprocess.run(["git", "remote", "add", "spaces", AUTH_REPO_URL], check=True)

print("✅ Git remote 'spaces' 설정 완료")
print("   → Hugging Face Spaces 연결됨")
print("   → GitHub 'origin'은 그대로 유지됨")

# ======================================================
# 🚀 Git Commit & Push (Spaces용)
# ======================================================
print("\n🚀 Hugging Face Spaces로 배포 중...")

# 변경사항 스테이징
subprocess.run(["git", "add", "."], check=True)

# 커밋 상태 확인
status_result = subprocess.run(
    ["git", "status", "--porcelain"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='ignore'
)

if status_result.stdout.strip():
    # 커밋할 변경사항이 있음
    commit_result = subprocess.run(
        ["git", "commit", "-m", "🚀 Deploy to Hugging Face Spaces (removed large files)"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    
    if commit_result.returncode == 0:
        print("✅ 변경사항 커밋 완료")
    else:
        print("⚠️  커밋 중 문제 발생:")
        print(commit_result.stderr)
        sys.exit(commit_result.returncode)
else:
    print("ℹ️  새로 커밋할 변경사항 없음 (기존 커밋 사용)")

# 브랜치를 main으로 맞추기
subprocess.run(["git", "branch", "-M", "main"], check=True)

# Hugging Face Spaces로 push
print("\n📤 Hugging Face로 업로드 중...")
push_result = subprocess.run(
    ["git", "push", "--force", "spaces", "main"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='ignore'
)

if push_result.returncode != 0:
    print("❌ Push 실패:")
    print(push_result.stderr)
    
    # 대용량 파일 에러 체크
    if "files larger than 10 MiB" in push_result.stderr:
        print("\n💡 해결 방법:")
        print("   1. 위에서 표시된 파일들을 .gitignore에 추가")
        print("   2. git rm --cached <파일명> 으로 제거")
        print("   3. 다시 커밋 후 푸시")
    
    sys.exit(push_result.returncode)

# ======================================================
# 🎉 완료
# ======================================================
print("\n" + "=" * 60)
print("🎉 배포 완료!")
print("=" * 60)
print(f"\n🔗 앱 URL: {REPO_URL}")
print("\n⏳ Hugging Face가 자동 빌드를 진행합니다 (약 1~5분)")
print("\n💡 팁:")
print("   • 빌드 로그 확인: {}/logs".format(REPO_URL))
print("   • Settings에서 환경변수 설정 가능")
print("   • GitHub과 별도로 관리됩니다 (spaces remote)")
print("\n📝 주의사항:")
print("   • .env 파일은 절대 Git에 올리지 마세요")
print("   • 대용량 파일은 Git LFS 사용을 고려하세요")
print("\n" + "=" * 60)
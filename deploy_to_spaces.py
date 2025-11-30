import os
import subprocess
import sys
from pathlib import Path

# ======================================================
# 🧩 1️⃣ 사용자 설정 (직접 입력)
# ======================================================

HF_USERNAME = "junki886"        # ← 본인 Hugging Face ID
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
# 🧰 3️⃣ 필수 파일 생성 (requirements.txt, runtime.txt, .env)
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
langchain-huggingface==0.0.4
chromadb==0.5.5
sentence-transformers==3.0.1
transformers==4.44.3
accelerate==0.34.0
huggingface-hub==0.24.6
tqdm==4.66.4
paddleocr==2.9.1
paddlepaddle-gpu
"""

runtime = "python-3.10\n"

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

# 🔐 .env가 이미 있으면 유지, 없을 때만 템플릿 생성
env_path = Path(".env")
if not env_path.exists():
    env_path.write_text(env_template, encoding="utf-8")
    print("✅ .env 템플릿 생성 완료")
    print("   → HF_TOKEN= 에 실제 토큰을 입력하세요")
else:
    print("ℹ️  .env 파일이 이미 존재합니다 (유지)")

# ======================================================
# 🚫 .gitignore 설정 (민감한 파일 제외)
# ======================================================
print("\n🚫 .gitignore 설정 중...")

gitignore_entries = [
    "# Environment variables",
    ".env",
    ".env.local",
    ".env.*.local",
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
    "# Database",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "",
    "# Uploads",
    "uploads/",
    "temp/",
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
    
    # Git에서 추적하는 파일만 검사
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    if result.returncode != 0:
        print("⚠️  Git 파일 목록을 가져올 수 없습니다")
        return issues
    
    files = result.stdout.strip().split('\n')
    
    import re
    for filepath in files:
        if not filepath or filepath.startswith('.'):
            continue
        
        try:
            path = Path(filepath)
            if not path.exists() or path.suffix in ['.db', '.sqlite', '.pyc']:
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
    text=True
)

if status_result.stdout.strip():
    # 커밋할 변경사항이 있음
    commit_result = subprocess.run(
        ["git", "commit", "-m", "🚀 Deploy to Hugging Face Spaces"],
        capture_output=True,
        text=True
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
    text=True
)

if push_result.returncode != 0:
    print("❌ Push 실패:")
    print(push_result.stderr)
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
print("\n" + "=" * 60)
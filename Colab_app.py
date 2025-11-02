# ============================================
# ⚙️ Colab 자동 PDF 파싱 + JSON 다운로드 버전
# ============================================

# 1️⃣ 필수 패키지 설치
!apt -y install poppler-utils
!pip install paddleocr paddlepaddle-gpu
!pip install pdf2image Pillow pytesseract
!pip install langchain langchain-community langchain-huggingface
!pip install transformers accelerate sentence-transformers
!pip install sqlalchemy alembic python-dotenv tqdm

# 2️⃣ 프로젝트 불러오기 또는 업데이트
import os
%cd /content
repo_url = "https://github.com/junki886-ops/cert-study-app.git"
if not os.path.exists("cert-study-app"):
    !git clone {repo_url}
else:
    %cd cert-study-app
    !git pull
%cd /content/cert-study-app

# 3️⃣ 데이터 폴더 준비
!mkdir -p data/uploads data/images data/outputs

# 4️⃣ DB 초기화
from pdf_parser import init_db
init_db()

# 5️⃣ PDF 업로드
from google.colab import files
uploaded = files.upload()
pdf_path = list(uploaded.keys())[0]
pdf_full_path = f"/content/cert-study-app/data/uploads/{pdf_path}"
print(f"[INFO] 업로드 완료: {pdf_full_path}")

# 6️⃣ OCR + LLM 파싱 실행
from pdf_parser import parse_pdf

results = parse_pdf(
    pdf_path=pdf_full_path,
    output_json="/content/cert-study-app/data/outputs/questions.json",
    use_llm=True,      # OCR + LLM 파싱
    lang="korean"      # 한글 OCR
)

print(f"✅ 파싱 완료: 총 {len(results)}문항 추출됨")

# 7️⃣ 결과 미리보기
import json
with open("/content/cert-study-app/data/outputs/questions.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"\n📘 총 {len(data)}문항 중 앞 2문항 미리보기 ↓\n")
print(json.dumps(data[:2], ensure_ascii=False, indent=2))

# 8️⃣ JSON 결과 다운로드
from google.colab import files
files.download("/content/cert-study-app/data/outputs/questions.json")

print("\n✅ JSON 파일 다운로드가 시작됩니다.")

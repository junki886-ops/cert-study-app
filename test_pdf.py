from pdf2image import convert_from_path
import os

# Poppler가 PATH에 없으면, 직접 경로 지정 (예시는 버전마다 다릅니다)
POPLER_BIN = r"C:\Program Files\poppler-24.08.0\Library\bin"

pdf_path = "sample.pdf"   # 임의의 PDF 파일 준비
out_dir = "./data/images"
os.makedirs(out_dir, exist_ok=True)

pages = convert_from_path(pdf_path, dpi=200, poppler_path=POPLER_BIN)
for i, p in enumerate(pages):
    out = os.path.join(out_dir, f"page_{i+1:03d}.png")
    p.save(out)
    print("Saved:", out)

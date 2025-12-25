# ==============================================
# ocr_test_light.py
# PaddleOCR 정상 작동 확인용 (CPU / No OpenCV)
# ==============================================

from paddleocr import PaddleOCR
from PIL import Image
import os, sys

# 1️⃣ 이미지 경로 설정
IMG_PATH = "data/images/page_1.jpg"  # 테스트할 이미지 경로

if not os.path.exists(IMG_PATH):
    print(f"[ERROR] 파일을 찾을 수 없습니다: {IMG_PATH}")
    print("PDF에서 변환된 이미지(page_1.jpg)가 존재하는지 확인하세요.")
    sys.exit(1)

# 2️⃣ PaddleOCR 초기화
print("[INFO] PaddleOCR 로드 중... (약간의 시간이 걸립니다)")
ocr = PaddleOCR(
    use_angle_cls=True,
    lang="korean",
    use_gpu=False,
    enable_mkldnn=False,
    cpu_threads=4,
    det_limit_side_len=1280,
)

# 3️⃣ OCR 실행
print(f"[INFO] OCR 실행: {IMG_PATH}")
result = ocr.ocr(IMG_PATH, cls=True)

# 4️⃣ 결과 출력
print("\n=== OCR 결과 ===")
if result and result[0]:
    for line in result[0]:
        text, conf = line[1]
        print(f"{text} (신뢰도: {conf:.3f})")
else:
    print("[WARN] 텍스트를 인식하지 못했습니다. 이미지 품질이나 DPI를 확인하세요.")

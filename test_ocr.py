import os
from dotenv import load_dotenv
import pytesseract
from PIL import Image, ImageDraw

load_dotenv()
tess = os.getenv("TESSERACT_CMD")
if tess and os.path.exists(tess):
    pytesseract.pytesseract.tesseract_cmd = tess

# 테스트용 이미지 만들기 (영문+국문)
img = Image.new("RGB", (400, 120), "white")
d = ImageDraw.Draw(img)
d.text((10,10), "Hello OCR", fill="black")
d.text((10,60), "안녕하세요 OCR", fill="black")
img.save("tmp_ocr.png")

print("tesseract path:", pytesseract.pytesseract.tesseract_cmd)
print("langs:", pytesseract.get_languages(config=''))

text = pytesseract.image_to_string(Image.open("tmp_ocr.png"), lang="eng+kor")
print("OCR Result:\n", text)

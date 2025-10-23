# ocr_parse.py
import os
import re
from pdf2image import convert_from_path
from PIL import Image
import pytesseract


def ocr_image(image_path: str) -> str:
    """이미지에서 OCR 실행"""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="kor+eng")
    return text.strip()


def parse_questions(text: str):
    """
    OCR 텍스트에서 문제/보기/정답 자동 파싱
    :param text: OCR로 추출한 텍스트
    :return: [{id, question, options, answer, explanation}]
    """
    questions = []
    
    # 문제 단위로 split (예: 1. ~ 2. ~)
    raw_questions = re.split(r"\n(?=\d+\.)", text)

    for q_block in raw_questions:
        q_block = q_block.strip()
        if not q_block:
            continue

        # 문제 번호 추출
        match = re.match(r"(\d+)\.\s*(.*)", q_block, re.DOTALL)
        if not match:
            continue
        q_id = int(match.group(1))
        body = match.group(2).strip()

        # 보기 추출 (A. ~ D.)
        options = re.findall(r"([A-D]\.\s*[^\n]+)", body)

        # 문제 본문에서 보기 제거
        question_text = re.split(r"[A-D]\.", body)[0].strip()

        # 정답 추출 (예: "정답: B" or "Answer: C")
        ans_match = re.search(r"(정답|Answer)[:：]\s*([A-D])", body)
        answer = ans_match.group(2) if ans_match else None

        # 해설 추출 (예: "해설:" 이후 텍스트)
        exp_match = re.search(r"(해설|Explanation)[:：]\s*(.*)", body)
        explanation = exp_match.group(2).strip() if exp_match else ""

        questions.append({
            "id": q_id,
            "question": question_text,
            "options": options,
            "answer": answer,
            "explanation": explanation
        })

    return questions


def parse_pdf(pdf_path: str, output_dir: str):
    """
    PDF → 이미지 → OCR → 문제/보기/정답 파싱
    :param pdf_path: PDF 경로
    :param output_dir: 이미지 저장 경로
    :return: [{page, id, question, options, answer, explanation}]
    """
    os.makedirs(output_dir, exist_ok=True)

    pages = convert_from_path(pdf_path, dpi=300)
    results = []

    for i, page in enumerate(pages, start=1):
        img_path = os.path.join(output_dir, f"page_{i}.png")
        page.save(img_path, "PNG")

        # OCR
        text = ocr_image(img_path)

        # 문제 파싱
        questions = parse_questions(t_

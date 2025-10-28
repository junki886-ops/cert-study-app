import pdfplumber, re, json
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract, cv2, numpy as np

def clean_text(line: str) -> str:
    """광고/불필요 텍스트 제거"""
    junk = ["The safer , easier way", "https://www.siheom.kr", "Exam :", "Version :", 
            "Siheom", "좋은 품질", "당신은 가질 가치가 있다", "덤프", "고객에게"]
    for j in junk:
        if j in line:
            return ""
    return line

def parse_pdf(pdf_path, output_json, poppler_path=None, lang="kor+eng"):
    text = ""

    # 1) pdfplumber (텍스트 PDF)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print("[WARN] pdfplumber 실패:", e)

    # 2) OCR fallback
    if len(text.strip()) < 50:
        print("[INFO] 텍스트 부족 → OCR 전환")
        pages = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
        for i, pil in enumerate(pages, start=1):
            cv = cv2.cvtColor(np.array(pil), cv2.COLOR_BGR2GRAY)
            cv = cv2.adaptiveThreshold(cv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 31, 9)
            txt = pytesseract.image_to_string(cv, lang=lang, config="--psm 6")
            text += txt + "\n"
            Path("data/debug").mkdir(parents=True, exist_ok=True)
            (Path("data/debug")/f"page_{i:03d}.txt").write_text(txt, encoding="utf-8")

    # 3) 전처리 - 줄별로 정리
    lines = []
    for raw in text.splitlines():
        line = clean_text(raw.strip())
        if line:
            lines.append(line)

    # 4) 문제 파싱
    items = []
    current = None
    in_explanation = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 새로운 문제 번호 감지 (더 엄격하게)
        # "1.", "2.", ... 형태이면서 다음 줄이 보기가 아닐 때
        question_match = re.match(r'^(\d+)\.\s*(.+)', line)
        if question_match:
            # 이전 문제 저장
            if current and current["stem"]:
                if not current["answer"]:
                    current["answer"] = "N/A"
                items.append(current)
            
            # 새 문제 시작
            qnum = question_match.group(1)
            qtext = question_match.group(2)
            current = {
                "stem": f"{qnum}. {qtext}",
                "options": [],
                "answer": None,
                "explanation": ""
            }
            in_explanation = False
            i += 1
            continue
        
        if not current:
            i += 1
            continue
        
        # 정답 파싱
        if re.match(r'^(정답|Answer)\s*[:：]?\s*', line, re.IGNORECASE):
            answer_text = re.sub(r'^(정답|Answer)\s*[:：]?\s*', '', line, flags=re.IGNORECASE).strip()
            # A, B, C, D, ①-⑤, 1-5 등 추출
            match = re.search(r'[A-E①-⑤1-5]', answer_text)
            if match:
                current["answer"] = match.group(0)
            in_explanation = False
            i += 1
            continue
        
        # 해설 시작
        if re.match(r'^(해설|Explanation)\s*[:：]?', line, re.IGNORECASE):
            in_explanation = True
            expl_text = re.sub(r'^(해설|Explanation)\s*[:：]?', '', line, flags=re.IGNORECASE).strip()
            if expl_text:
                current["explanation"] += expl_text + " "
            i += 1
            continue
        
        # 해설 내용
        if in_explanation:
            # 다음 문제나 보기가 나오면 해설 종료
            if re.match(r'^\d+\.', line) or re.match(r'^[A-E①-⑤]\s*[.):]', line):
                in_explanation = False
            else:
                current["explanation"] += line + " "
                i += 1
                continue
        
        # 보기 파싱 (A., B., ①, ② 등)
        option_match = re.match(r'^([A-E①-⑤])\s*[.):]\s*(.+)', line)
        if option_match:
            opt_label = option_match.group(1)
            opt_text = option_match.group(2)
            current["options"].append(f"{opt_label}. {opt_text}")
            i += 1
            continue
        
        # 문제 본문에 추가
        if not in_explanation and not re.match(r'^\d+\.', line):
            current["stem"] += " " + line
        
        i += 1

    # 마지막 문제 저장
    if current and current["stem"]:
        if not current["answer"]:
            current["answer"] = "N/A"
        items.append(current)

    # 5) 후처리 - 너무 짧은 문제나 보기 없는 문제 제거
    valid_items = []
    for item in items:
        if len(item["stem"]) > 10 and len(item["options"]) >= 2:
            valid_items.append(item)
        else:
            print(f"[WARN] 제외된 문제: {item['stem'][:50]}")

    # 6) 저장
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(valid_items, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[INFO] 파싱된 문항 수: {len(valid_items)}")
    no_answer = sum(1 for item in valid_items if item["answer"] == "N/A")
    if no_answer > 0:
        print(f"[WARN] 정답 없는 문항: {no_answer}개")
    
    return valid_items
# ==============================================
# pdf_parser_adaptive.py (v6.3 CPU-Stable + SmartSkip)
# OCR + LLM 기반 Adaptive PDF Parser
# ✅ 기존 OCR/이미지 감지 → OCR 단계 자동 스킵
# ✅ LLM 파싱만 재실행 가능
# Compatible with app_v2025 + models_v2025 + llm_parse_v3.1
# ==============================================

import os, re, json, time, traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import torch
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langchain_huggingface import HuggingFacePipeline
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

# 외부 LLM 파서
from llm_parse import llm_parse_v2

# ----------------------------------------------
# 경로 설정
# ----------------------------------------------
DATA_DIR = Path("data")
IMAGE_DIR = DATA_DIR / "images"
OCR_LOG_DIR = DATA_DIR / "ocr_logs"
RUN_LOG_DIR = DATA_DIR / "run_logs"
for p in [IMAGE_DIR, OCR_LOG_DIR, RUN_LOG_DIR]:
    p.mkdir(parents=True, exist_ok=True)

def _log(level, msg):
    print(f"[{level}] {msg}")

# ----------------------------------------------
# Config
# ----------------------------------------------
@dataclass
class ParserConfig:
    pdf_path: str
    output_json: str
    use_llm: bool = True
    lang: str = "korean"
    dpi: int = 200
    cpu_threads: int = max(1, (os.cpu_count() or 4) // 4)
    llm_model: str = "Qwen/Qwen2.5-1.8B"
    max_new_tokens: int = 192
    ocr_workers: int = 1

# ----------------------------------------------
# OCR 생성기
# ----------------------------------------------
def create_ocr(lang: str, cpu_threads: int) -> PaddleOCR:
    return PaddleOCR(
        use_angle_cls=True,
        lang=lang,
        rec_char_type="korean_english",
        rec_algorithm="SVTR_LCNet",
        det_limit_side_len=1280,
        det_db_box_thresh=0.3,
        use_gpu=False,
        enable_mkldnn=False,
        cpu_threads=cpu_threads
    )

# ----------------------------------------------
# 전처리
# ----------------------------------------------
def preprocess_light(img_path: Path) -> Path:
    img = Image.open(img_path)
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    out_path = img_path.with_name(img_path.stem + "_light.jpg")
    img.save(out_path, "JPEG", quality=90)
    return out_path

def preprocess_heavy(img_path: Path) -> Path:
    img = Image.open(img_path)
    img = ImageOps.exif_transpose(img).convert("L")
    w, h = img.size
    img = img.resize((int(w * 1.2), int(h * 1.2)))
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(1.7)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))
    out_path = img_path.with_name(img_path.stem + "_heavy.jpg")
    img.save(out_path, "JPEG", quality=90)
    return out_path

def ocr_quality_score(text: str) -> float:
    if not text.strip():
        return 0.0
    valid = re.findall(r"[가-힣A-Za-z0-9]", text)
    ratio = len(valid) / max(len(text), 1)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    avg_len = sum(len(l) for l in lines) / max(1, len(lines))
    return min(1.0, ratio * (avg_len / 10 + 0.5))

def clean_text(t: str) -> str:
    t = re.sub(r"[\r\t]+", " ", t)
    t = re.sub(r"[ \u00A0]+", " ", t)
    t = re.sub(r"[ ]{2,}", " ", t)
    return t.strip()

# ----------------------------------------------
# PDF → 이미지 변환
# ----------------------------------------------
def pdf_to_images(cfg: ParserConfig) -> List[Path]:
    _log("INFO", f"[STEP 1] PDF → 이미지 변환 중... ({cfg.dpi}dpi)")

    # 기존 이미지가 존재하면 변환 스킵
    existing_imgs = sorted(IMAGE_DIR.glob("page_*.jpg")) + sorted(IMAGE_DIR.glob("page_*.png"))
    if existing_imgs:
        _log("INFO", f"[STEP 1] 기존 이미지 {len(existing_imgs)}개 발견 → 변환 스킵")
        return existing_imgs

    pages = convert_from_path(cfg.pdf_path, dpi=cfg.dpi)
    paths = []
    for i, pg in enumerate(pages, 1):
        path = IMAGE_DIR / f"page_{i}.jpg"
        pg.save(path, "JPEG")
        paths.append(path)
    _log("INFO", f"[STEP 1] 완료 ({len(paths)}페이지)")
    return paths

# ----------------------------------------------
# OCR 실행 (자동 스킵)
# ----------------------------------------------
def run_ocr(cfg: ParserConfig, ocr: PaddleOCR, img_paths: List[Path]) -> Dict[int, str]:
    _log("INFO", "[STEP 2] OCR 단계 시작 (자동 스킵 감지)")
    ocr_map = {}

    existing_txts = sorted(OCR_LOG_DIR.glob("page_*.txt"))
    existing_imgs = sorted(IMAGE_DIR.glob("page_*.jpg")) + sorted(IMAGE_DIR.glob("page_*.png"))

    # ✅ 기존 OCR 결과 존재 시 스킵
    if existing_txts or existing_imgs:
        _log("INFO", f"기존 OCR 결과 감지됨 → OCR 단계 스킵하고 기존 결과 사용")

        # 텍스트 파일 우선 로드
        for txt_path in existing_txts:
            m = re.search(r"page[_-]?(\d+)", txt_path.name)
            page_num = int(m.group(1)) if m else 0
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    text = clean_text(f.read())
                    ocr_map[page_num] = text
            except Exception as e:
                _log("WARN", f"OCR 텍스트 로드 실패: {txt_path} ({e})")

        # 이미지만 있고 텍스트 없는 경우
        for img_path in existing_imgs:
            m = re.search(r"page[_-]?(\d+)", img_path.name)
            page_num = int(m.group(1)) if m else 0
            if page_num not in ocr_map:
                ocr_map[page_num] = f"[SKIP OCR] {img_path.name}"
        return ocr_map

    # ✅ OCR 신규 수행
    _log("INFO", "[STEP 2] OCR 신규 수행 중...")
    def ocr_one(img_path: Path):
        m = re.search(r"page[_-]?(\d+)", img_path.name)
        page = int(m.group(1)) if m else 0
        cache_path = OCR_LOG_DIR / f"page_{page}.txt"

        for pre_fn in [preprocess_light, preprocess_heavy]:
            try:
                processed = pre_fn(img_path)
                res = ocr.ocr(str(processed), cls=True)
                text = "\n".join([ln[1][0] for ln in (res[0] or [])]) if res and res[0] else ""
                text = clean_text(text)
                if text and ocr_quality_score(text) >= 0.3:
                    cache_path.write_text(text, encoding="utf-8")
                    return page, text
            except Exception as e:
                _log("WARN", f"OCR 실패 (p{page}): {e}")

        cache_path.write_text("", encoding="utf-8")
        return page, ""

    with ThreadPoolExecutor(max_workers=cfg.ocr_workers) as ex:
        futures = [ex.submit(ocr_one, p) for p in img_paths]
        for i, f in enumerate(as_completed(futures), 1):
            p, txt = f.result()
            ocr_map[p] = txt
            if i % 2 == 0:
                _log("INFO", f"[OCR] {i}/{len(img_paths)} 완료 (p{p}, score={ocr_quality_score(txt):.2f})")

    return ocr_map

# ----------------------------------------------
# 병합 및 LLM 파싱
# ----------------------------------------------
Q_SPLIT = re.compile(r"(?:문제\s*\d+\.?|Q\s*\d+\.?|^\s*\d+\.\s|다음\s*중|시나리오|Case\s*\d+|Explanation\s*:?)", re.IGNORECASE | re.MULTILINE)

def merge_pages_to_questions(ocr_map: Dict[int, str]) -> List[Tuple[int, str]]:
    merged = []
    for p in sorted(ocr_map.keys()):
        txt = clean_text(ocr_map[p])
        if not txt:
            continue
        chunks = [c.strip() for c in re.split(Q_SPLIT, txt) if c.strip()]
        for c in chunks:
            if len(c) >= 50 and any(k in c for k in ["정답", "보기", "Answer", "Explanation", "문제"]):
                merged.append((p, c))
    return merged

def load_llm(cfg: ParserConfig):
    _log("INFO", f"[STEP 4] LLM 로드 중... ({cfg.llm_model})")
    tok = AutoTokenizer.from_pretrained(cfg.llm_model)
    mdl = AutoModelForCausalLM.from_pretrained(cfg.llm_model, torch_dtype="auto", low_cpu_mem_usage=True)
    pipe = pipeline("text-generation", model=mdl, tokenizer=tok, device=-1, max_new_tokens=cfg.max_new_tokens, temperature=0.0)
    _log("INFO", "[STEP 4] LLM 로드 완료")
    return HuggingFacePipeline(pipeline=pipe)

# ----------------------------------------------
# 메인 파이프라인
# ----------------------------------------------
def parse_pdf(pdf_path: str, output_json: str, use_llm=True, lang="korean", dpi: Optional[int] = None):
    torch.set_num_threads(1)
    cfg = ParserConfig(pdf_path, output_json, use_llm, lang)
    if dpi:
        cfg.dpi = dpi

    _log("INFO", f"[START] {pdf_path} (dpi={cfg.dpi}, threads={cfg.cpu_threads})")

    # STEP 1: PDF → 이미지 (있으면 스킵)
    pages = pdf_to_images(cfg)

    # STEP 2: OCR (있으면 스킵)
    ocr = create_ocr(cfg.lang, cfg.cpu_threads)
    ocr_map = run_ocr(cfg, ocr, pages)

    # STEP 3: 문항 병합
    items = merge_pages_to_questions(ocr_map)
    _log("INFO", f"[STEP 3] 문항 병합 완료 ({len(items)}개)")

    # STEP 4: LLM 파싱
    results = []
    if use_llm:
        llm = load_llm(cfg)
        for p, t in items:
            try:
                results.append(llm_parse_v2(llm, p, t))
            except Exception as e:
                results.append({
                    "page": p,
                    "stem": t[:400],
                    "options": [],
                    "answer": [],
                    "explanation": f"LLM 실패: {e}",
                    "question_type": "mcq"
                })
    else:
        for p, t in items:
            results.append({
                "page": p,
                "stem": t[:400],
                "options": [],
                "answer": [],
                "explanation": "",
                "question_type": "mcq"
            })

    Path(output_json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("INFO", f"[DONE] 총 {len(results)} 문항 저장 → {output_json}")
    return results

# ----------------------------------------------
# CLI 디버그 실행
# ----------------------------------------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default="data/parsed.json")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--dpi", type=int, default=None)
    args = ap.parse_args()
    try:
        parse_pdf(args.pdf, args.out, use_llm=not args.no_llm, dpi=args.dpi)
    except Exception as e:
        _log("ERROR", f"실행 중 오류: {e}")
        print(traceback.format_exc())

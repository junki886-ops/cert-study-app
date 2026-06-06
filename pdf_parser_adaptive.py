# ==============================================
# pdf_parser_adaptive.py (v6.3 CPU-Stable + SmartSkip)
# OCR + LLM 기반 Adaptive PDF Parser
# ✅ 기존 OCR/이미지 감지 → OCR 단계 자동 스킵
# ✅ LLM 파싱만 재실행 가능
# Compatible with app_v2025 + models_v2025 + llm_parse_v3.1
# ==============================================

import hashlib
import os, re, json, time, traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import torch
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError
from paddleocr import PaddleOCR
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langchain_huggingface import HuggingFacePipeline
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

# LangChain parser
from cert_study_app.chains.question_parser_chain import parse_question_with_chain
from cert_study_app.services.text_cleanup_service import clean_question_text, is_noise_line

# ----------------------------------------------
# 경로 설정
# ----------------------------------------------
DATA_DIR = Path("data")
IMAGE_DIR = DATA_DIR / "images"
QUESTION_IMAGE_DIR = DATA_DIR / "question_images"
OCR_LOG_DIR = DATA_DIR / "ocr_logs"
RUN_LOG_DIR = DATA_DIR / "run_logs"
for p in [IMAGE_DIR, QUESTION_IMAGE_DIR, OCR_LOG_DIR, RUN_LOG_DIR]:
    p.mkdir(parents=True, exist_ok=True)

def _log(level, msg):
    print(f"[{level}] {msg}")


def _emit(callback, **payload):
    if callback:
        callback(payload)


def _job_name(pdf_path: str) -> str:
    stem = Path(pdf_path).stem
    safe = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", stem).strip("._-") or "pdf"
    digest = hashlib.sha1(str(Path(pdf_path).resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{safe}_{digest}"


def _item_key(page: int, text: str) -> str:
    return hashlib.sha1(f"{page}:{text[:600]}".encode("utf-8")).hexdigest()


def _page_images(directory: Path) -> List[Path]:
    paths = sorted(directory.glob("page_*.jpg")) + sorted(directory.glob("page_*.png"))
    return [p for p in paths if not p.stem.endswith(("_light", "_heavy"))]

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
    llm_provider: str = os.getenv("CERT_STUDY_LLM_PROVIDER", "ollama")
    llm_model: str = "Qwen/Qwen2.5-1.8B"
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    max_new_tokens: int = 192
    ocr_workers: int = 1
    job_name: str = ""
    image_dir: Path = IMAGE_DIR
    question_image_dir: Path = QUESTION_IMAGE_DIR
    ocr_log_dir: Path = OCR_LOG_DIR
    partial_jsonl: Path = RUN_LOG_DIR / "parsed.partial.jsonl"


@dataclass
class PdfTextLine:
    page: int
    text: str
    bbox: Tuple[float, float, float, float]


@dataclass
class QuestionRange:
    number: int
    start: int
    end: int

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


def clean_pdf_line(text: str) -> str:
    text = clean_text(text)
    if not text:
        return ""
    if is_noise_line(text):
        return ""
    if "The safer" in text and "IT exams" in text:
        return ""
    if re.match(r"^\d+\s*/\s*\d+$", text):
        return ""
    return text


def extract_pdf_text_lines(pdf_path: str) -> List[PdfTextLine]:
    try:
        import fitz
    except Exception:
        return []

    lines: List[PdfTextLine] = []
    try:
        with fitz.open(pdf_path) as doc:
            for page_index, page in enumerate(doc, 1):
                data = page.get_text("dict")
                for block in data.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        text = "".join(span.get("text", "") for span in line.get("spans", []))
                        text = clean_pdf_line(text)
                        if text:
                            lines.append(
                                PdfTextLine(
                                    page=page_index,
                                    text=text,
                                    bbox=tuple(line.get("bbox", (0, 0, 0, 0))),
                                )
                            )
    except Exception as exc:
        _log("WARN", f"PDF 텍스트 추출 실패: {exc}")
        return []
    return lines


def _question_start_number(text: str) -> Optional[int]:
    match = re.match(r"^\s*(\d{1,3})\s*[.)]\s*\S+", text)
    if not match:
        return None
    return int(match.group(1))


def split_pdf_lines_to_ranges(lines: List[PdfTextLine]) -> List[QuestionRange]:
    candidates = []
    for index, line in enumerate(lines):
        number = _question_start_number(line.text)
        if number is None:
            continue
        candidates.append((index, number))

    selected = []
    expected = 1
    for index, number in candidates:
        if number == expected:
            selected.append((index, number))
            expected += 1

    ranges: List[QuestionRange] = []
    for pos, (start, number) in enumerate(selected):
        end = selected[pos + 1][0] if pos + 1 < len(selected) else len(lines)
        chunk = "\n".join(line.text for line in lines[start:end])
        if "Answer:" not in chunk and "정답" not in chunk and len(chunk) < 80:
            continue
        ranges.append(QuestionRange(number=number, start=start, end=end))
    return ranges


def _split_explanation(text: str) -> Tuple[str, str]:
    match = re.search(r"(?im)^\s*Explanation\s*:\s*", text)
    if not match:
        match = re.search(r"(?im)^\s*해설\s*:\s*", text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.end() :].strip()


def _extract_answer(text: str) -> Tuple[str, str]:
    match = re.search(r"(?im)^\s*(?:Answer|정답)\s*:\s*(.*?)\s*$", text)
    if not match:
        return "", text
    explanation_match = re.search(r"(?im)^\s*(?:Explanation|해설)\s*:\s*", text[match.end() :])
    if explanation_match:
        answer_end = match.end() + explanation_match.start()
    else:
        answer_end = len(text)
    answer = (match.group(1) + "\n" + text[match.end() : answer_end]).strip()
    answer = re.sub(r"\n+", " ", answer)
    answer = re.sub(r"\s+", " ", answer).strip()
    without = (text[: match.start()] + "\n" + text[answer_end:]).strip()
    return answer, without


def _extract_options(text: str) -> Tuple[str, List[str]]:
    option_matches = list(re.finditer(r"(?m)^\s*([A-H])\.\s*(.+)$", text))
    if len(option_matches) < 2:
        return text.strip(), []

    options = []
    for pos, match in enumerate(option_matches):
        end = option_matches[pos + 1].start() if pos + 1 < len(option_matches) else len(text)
        body = text[match.start() : end].strip()
        body = re.sub(r"\n+", " ", body)
        body = re.sub(r"\s+\d+\s*[.)]\s*[「『].*$", "", body)
        body = re.sub(r"\s+", " ", body).strip()
        options.append(body)
    stem = text[: option_matches[0].start()].strip()
    return stem, options


def _looks_like_multi_select(text: str, answer: str, options: List[str]) -> bool:
    if len(options) < 2:
        return False
    answer_labels = re.findall(r"\b[A-H]\b", answer or "")
    compact_answer = re.sub(r"[^A-H]", "", (answer or "").upper())
    has_multiple_answers = len(set(answer_labels)) > 1 or len(set(compact_answer)) > 1
    if has_multiple_answers:
        return True
    return bool(
        re.search(
            r"(어떤\s*(두|세|네)\s*(가지|개)|두\s*가지\s*옵션|세\s*가지\s*작업|각\s*정답|각\s*올바른\s*선택|choose\s+two|choose\s+three|select\s+two|select\s+three)",
            text or "",
            re.I,
        )
    )


def _detect_structured_type(text: str, options: List[str], answer: str = "") -> str:
    lowered = text.lower()
    if "핫스팟" in text or "hotspot" in lowered or "답변 영역" in text:
        return "hotspot"
    if "끌어" in text or "drag" in lowered or "drop" in lowered:
        return "matching"
    if "순서" in text or "정렬" in text or "배치" in text:
        return "ordering"
    if "다음 각 진술" in text or "각 진술" in text:
        return "yes_no"
    if "예" in text and "아니오" in text:
        return "yes_no"
    if "표" in text and ("선택" in text or "각 행" in text):
        return "table_choice"
    if _looks_like_multi_select(text, answer, options):
        return "multi_select"
    if len(options) >= 2 and any(marker in text for marker in ["개요", "기존 환경", "요구 사항", "계획된 변경", "시나리오"]):
        return "case_study"
    if len(options) >= 2:
        return "mcq"
    return "unparsed"


def _group_marker(text: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"(\d{1,3})\s*[~～-]\s*(\d{1,3})\s*번\s*문제", text)
    if not match:
        match = re.search(r"\(\s*(\d{1,3})\s*[~～-]\s*(\d{1,3})\s*\)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _topic_intro_number(text: str) -> Optional[int]:
    match = re.match(r"^\s*(\d{1,3})\s*[.)]\s*주제\s*\d+", text)
    if not match:
        return None
    return int(match.group(1))


def _split_parent_and_child(stem: str) -> Tuple[Optional[str], str]:
    lines = [line.strip() for line in stem.splitlines() if line.strip()]
    if len(lines) < 4:
        return None, stem.strip()

    marker_index = None
    for index, line in enumerate(lines):
        if _group_marker(line):
            marker_index = index
            break
    if marker_index is None:
        return None, stem.strip()

    child_start = max(marker_index + 1, len(lines) - 3)
    parent = _clean_parent_stem("\n".join(lines[:child_start]))
    child = "\n".join(lines[child_start:]).strip()
    return parent, child or stem.strip()


def _split_topic_parent_and_child(stem: str) -> Tuple[Optional[str], str]:
    lines = [line.strip() for line in stem.splitlines() if line.strip()]
    if len(lines) < 8 or not _topic_intro_number(lines[0]):
        return None, stem.strip()

    cue_indexes = [
        index
        for index, line in enumerate(lines)
        if any(cue in line for cue in ["핫스팟", "드래그 앤 드롭", "드래그 드롭", "끌어 놓기"])
    ]
    cue_indexes = [index for index in cue_indexes if index > 2]
    if not cue_indexes:
        return None, stem.strip()

    child_start = cue_indexes[-1]
    parent = _clean_parent_stem("\n".join(lines[:child_start]))
    child = "\n".join(lines[child_start:]).strip()
    return parent, child or stem.strip()


def _clean_parent_stem(text: str) -> str:
    cleaned = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        topic_match = re.match(r"^\s*\d{1,3}\s*[.)]\s*(주제\s+\d+\s*,?\s*.+)$", line)
        if topic_match:
            line = topic_match.group(1).strip()
        if re.search(r"\d{1,3}\s*[~～-]\s*\d{1,3}\s*번\s*문제\)?", line):
            continue
        if re.fullmatch(r"\(?\s*\d{1,3}\s*[~～-]\s*\d{1,3}\s*\)?", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _nonempty_line_count(text: Optional[str]) -> int:
    return len([line for line in (text or "").splitlines() if line.strip()])


def _page_image_paths_for_lines(cfg: ParserConfig, lines: List[PdfTextLine], start: int, end: int) -> List[str]:
    pages = []
    for line in lines[start:end]:
        if line.page not in pages:
            pages.append(line.page)
    paths = []
    for page in pages:
        path = cfg.image_dir / f"page_{page}.jpg"
        if path.exists():
            paths.append(path.as_posix())
    return paths


def crop_pdf_question_image(cfg: ParserConfig, lines: List[PdfTextLine], qrange: QuestionRange) -> Optional[str]:
    cfg.question_image_dir.mkdir(parents=True, exist_ok=True)
    start_line = lines[qrange.start]
    answer_start = None
    for line_index in range(qrange.start, qrange.end):
        if re.match(r"(?i)^\s*(Answer|Explanation|Reference)\s*:", lines[line_index].text) or re.match(r"^\s*(정답|해설)\s*:", lines[line_index].text):
            answer_start = line_index
            break
    answer_line = lines[answer_start] if answer_start is not None else None
    crop_end = answer_start + 1 if answer_start is not None else qrange.end
    answer_lines = [
        lines[line_index]
        for line_index in range(qrange.start, crop_end)
        if re.match(r"(?i)^\s*Answer\s*:", lines[line_index].text) or re.match(r"^\s*정답\s*:", lines[line_index].text)
    ]
    end_line = lines[crop_end - 1] if crop_end - 1 < len(lines) else start_line
    pages = []
    for line in lines[qrange.start : crop_end]:
        if line.page not in pages:
            pages.append(line.page)
    if not pages:
        pages = [start_line.page]

    crops = []
    page_count = len(pages)
    scale = cfg.dpi / 72
    for page in pages:
        page_image = cfg.image_dir / f"page_{page}.jpg"
        if not page_image.exists():
            continue
        with Image.open(page_image) as img:
            width, height = img.size
            if page == start_line.page:
                top = max(0, int(start_line.bbox[1] * scale) - 24)
            else:
                top = 0
            if answer_line and page == answer_line.page:
                bottom = max(top + 80, min(height, int(answer_line.bbox[1] * scale) - 12))
            elif page == end_line.page:
                bottom = min(height, int(end_line.bbox[3] * scale) + 56)
            else:
                bottom = height
            if bottom <= top + 40:
                bottom = min(height, top + 240)
            crop = img.crop((0, top, width, bottom)).convert("RGB")

            page_answer_lines = [line for line in answer_lines if line.page == page]
            if page_answer_lines:
                from PIL import ImageDraw

                draw = ImageDraw.Draw(crop)
                for answer_line in page_answer_lines:
                    mask_top = max(0, int(answer_line.bbox[1] * scale) - top - 8)
                    mask_bottom = min(crop.height, int(answer_line.bbox[3] * scale) - top + 12)
                    if mask_bottom > mask_top:
                        draw.rectangle((0, mask_top, crop.width, mask_bottom), fill=(255, 255, 255))
            crops.append(crop.copy())

    if not crops:
        return None

    if len(crops) == 1:
        stitched = crops[0]
    else:
        divider = 18
        width = max(crop.width for crop in crops)
        height = sum(crop.height for crop in crops) + divider * (len(crops) - 1)
        stitched = Image.new("RGB", (width, height), (255, 255, 255))
        y = 0
        for index, crop in enumerate(crops):
            if crop.width != width:
                padded = Image.new("RGB", (width, crop.height), (255, 255, 255))
                padded.paste(crop, (0, 0))
                crop = padded
            stitched.paste(crop, (0, y))
            y += crop.height
            if index < len(crops) - 1:
                y += divider

    suffix = f"pages_{pages[0]}-{pages[-1]}" if page_count > 1 else f"page_{pages[0]}"
    out_path = cfg.question_image_dir / f"q_{qrange.number}_{suffix}.jpg"
    stitched.save(out_path, "JPEG", quality=90)
    return out_path.as_posix()


def parse_pdf_text_first(cfg: ParserConfig, progress_callback=None) -> List[dict]:
    _log("INFO", "[STEP 2] PDF 내장 텍스트 기반 파싱 시도")
    lines = extract_pdf_text_lines(cfg.pdf_path)
    ranges = split_pdf_lines_to_ranges(lines)
    answer_count = sum(1 for line in lines if re.match(r"(?i)^Answer\s*:", line.text))
    if len(ranges) < 20 or answer_count < 20:
        _log("INFO", f"내장 텍스트 문항 후보 부족(lines={len(lines)}, ranges={len(ranges)}, answers={answer_count})")
        return []

    results = []
    active_group = None
    for index, qrange in enumerate(ranges, 1):
        chunk = clean_question_text("\n".join(line.text for line in lines[qrange.start : qrange.end]))
        answer, without_answer = _extract_answer(chunk)
        before_expl, explanation = _split_explanation(without_answer)
        stem, options = _extract_options(before_expl)
        question_type = _detect_structured_type(chunk, options, answer)
        marker = _group_marker(stem)
        parent_stem = None
        parent_image_paths = []
        group_id = None
        topic_intro_number = _topic_intro_number(stem)
        if marker:
            group_start, group_end = marker
            parent_stem, stem = _split_parent_and_child(stem)
            parent_line_end = qrange.start + max(_nonempty_line_count(parent_stem), 1)
            parent_image_paths = _page_image_paths_for_lines(cfg, lines, qrange.start, min(parent_line_end, qrange.end))
            active_group = {
                "end": group_end,
                "group_id": f"q{group_start}-{group_end}",
                "parent_stem": parent_stem or _clean_parent_stem(before_expl),
                "parent_image_paths": parent_image_paths,
            }
        elif topic_intro_number and answer:
            parent_stem, split_stem = _split_topic_parent_and_child(stem)
            if parent_stem:
                stem = split_stem
                parent_line_end = qrange.start + max(_nonempty_line_count(parent_stem), 1)
                parent_image_paths = _page_image_paths_for_lines(cfg, lines, qrange.start, min(parent_line_end, qrange.end))
                active_group = {
                    "end": None,
                    "group_id": f"q{topic_intro_number}-case",
                    "parent_stem": _clean_parent_stem(parent_stem),
                    "parent_image_paths": parent_image_paths,
                }
        elif topic_intro_number and not answer and not options:
            parent_image_paths = _page_image_paths_for_lines(cfg, lines, qrange.start, qrange.end)
            active_group = {
                "end": None,
                "group_id": f"q{topic_intro_number}-case",
                "parent_stem": _clean_parent_stem(before_expl),
                "parent_image_paths": parent_image_paths,
            }
            _emit(
                progress_callback,
                stage="text_parse",
                message=f"공통 지문 저장 q.{topic_intro_number}",
                current=index,
                total=len(ranges),
            )
            continue
        elif topic_intro_number and active_group and active_group.get("end") is None:
            active_group = None

        if active_group and active_group.get("end") is None:
            group_id = active_group["group_id"]
            parent_stem = parent_stem or active_group["parent_stem"]
            parent_image_paths = parent_image_paths or active_group.get("parent_image_paths", [])
        elif active_group and qrange.number <= active_group["end"]:
            group_id = active_group["group_id"]
            parent_stem = parent_stem or active_group["parent_stem"]
            parent_image_paths = parent_image_paths or active_group.get("parent_image_paths", [])
        elif active_group and qrange.number > active_group["end"]:
            active_group = None

        if marker and not answer and not options:
            _emit(
                progress_callback,
                stage="text_parse",
                message=f"공통 지문 저장 q.{qrange.number}",
                current=index,
                total=len(ranges),
            )
            continue

        image_path = crop_pdf_question_image(cfg, lines, qrange)
        result = {
            "page": lines[qrange.start].page,
            "number": qrange.number,
            "group_id": group_id,
            "parent_stem": parent_stem,
            "parent_image_paths": parent_image_paths,
            "stem": stem or before_expl[:1200],
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "question_type": question_type,
            "image_path": image_path,
            "raw_text": chunk,
            "parse_status": "draft"
            if stem and answer and (options or question_type in {"hotspot", "yes_no", "ordering", "table_choice", "matching"})
            else "needs_review",
        }
        results.append(result)
        _emit(
            progress_callback,
            stage="text_parse",
            message=f"PDF 텍스트 문항 파싱 {index}/{len(ranges)}",
            current=index,
            total=len(ranges),
        )

    _log("INFO", f"[STEP 2] PDF 내장 텍스트 파싱 완료 ({len(results)}개)")
    return results

# ----------------------------------------------
# PDF → 이미지 변환
# ----------------------------------------------
def _pdf_page_count(pdf_path: str) -> int:
    try:
        from pdf2image.pdf2image import pdfinfo_from_path

        return int(pdfinfo_from_path(pdf_path).get("Pages") or 0)
    except Exception:
        import fitz

        with fitz.open(pdf_path) as doc:
            return doc.page_count


def pdf_to_images(cfg: ParserConfig, progress_callback=None) -> List[Path]:
    _log("INFO", f"[STEP 1] PDF → 이미지 변환 중... ({cfg.dpi}dpi)")

    cfg.image_dir.mkdir(parents=True, exist_ok=True)
    try:
        page_count = _pdf_page_count(cfg.pdf_path)
    except (PDFInfoNotInstalledError, PDFPageCountError) as exc:
        _log("WARN", f"PDF 페이지 수 확인 실패, PyMuPDF로 전환합니다: {exc}")
        import fitz

        with fitz.open(cfg.pdf_path) as doc:
            page_count = doc.page_count

    existing = {int(m.group(1)): path for path in _page_images(cfg.image_dir) if (m := re.search(r"page_(\d+)", path.name))}
    if page_count and len(existing) >= page_count:
        _log("INFO", f"[STEP 1] 기존 이미지 {len(existing)}개 발견 → 변환 스킵")
        _emit(
            progress_callback,
            stage="render",
            message=f"기존 페이지 이미지 {len(existing)}개를 사용합니다.",
            current=len(existing),
            total=page_count,
        )
        return [existing[i] for i in sorted(existing)]

    paths = []
    for page_num in range(1, page_count + 1):
        path = cfg.image_dir / f"page_{page_num}.jpg"
        if path.exists():
            paths.append(path)
            _emit(
                progress_callback,
                stage="render",
                message=f"기존 페이지 이미지 사용 p.{page_num}",
                current=page_num,
                total=page_count,
            )
            continue

        try:
            pages = convert_from_path(
                cfg.pdf_path,
                dpi=cfg.dpi,
                first_page=page_num,
                last_page=page_num,
                thread_count=1,
            )
            if pages:
                pages[0].save(path, "JPEG", quality=90)
                paths.append(path)
        except PDFInfoNotInstalledError:
            _log("WARN", "Poppler를 찾을 수 없어 PyMuPDF 렌더링으로 전환합니다.")
            import fitz

            zoom = cfg.dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            with fitz.open(cfg.pdf_path) as doc:
                page = doc.load_page(page_num - 1)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                pix.save(path)
                paths.append(path)

        _emit(
            progress_callback,
            stage="render",
            message=f"페이지 이미지 변환 p.{page_num}",
            current=page_num,
            total=page_count,
        )

    _log("INFO", f"[STEP 1] 완료 ({len(paths)}페이지)")
    return paths

# ----------------------------------------------
# OCR 실행 (자동 스킵)
# ----------------------------------------------
def run_ocr(cfg: ParserConfig, ocr: PaddleOCR, img_paths: List[Path]) -> Dict[int, str]:
    _log("INFO", "[STEP 2] OCR 단계 시작 (자동 스킵 감지)")
    ocr_map = {}

    cfg.ocr_log_dir.mkdir(parents=True, exist_ok=True)
    existing_txts = sorted(cfg.ocr_log_dir.glob("page_*.txt"))

    # ✅ 기존 OCR 텍스트 결과 존재 시에만 스킵
    if existing_txts:
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
        return ocr_map

    # ✅ OCR 신규 수행
    _log("INFO", "[STEP 2] OCR 신규 수행 중...")
    def ocr_one(img_path: Path):
        m = re.search(r"page[_-]?(\d+)", img_path.name)
        page = int(m.group(1)) if m else 0
        cache_path = cfg.ocr_log_dir / f"page_{page}.txt"

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
    if not merged:
        for p in sorted(ocr_map.keys()):
            txt = clean_text(ocr_map[p])
            if len(txt) >= 50 and not txt.startswith("[SKIP OCR]"):
                merged.append((p, txt))
    return merged


def load_partial_results(partial_jsonl: Path) -> Tuple[List[dict], set]:
    results = []
    keys = set()
    if not partial_jsonl.exists():
        return results, keys

    with partial_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except Exception:
                continue
            item = row.get("result") if isinstance(row, dict) else None
            key = row.get("key") if isinstance(row, dict) else None
            if item and key:
                results.append(item)
                keys.add(key)
    return results, keys


def append_partial_result(partial_jsonl: Path, key: str, result: dict) -> None:
    partial_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with partial_jsonl.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "result": result}, ensure_ascii=False) + "\n")


def create_question_crops(
    cfg: ParserConfig,
    items: List[Tuple[int, str]],
    progress_callback=None,
) -> Dict[int, str]:
    cfg.question_image_dir.mkdir(parents=True, exist_ok=True)
    by_page: Dict[int, List[int]] = {}
    for idx, (page, _text) in enumerate(items):
        by_page.setdefault(page, []).append(idx)

    image_paths: Dict[int, str] = {}
    total = max(len(items), 1)
    done = 0
    for page, item_indexes in by_page.items():
        page_image = cfg.image_dir / f"page_{page}.jpg"
        if not page_image.exists():
            continue

        with Image.open(page_image) as img:
            width, height = img.size
            band_count = len(item_indexes)
            for position, item_index in enumerate(item_indexes):
                top = max(0, int(height * position / band_count) - 60)
                bottom = min(height, int(height * (position + 1) / band_count) + 60)
                crop = img.crop((0, top, width, bottom))
                out_path = cfg.question_image_dir / f"page_{page}_q{position + 1}.jpg"
                crop.save(out_path, "JPEG", quality=88)
                image_paths[item_index] = out_path.as_posix()
                done += 1
                _emit(
                    progress_callback,
                    stage="crop",
                    message=f"문항 이미지 생성 p.{page} ({done}/{total})",
                    current=done,
                    total=total,
                )
    return image_paths

def load_llm(cfg: ParserConfig):
    if cfg.llm_provider == "ollama":
        _log("INFO", f"[STEP 4] Ollama LLM 연결 중... ({cfg.ollama_model}, {cfg.ollama_base_url})")
        from langchain_community.llms import Ollama

        return Ollama(
            model=cfg.ollama_model,
            base_url=cfg.ollama_base_url,
            temperature=0,
        )

    _log("INFO", f"[STEP 4] Hugging Face LLM 로드 중... ({cfg.llm_model})")
    tok = AutoTokenizer.from_pretrained(cfg.llm_model)
    mdl = AutoModelForCausalLM.from_pretrained(cfg.llm_model, torch_dtype="auto", low_cpu_mem_usage=True)
    pipe = pipeline("text-generation", model=mdl, tokenizer=tok, device=-1, max_new_tokens=cfg.max_new_tokens, temperature=0.0)
    _log("INFO", "[STEP 4] LLM 로드 완료")
    return HuggingFacePipeline(pipeline=pipe)

# ----------------------------------------------
# 메인 파이프라인
# ----------------------------------------------
def parse_pdf(
    pdf_path: str,
    output_json: str,
    use_llm=True,
    lang="korean",
    dpi: Optional[int] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
    progress_callback=None,
):
    torch.set_num_threads(1)
    cfg = ParserConfig(pdf_path, output_json, use_llm, lang)
    cfg.job_name = _job_name(pdf_path)
    cfg.image_dir = IMAGE_DIR / cfg.job_name
    cfg.question_image_dir = QUESTION_IMAGE_DIR / cfg.job_name
    cfg.ocr_log_dir = OCR_LOG_DIR / cfg.job_name
    cfg.partial_jsonl = RUN_LOG_DIR / f"{cfg.job_name}.partial.jsonl"
    if dpi:
        cfg.dpi = dpi
    if llm_provider:
        cfg.llm_provider = llm_provider
    if llm_model:
        if cfg.llm_provider == "ollama":
            cfg.ollama_model = llm_model
        else:
            cfg.llm_model = llm_model
    if ollama_base_url:
        cfg.ollama_base_url = ollama_base_url

    _log("INFO", f"[START] {pdf_path} (dpi={cfg.dpi}, threads={cfg.cpu_threads})")
    _emit(progress_callback, stage="start", message="파싱을 시작합니다.", current=0, total=1)

    # STEP 1: PDF → 이미지 (있으면 스킵)
    _emit(progress_callback, stage="render", message="PDF를 페이지 이미지로 변환합니다.", current=0, total=1)
    pages = pdf_to_images(cfg, progress_callback=progress_callback)
    _emit(progress_callback, stage="render", message=f"페이지 이미지 {len(pages)}개 준비 완료", current=len(pages), total=len(pages) or 1)

    text_results = parse_pdf_text_first(cfg, progress_callback=progress_callback)
    if text_results:
        Path(output_json).write_text(json.dumps(text_results, ensure_ascii=False, indent=2), encoding="utf-8")
        _log("INFO", f"[DONE] PDF 텍스트 기반 총 {len(text_results)} 문항 저장 → {output_json}")
        _emit(
            progress_callback,
            stage="done",
            message=f"PDF 텍스트 기반 {len(text_results)}문항 파싱 완료",
            current=len(text_results),
            total=len(text_results),
        )
        return text_results

    # STEP 2: OCR (있으면 스킵)
    _emit(progress_callback, stage="ocr", message="OCR 텍스트를 준비합니다.", current=0, total=len(pages) or 1)
    ocr = create_ocr(cfg.lang, cfg.cpu_threads)
    ocr_map = run_ocr(cfg, ocr, pages)
    _emit(progress_callback, stage="ocr", message=f"OCR 텍스트 {len(ocr_map)}페이지 준비 완료", current=len(ocr_map), total=len(pages) or len(ocr_map) or 1)

    # STEP 3: 문항 병합
    items = merge_pages_to_questions(ocr_map)
    _log("INFO", f"[STEP 3] 문항 병합 완료 ({len(items)}개)")
    _emit(progress_callback, stage="split", message=f"문항 후보 {len(items)}개를 찾았습니다.", current=0, total=len(items) or 1)
    item_images = create_question_crops(cfg, items, progress_callback=progress_callback)

    # STEP 4: LLM 파싱
    results, parsed_keys = load_partial_results(cfg.partial_jsonl)
    if results:
        _log("INFO", f"[RESUME] 부분 저장 결과 {len(results)}개 로드 → 이미 처리한 문항 스킵")
        _emit(
            progress_callback,
            stage="resume",
            message=f"이전 부분 저장 {len(results)}개를 이어서 사용합니다.",
            current=len(results),
            total=len(items) or len(results) or 1,
        )

    if use_llm:
        try:
            llm = load_llm(cfg)
        except Exception as e:
            _log("WARN", f"LLM 로드 실패 → 기본 파싱으로 계속 진행합니다: {e}")
            use_llm = False
        else:
            for index, (p, t) in enumerate(items, 1):
                key = _item_key(p, t)
                if key in parsed_keys:
                    _emit(
                        progress_callback,
                        stage="llm",
                        message=f"이미 처리한 문항을 건너뜁니다. ({index}/{len(items)})",
                        current=index,
                        total=len(items),
                    )
                    continue
                _emit(
                    progress_callback,
                    stage="llm",
                    message=f"Qwen으로 문항을 정제합니다. p.{p} ({index}/{len(items)})",
                    current=index - 1,
                    total=len(items),
                )
                try:
                    parsed = parse_question_with_chain(llm, p, t)
                except Exception as e:
                    parsed = {
                        "page": p,
                        "stem": t[:400],
                        "options": [],
                        "answer": [],
                        "explanation": f"LLM 실패: {e}",
                        "question_type": "mcq"
                    }
                parsed["raw_text"] = parsed.get("raw_text") or t
                parsed["chunk_index"] = index
                parsed["chunk_key"] = key
                if index - 1 in item_images:
                    parsed["image_path"] = item_images[index - 1]
                results.append(parsed)
                parsed_keys.add(key)
                append_partial_result(cfg.partial_jsonl, key, parsed)
                Path(output_json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
                _emit(
                    progress_callback,
                    stage="llm",
                    message=f"문항 {len(results)}개 저장됨",
                    current=index,
                    total=len(items),
                )

    if not use_llm:
        for index, (p, t) in enumerate(items, 1):
            key = _item_key(p, t)
            if key in parsed_keys:
                continue
            parsed = {
                "page": p,
                "stem": t[:400],
                "options": [],
                "answer": [],
                "explanation": "",
                "question_type": "mcq",
                "image_path": item_images.get(index - 1),
                "raw_text": t,
                "chunk_index": index,
                "chunk_key": key,
            }
            results.append(parsed)
            parsed_keys.add(key)
            append_partial_result(cfg.partial_jsonl, key, parsed)
            _emit(progress_callback, stage="basic", message=f"기본 파싱 {index}/{len(items)}", current=index, total=len(items))

    if not use_llm and not results:
        for index, (p, t) in enumerate(items, 1):
            results.append({
                "page": p,
                "stem": t[:400],
                "options": [],
                "answer": [],
                "explanation": "",
                "question_type": "mcq",
                "raw_text": t,
                "chunk_index": index,
                "chunk_key": _item_key(p, t),
            })

    Path(output_json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("INFO", f"[DONE] 총 {len(results)} 문항 저장 → {output_json}")
    _emit(progress_callback, stage="done", message=f"총 {len(results)}문항 파싱 완료", current=len(results), total=len(results) or 1)
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

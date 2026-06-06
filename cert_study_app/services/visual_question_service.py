import base64
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from cert_study_app.models import Question
from cert_study_app.services.question_concept_service import apply_question_concept


VISUAL_MODEL = os.getenv("OLLAMA_VISUAL_MODEL", "qwen3-vl:8b-instruct-q4_K_M")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _image_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _json_from_response(text: str) -> dict:
    if not text:
        return {}
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except Exception:
        return {"raw_response": text}


def analyze_visual_question(question: Question, model: str = VISUAL_MODEL, base_url: str = OLLAMA_BASE_URL) -> dict:
    if not question.image_path or not Path(question.image_path).exists():
        return {"ok": False, "error": "image_not_found"}

    prompt = f"""
You are an exam question image parser.
Look at the image and the OCR text. Return JSON only. No reasoning.

Fields:
- question_type: one of hotspot, ordering, matching, table_choice, yes_no, mcq, unparsed
- stem: clean Korean question text without answer/explanation and without duplicated answer-area row labels
- source_content: visible code, JSON, table, diagram text, configuration, or other source material that the question asks about
- options: array of visible selectable choices, if any
- answer: answer shown in OCR text or image, if visible in source data
- answer_areas: for hotspot/table dropdown questions, array of objects with:
  - label: left-side prompt text such as "From the Azure portal"
  - selected_answer: selected value for that row if visible
  - options: selectable choices for that row if visible
- statements: for Yes/No matrix questions, array of objects with:
  - text: statement text
  - selected_answer: Yes or No if visible
- confidence: integer 0-100
- notes: short Korean note

Rules:
- If the question refers to a shown code block, JSON, table, role definition, policy, diagram, or configuration, put that visible material in source_content.
- Do not repeat answer_areas labels in stem. Keep the common instruction in stem and put row-specific prompts only in answer_areas.
- If the image has dropdown boxes, preserve each left-side label exactly and put it in answer_areas.
- If the image has a Statements / Yes / No table, preserve every statement row in statements.
- For highlighted or circled answers, include selected_answer.
- Do not infer from Azure knowledge. Parse only what is visible in the image/OCR.

OCR text:
{(question.raw_text or question.stem or '')[:1800]}
"""
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [_image_base64(question.image_path)],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": 1400,
        },
    }
    response = requests.post(f"{base_url.rstrip('/')}/api/generate", json=payload, timeout=180)
    response.raise_for_status()
    body = response.json()
    parsed = _json_from_response(body.get("response", ""))
    parsed.setdefault("model", model)
    parsed.setdefault("ok", True)
    return parsed


def apply_visual_analysis(question: Question, analysis: dict) -> None:
    if analysis.get("raw_response") and not any(
        key in analysis for key in ["stem", "source_content", "options", "answer_areas", "statements"]
    ):
        question.review_issues = json.dumps(["이미지 분석 응답이 구조화 JSON으로 완성되지 않았습니다."], ensure_ascii=False)
        return

    question.visual_analysis_json = json.dumps(analysis, ensure_ascii=False)
    question.visual_reviewed_at = datetime.utcnow()

    if not analysis.get("ok", True):
        question.review_issues = json.dumps([analysis.get("error", "이미지 분석 실패")], ensure_ascii=False)
        question.parse_status = "needs_visual"
        return

    options = analysis.get("options")
    answer = analysis.get("answer")
    answer_areas = analysis.get("answer_areas")
    statements = analysis.get("statements")
    stem = analysis.get("stem")
    question_type = analysis.get("question_type")
    confidence = int(analysis.get("confidence") or 0)

    if isinstance(options, list) and options:
        question.set_options(options)
    if answer and not question.answer:
        question.answer = str(answer).strip()
    if stem and len(str(stem).strip()) > 20:
        question.stem = str(stem).strip()
    if question_type:
        question.question_type = str(question_type).strip()
    apply_question_concept(question, overwrite=False)

    if confidence >= 70:
        question.review_score = max(question.review_score or 0, confidence)
        question.review_issues = json.dumps([], ensure_ascii=False)
        if options and (answer or answer_areas or statements):
            question.parse_status = "approved"
            question.reviewed_at = datetime.utcnow()
        elif question.parse_status != "approved":
            question.parse_status = "needs_visual"


def run_visual_analysis(db, source: Optional[str] = None, limit: int = 10, model: str = VISUAL_MODEL) -> dict:
    query = db.query(Question).filter(Question.parse_status.in_(["needs_visual", "needs_review"]))
    query = query.filter(Question.question_type.in_(["hotspot", "ordering", "matching", "table_choice", "yes_no"]))
    if source:
        query = query.filter(Question.source == source)

    questions = (
        query.order_by(
            Question.parse_status.asc(),
            Question.id.asc(),
        )
        .limit(limit)
        .all()
    )
    summary = {"checked": 0, "approved": 0, "needs_visual": 0, "failed": 0}
    total = len(questions)
    print(f"[visual] targets={total} source={source or 'all'} model={model}", flush=True)
    for index, question in enumerate(questions, 1):
        try:
            analysis = analyze_visual_question(question, model=model)
            apply_visual_analysis(question, analysis)
        except Exception as exc:
            apply_visual_analysis(question, {"ok": False, "error": str(exc)[:300], "model": model})
            summary["failed"] += 1
        summary["checked"] += 1
        if question.parse_status == "approved":
            summary["approved"] += 1
        elif question.parse_status == "needs_visual":
            summary["needs_visual"] += 1
        db.commit()
        print(
            f"[visual] {index}/{total} q{question.question_number or question.id} "
            f"{question.parse_status} {question.question_type}",
            flush=True,
        )
    return summary

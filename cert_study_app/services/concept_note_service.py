from __future__ import annotations

import json
import re
from typing import Optional

import requests
from sqlalchemy import or_

from cert_study_app.config import DEFAULT_USER
from cert_study_app.models import ConceptNote, Question


CONCEPT_PROMPT = """
너는 자격증 시험 학습 노트 큐레이터다.
아래 문제에서 저장할 만한 개념 후보를 1~3개만 제안하라.
너무 세부적인 문제 상황이 아니라 재사용 가능한 시험 개념으로 추상화하라.
JSON만 반환하라.

형식:
{
  "concepts": [
    {
      "concept_name": "개념명",
      "summary": "핵심 요약 1~2문장",
      "exam_point": "시험장에서 기억할 포인트",
      "trap_point": "헷갈릴 포인트",
      "keywords": ["keyword1", "keyword2"]
    }
  ]
}

문제:
{stem}

보기:
{options}

정답:
{answer}

해설:
{explanation}
"""


def _json_from_response(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except Exception:
        return {"concepts": []}


class ConceptNoteService:
    def __init__(self, db):
        self.db = db

    def generate_candidates(
        self,
        question_id: int,
        model: str = "qwen2.5:14b",
        base_url: str = "http://localhost:11434",
    ) -> list[dict]:
        question = self.db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return []

        prompt = CONCEPT_PROMPT.format(
            stem=(question.stem or "")[:1600],
            options="\n".join(str(option) for option in question.get_options())[:1200],
            answer=question.answer or "",
            explanation=(question.explanation or "")[:1600],
        )
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": 0, "num_predict": 700},
        }
        response = requests.post(f"{base_url.rstrip('/')}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
        parsed = _json_from_response(response.json().get("response", ""))
        concepts = parsed.get("concepts") if isinstance(parsed, dict) else []
        return [self._normalize_candidate(item) for item in concepts if isinstance(item, dict)][:3]

    def save_candidate(
        self,
        candidate: dict,
        question_id: int,
        user_id: str = DEFAULT_USER,
    ) -> ConceptNote:
        question = self.db.query(Question).filter(Question.id == question_id).first()
        note = ConceptNote(
            concept_name=str(candidate.get("concept_name") or "").strip()[:255],
            summary=str(candidate.get("summary") or "").strip(),
            exam_point=str(candidate.get("exam_point") or "").strip(),
            trap_point=str(candidate.get("trap_point") or "").strip(),
            source=question.source if question else None,
            source_question_id=question_id,
            user_id=user_id,
        )
        note.set_keywords(candidate.get("keywords") or [])
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def list_notes(self, source: Optional[str] = None, query: str = "", limit: int = 100) -> list[ConceptNote]:
        rows = self.db.query(ConceptNote)
        if source:
            rows = rows.filter(ConceptNote.source == source)
        if query:
            like = f"%{query.strip()}%"
            rows = rows.filter(
                or_(
                    ConceptNote.concept_name.ilike(like),
                    ConceptNote.summary.ilike(like),
                    ConceptNote.exam_point.ilike(like),
                    ConceptNote.trap_point.ilike(like),
                    ConceptNote.keywords.ilike(like),
                )
            )
        return rows.order_by(ConceptNote.updated_at.desc(), ConceptNote.id.desc()).limit(limit).all()

    def get_note(self, note_id: int) -> ConceptNote | None:
        return self.db.query(ConceptNote).filter(ConceptNote.id == note_id).first()

    def related_questions(self, note: ConceptNote, limit: int = 20) -> list[Question]:
        keywords = [note.concept_name, *note.keyword_list()]
        keywords = [keyword for keyword in keywords if str(keyword or "").strip()]
        if not keywords:
            return []
        filters = []
        for keyword in keywords[:8]:
            like = f"%{keyword}%"
            filters.append(Question.stem.ilike(like))
            filters.append(Question.explanation.ilike(like))
            filters.append(Question.raw_text.ilike(like))
        query = self.db.query(Question).filter(Question.parse_status == "approved")
        if note.source:
            query = query.filter(Question.source == note.source)
        return query.filter(or_(*filters)).order_by(Question.id.asc()).limit(limit).all()

    def _normalize_candidate(self, item: dict) -> dict:
        keywords = item.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [keyword.strip() for keyword in re.split(r"[,#]", keywords) if keyword.strip()]
        return {
            "concept_name": str(item.get("concept_name") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
            "exam_point": str(item.get("exam_point") or "").strip(),
            "trap_point": str(item.get("trap_point") or "").strip(),
            "keywords": [str(keyword).strip() for keyword in keywords if str(keyword).strip()][:8],
        }

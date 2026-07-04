from __future__ import annotations

from functools import lru_cache
import hashlib
import time

from cert_study_app.chains.study_assistant_chain import build_ollama_llm, build_study_assistant_chain
from cert_study_app.models import Question
from cert_study_app.services.official_docs_service import LEGACY_AZURE_DOCS_COLLECTION, OFFICIAL_DOCS_COLLECTION
from cert_study_app.services.vector_service import QuestionVectorStore


_ANSWER_CACHE: dict[str, tuple[float, dict]] = {}
ANSWER_CACHE_TTL_SECONDS = 600
ANSWER_PROMPT_VERSION = "ko-summary-v2"


@lru_cache(maxsize=8)
def cached_ollama_llm(model: str, base_url: str, temperature: float, num_predict: int):
    return build_ollama_llm(model=model, base_url=base_url, temperature=temperature, num_predict=num_predict)


@lru_cache(maxsize=8)
def cached_study_chain(model: str, base_url: str, temperature: float, num_predict: int):
    llm = cached_ollama_llm(model, base_url, temperature, num_predict)
    return build_study_assistant_chain(llm)


def _cache_key(
    question: str,
    model: str,
    base_url: str,
    k: int,
    source: str | None,
    max_context_chars: int,
    embedding_model: str,
) -> str:
    raw = "|".join(
        [ANSWER_PROMPT_VERSION, question, model, base_url, str(k), source or "", str(max_context_chars), embedding_model]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class StudyAssistantService:
    def __init__(self, db, vector_store: QuestionVectorStore | None = None):
        self.db = db
        self.vector_store = vector_store or QuestionVectorStore()
        self.docs_vector_store = QuestionVectorStore(
            collection_name=OFFICIAL_DOCS_COLLECTION,
            embedding_model=self.vector_store.embedding_model,
        )
        self.legacy_docs_vector_store = QuestionVectorStore(
            collection_name=LEGACY_AZURE_DOCS_COLLECTION,
            embedding_model=self.vector_store.embedding_model,
        )

    def index_questions(self) -> int:
        questions = self.db.query(Question).order_by(Question.id.asc()).all()
        payloads = []
        for question in questions:
            payloads.append(
                {
                    "id": question.id,
                    "stem": question.stem,
                    "options": question.get_options(),
                    "answer": question.answer,
                    "explanation": question.explanation,
                    "category": question.category,
                    "subcategory": question.subcategory,
                    "source": question.source,
                }
            )
        return self.vector_store.upsert_questions(payloads)

    def ask(
        self,
        question: str,
        model: str = "qwen2.5:14b",
        base_url: str = "http://localhost:11434",
        k: int = 2,
        source: str | None = None,
        max_context_chars: int = 2200,
        use_cache: bool = True,
    ) -> dict:
        key = _cache_key(question, model, base_url, k, source, max_context_chars, self.vector_store.embedding_model)
        now = time.time()
        if use_cache and key in _ANSWER_CACHE:
            cached_at, cached = _ANSWER_CACHE[key]
            if now - cached_at <= ANSWER_CACHE_TTL_SECONDS:
                return {**cached, "cached": True}

        doc_results = self._search_docs(question, k=min(3, max(1, k)))
        question_results = self.vector_store.search(question, k=k, source=source)
        results = [*doc_results, *question_results]
        chain = cached_study_chain(model, base_url, 0.2, 320)
        answer = chain.invoke(
            {
                "question": question,
                "results": results,
                "max_context_chars": max_context_chars,
            }
        )
        payload = {
            "answer": answer,
            "sources": [
                {
                    "id": item.id,
                    "score": item.score,
                    "text": item.text,
                    "metadata": item.metadata or {},
                }
                for item in results
            ],
            "cached": False,
        }
        if use_cache:
            _ANSWER_CACHE[key] = (now, payload)
        return payload

    def ask_stream(
        self,
        question: str,
        model: str = "qwen2.5:14b",
        base_url: str = "http://localhost:11434",
        k: int = 2,
        source: str | None = None,
        max_context_chars: int = 2200,
        use_cache: bool = True,
    ) -> dict:
        key = _cache_key(question, model, base_url, k, source, max_context_chars, self.vector_store.embedding_model)
        now = time.time()
        if use_cache and key in _ANSWER_CACHE:
            cached_at, cached = _ANSWER_CACHE[key]
            if now - cached_at <= ANSWER_CACHE_TTL_SECONDS:
                return {**cached, "cached": True, "stream": None}

        doc_results = self._search_docs(question, k=min(3, max(1, k)))
        question_results = self.vector_store.search(question, k=k, source=source)
        results = [*doc_results, *question_results]
        chain = cached_study_chain(model, base_url, 0.2, 320)
        sources = [
            {
                "id": item.id,
                "score": item.score,
                "text": item.text,
                "metadata": item.metadata or {},
            }
            for item in results
        ]

        def stream_chunks():
            chunks = []
            try:
                for chunk in chain.stream(
                    {
                        "question": question,
                        "results": results,
                        "max_context_chars": max_context_chars,
                    }
                ):
                    text = str(chunk or "")
                    if not text:
                        continue
                    chunks.append(text)
                    yield text
            except Exception as exc:
                error_msg = f"\n\n*(Ollama 응답 오류: {exc})*"
                chunks.append(error_msg)
                yield error_msg
                return
            if use_cache:
                _ANSWER_CACHE[key] = (
                    time.time(),
                    {
                        "answer": "".join(chunks),
                        "sources": sources,
                        "cached": False,
                    },
                )

        return {"stream": stream_chunks(), "sources": sources, "cached": False}

    def _search_docs(self, question: str, k: int):
        official_results = self.docs_vector_store.search(question, k=k)
        if official_results:
            return official_results
        return self.legacy_docs_vector_store.search(question, k=k)

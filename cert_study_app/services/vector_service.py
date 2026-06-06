from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from cert_study_app.config import BASE_DIR


DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")


@dataclass
class VectorSearchResult:
    id: str
    text: str
    score: Optional[float] = None
    metadata: Optional[dict] = None


class QuestionVectorStore:
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "questions",
        embedding_model: Optional[str] = None,
    ):
        self.persist_dir = persist_dir or str(BASE_DIR / "chroma_db")
        self.base_collection_name = collection_name
        self.embedding_model = embedding_model or DEFAULT_EMBEDDING_MODEL
        self.collection_name = _collection_name(collection_name, self.embedding_model)
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        import chromadb
        from chromadb.utils import embedding_functions

        self._client = chromadb.PersistentClient(path=self.persist_dir)
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model,
        )
        self._collection = self._client.get_or_create_collection(
            self.collection_name,
            embedding_function=embedding_function,
            metadata={
                "base_collection": self.base_collection_name,
                "embedding_model": self.embedding_model,
            },
        )
        return self._collection

    def upsert_questions(self, questions: Iterable[dict]) -> int:
        ids = []
        documents = []
        metadatas = []

        for item in questions:
            question_id = str(item["id"])
            ids.append(question_id)
            documents.append(_question_document(item))
            metadatas.append(
                {
                    "answer": item.get("answer", ""),
                    "category": item.get("category") or "",
                    "subcategory": item.get("subcategory") or "",
                    "source": item.get("source") or "",
                    "embedding_model": self.embedding_model,
                }
            )

        if not ids:
            return 0

        self._get_collection().upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def upsert_documents(self, documents: Iterable[dict]) -> int:
        ids = []
        texts = []
        metadatas = []

        for item in documents:
            doc_id = str(item["id"])
            text = str(item.get("text") or "").strip()
            if not doc_id or not text:
                continue
            ids.append(doc_id)
            texts.append(text)
            metadatas.append(
                {
                    "source_type": item.get("source_type") or self.base_collection_name,
                    "source": item.get("source") or "",
                    "title": item.get("title") or "",
                    "url": item.get("url") or "",
                    "category": item.get("category") or "",
                    "subcategory": item.get("subcategory") or "",
                    "embedding_model": self.embedding_model,
                }
            )

        if not ids:
            return 0

        self._get_collection().upsert(ids=ids, documents=texts, metadatas=metadatas)
        return len(ids)

    def search(self, query: str, k: int = 5, source: Optional[str] = None) -> list[VectorSearchResult]:
        kwargs = {"query_texts": [query], "n_results": k}
        if source:
            kwargs["where"] = {"source": source}
        result = self._get_collection().query(**kwargs)
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0] if result.get("distances") else []
        metadatas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []

        items = []
        for idx, item_id in enumerate(ids):
            items.append(
                VectorSearchResult(
                    id=item_id,
                    text=documents[idx] if idx < len(documents) else "",
                    score=distances[idx] if idx < len(distances) else None,
                    metadata=metadatas[idx] if idx < len(metadatas) else None,
                )
            )
        return items


def _question_document(item: dict) -> str:
    parts = [f"문제: {item.get('stem') or ''}"]

    options = item.get("options") or {}
    if isinstance(options, dict) and options:
        rendered_options = "\n".join(f"{key}. {value}" for key, value in sorted(options.items()))
        parts.append(f"보기:\n{rendered_options}")
    elif isinstance(options, list) and options:
        parts.append("보기:\n" + "\n".join(str(option) for option in options))

    if item.get("answer"):
        parts.append(f"정답: {item['answer']}")
    if item.get("explanation"):
        parts.append(f"해설: {item['explanation']}")
    if item.get("category") or item.get("subcategory"):
        parts.append(f"분류: {item.get('category') or ''} / {item.get('subcategory') or ''}")

    return "\n".join(parts)


def _collection_name(base: str, embedding_model: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", embedding_model).strip("_").lower()
    name = f"{base}_{slug}" if slug else base
    return name[:63].strip("._-") or base

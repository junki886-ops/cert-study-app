from __future__ import annotations

import hashlib
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional

import requests

from cert_study_app.models import AzureDocsSync
from cert_study_app.services.vector_service import DEFAULT_EMBEDDING_MODEL, QuestionVectorStore


AZURE_DOC_URLS = [
    "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-overview",
    "https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview",
    "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-service-endpoints-overview",
    "https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-overview",
    "https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview",
    "https://learn.microsoft.com/en-us/azure/application-gateway/overview",
    "https://learn.microsoft.com/en-us/azure/virtual-machines/overview",
    "https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview",
    "https://learn.microsoft.com/en-us/azure/role-based-access-control/overview",
    "https://learn.microsoft.com/en-us/entra/identity/role-based-access-control/permissions-reference",
    "https://learn.microsoft.com/en-us/azure/azure-monitor/overview",
    "https://learn.microsoft.com/en-us/azure/backup/backup-overview",
]


class _MainTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "td", "th"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", data or "").strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        if not self._skip_depth:
            self._chunks.append(text)

    def text(self) -> str:
        text = " ".join(self._chunks)
        text = re.sub(r"\s*\n\s*", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


def _chunk_text(text: str, chunk_size: int = 1400, overlap: int = 180) -> list[str]:
    clean = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        start = max(0, end - overlap)
    return chunks


def _doc_id(url: str, index: int, text: str) -> str:
    digest = hashlib.sha1(f"{url}|{index}|{text}".encode("utf-8")).hexdigest()[:16]
    return f"azure_docs:{digest}"


class AzureDocsService:
    def __init__(self, db, embedding_model: Optional[str] = None, urls: Optional[list[str]] = None):
        self.db = db
        self.embedding_model = embedding_model or DEFAULT_EMBEDDING_MODEL
        self.urls = urls or AZURE_DOC_URLS
        self.vector_store = QuestionVectorStore(
            collection_name="azure_docs",
            embedding_model=self.embedding_model,
        )

    def latest_sync(self) -> AzureDocsSync | None:
        return self.db.query(AzureDocsSync).order_by(AzureDocsSync.id.desc()).first()

    def sync(self, limit: Optional[int] = None) -> dict:
        sync = AzureDocsSync(
            embedding_model=self.embedding_model,
            status="running",
            message="Azure Docs 동기화를 시작했습니다.",
            started_at=datetime.utcnow(),
        )
        self.db.add(sync)
        self.db.commit()

        urls = self.urls[: int(limit)] if limit else self.urls
        checked = 0
        docs_indexed = 0
        chunks_indexed = 0
        try:
            for url in urls:
                checked += 1
                response = requests.get(url, timeout=20, headers={"User-Agent": "cert-study-app/1.0"})
                response.raise_for_status()
                parser = _MainTextParser()
                parser.feed(response.text)
                title = parser.title or url.rsplit("/", 1)[-1]
                chunks = _chunk_text(parser.text())
                payloads = [
                    {
                        "id": _doc_id(url, index, chunk),
                        "text": f"Title: {title}\nURL: {url}\n\n{chunk}",
                        "source_type": "azure_docs",
                        "source": "Microsoft Learn",
                        "title": title,
                        "url": url,
                        "category": _category_from_url(url),
                    }
                    for index, chunk in enumerate(chunks, 1)
                ]
                inserted = self.vector_store.upsert_documents(payloads)
                if inserted:
                    docs_indexed += 1
                    chunks_indexed += inserted

            sync.status = "success"
            sync.message = f"{docs_indexed}개 문서, {chunks_indexed}개 chunk를 색인했습니다."
        except Exception as exc:
            sync.status = "failed"
            sync.error_message = str(exc)[:1000]
            sync.message = "Azure Docs 동기화 실패"
        finally:
            sync.urls_checked = checked
            sync.documents_indexed = docs_indexed
            sync.chunks_indexed = chunks_indexed
            sync.completed_at = datetime.utcnow()
            self.db.commit()

        return {
            "status": sync.status,
            "urls_checked": checked,
            "documents_indexed": docs_indexed,
            "chunks_indexed": chunks_indexed,
            "message": sync.message,
            "error_message": sync.error_message,
        }


def _category_from_url(url: str) -> str:
    if "virtual-network" in url or "private-link" in url or "load-balancer" in url or "application-gateway" in url:
        return "network"
    if "virtual-machines" in url:
        return "compute"
    if "storage" in url:
        return "storage"
    if "role-based-access-control" in url or "entra" in url:
        return "identity"
    if "monitor" in url:
        return "monitor"
    if "backup" in url:
        return "backup"
    return "azure"

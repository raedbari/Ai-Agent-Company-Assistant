import json
import re
from pathlib import Path

from langchain_core.documents import Document

from travelx_agent.domain.service_catalog import Department, ServiceKey

_ARABIC_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
_WORD = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


class KnowledgeBaseConfigurationError(RuntimeError):
    """Raised when the curated knowledge file is missing or invalid."""


def _normalized_tokens(text: str) -> set[str]:
    normalized = _ARABIC_DIACRITICS.sub("", text.casefold())
    normalized = normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    normalized = normalized.replace("ى", "ي")
    return {token for token in _WORD.findall(normalized) if len(token) >= 3}


class TravelXKnowledgeBase:
    def __init__(
        self,
        documents: list[Document],
        *,
        scope_department: Department | None = None,
    ) -> None:
        self._documents = [
            document.model_copy(deep=True)
            for document in documents
        ]
        self._scope_department = scope_department

    @property
    def scope_department(self) -> Department | None:
        return self._scope_department

    def for_department(
        self,
        department: Department,
    ) -> "TravelXKnowledgeBase":
        documents = [
            document
            for document in self._documents
            if document.metadata.get("department")
            in {None, department.value}
        ]

        return TravelXKnowledgeBase(
            documents,
            scope_department=department,
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "TravelXKnowledgeBase":
        knowledge_path = Path(path)
        if not knowledge_path.is_file():
            raise KnowledgeBaseConfigurationError(
                f"Knowledge file does not exist: {knowledge_path}"
            )
        try:
            payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
            raw_documents = payload["documents"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise KnowledgeBaseConfigurationError(
                f"Knowledge file is invalid: {knowledge_path}"
            ) from exc

        documents: list[Document] = []
        seen_ids: set[str] = set()
        for item in raw_documents:
            source_id = str(item["source_id"]).strip()
            content = str(item["content_ar"]).strip()
            if not source_id or not content or source_id in seen_ids:
                raise KnowledgeBaseConfigurationError(
                    "Every knowledge document needs a unique source_id and content_ar"
                )
            seen_ids.add(source_id)
            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source_id": source_id,
                        "title_ar": str(item["title_ar"]),
                        "department": item.get("department"),
                        "service_keys": list(item.get("service_keys", [])),
                        "knowledge_version": payload.get("version", "unknown"),
                        "knowledge_status": payload.get("status", "unknown"),
                    },
                )
            )
        return cls(documents)

    def retrieve(
        self,
        query: str,
        service_key: ServiceKey | None,
        *,
        limit: int = 4,
    ) -> list[Document]:
        query_tokens = _normalized_tokens(query)
        scored: list[tuple[int, Document]] = []
        for document in self._documents:
            metadata = document.metadata
            score = len(query_tokens & _normalized_tokens(document.page_content))
            if service_key and service_key.value in metadata.get("service_keys", []):
                score += 100
            if metadata.get("source_id") == "travelx-company-overview":
                score += 10
            if metadata.get("source_id") == "travelx-customer-service-policies":
                score += 5
            scored.append((score, document))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [document.model_copy(deep=True) for _, document in scored[:limit]]
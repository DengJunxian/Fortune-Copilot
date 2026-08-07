from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.core.privacy import scan_prompt_injection
from app.domain.enums import AuditEventType
from app.models.common import utc_now
from app.models.governance import AuditEvent, PolicyDocument
from app.models.trust import KnowledgeChunk
from app.schemas.trust import (
    ControlledKnowledgeDataset,
    KnowledgeCatalogDocument,
    KnowledgeCatalogResponse,
    KnowledgeCitation,
    KnowledgeClaim,
    KnowledgeMatch,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.security.model_risk import record_model_run

RETRIEVAL_VERSION = "hybrid-rag-v1.0.0"
VECTOR_DIMENSIONS = 64
MINIMUM_MATCH_SCORE = 0.16


@dataclass(frozen=True)
class KnowledgeSeedResult:
    dataset_version: str
    document_count: int
    chunk_count: int
    quarantined_chunk_count: int
    changed_document_count: int
    changed_chunk_count: int


def resolve_knowledge_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/knowledge/controlled_knowledge_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "knowledge_base_missing",
        "找不到受控知识库文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


def load_knowledge_dataset(configured_path: str) -> ControlledKnowledgeDataset:
    path = resolve_knowledge_path(configured_path)
    try:
        return ControlledKnowledgeDataset.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise AppError(
            "knowledge_base_invalid",
            "受控知识库未通过结构校验",
            status_code=500,
        ) from exc


def scan_untrusted_instructions(text: str) -> list[str]:
    return scan_prompt_injection(text)


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", "", text.casefold())


def deterministic_embedding(text: str) -> list[float]:
    normalized = _normalized_text(text)
    units: list[str] = []
    units.extend(re.findall(r"[a-z0-9_.%-]+", normalized))
    units.extend(normalized[index : index + 2] for index in range(max(0, len(normalized) - 1)))
    vector = [0.0] * VECTOR_DIMENSIONS
    for unit in units:
        digest = hashlib.sha256(unit.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % VECTOR_DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 8) for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True))))


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _canonical_document_content(document: Any) -> str:
    return "\n".join(chunk.content.strip() for chunk in document.chunks)


def ensure_knowledge_base(session: Session, configured_path: str) -> KnowledgeSeedResult:
    dataset = load_knowledge_dataset(configured_path)
    changed_documents = 0
    changed_chunks = 0
    quarantined = 0
    expected_chunk_codes: set[str] = set()

    for payload in dataset.documents:
        content = _canonical_document_content(payload)
        document_values: dict[str, Any] = {
            "code": payload.code,
            "title": payload.title,
            "issuing_authority": payload.issuing_authority,
            "category": payload.category,
            "document_version": payload.document_version,
            "publication_date": payload.publication_date,
            "effective_date": payload.effective_date,
            "expiry_date": payload.expiry_date,
            "source_uri": payload.source_uri,
            "source_type": payload.source_type,
            "applicable_audiences": payload.applicable_audiences,
            "applicable_regions": payload.applicable_regions,
            "content": content,
            "content_hash": _content_hash(content),
            "last_verified_date": payload.last_verified_date,
            "controlled_snapshot": payload.controlled_snapshot,
            "metadata_json": {
                **payload.metadata,
                "dataset_version": dataset.dataset_version,
                "dataset_updated_at": dataset.updated_at.isoformat(),
                "vectorizer_version": dataset.vectorizer_version,
            },
            "valuation_date": dataset.updated_at,
            "data_source": dataset.dataset_version,
            "is_user_confirmed": True,
            "is_deleted": False,
            "deleted_at": None,
        }
        document = session.scalar(select(PolicyDocument).where(PolicyDocument.code == payload.code))
        if document is None:
            document = PolicyDocument(**document_values)
            session.add(document)
            session.flush()
            changed_documents += 1
        else:
            changed = False
            for field, value in document_values.items():
                if getattr(document, field) != value:
                    setattr(document, field, value)
                    changed = True
            if changed:
                document.version += 1
                changed_documents += 1

        for chunk_payload in payload.chunks:
            expected_chunk_codes.add(chunk_payload.code)
            security_evidence = scan_untrusted_instructions(chunk_payload.content)
            security_status = "quarantined" if security_evidence else "clean"
            if security_status == "quarantined":
                quarantined += 1
            chunk_values: dict[str, Any] = {
                "document_id": document.id,
                "code": chunk_payload.code,
                "page_ref": chunk_payload.page_ref,
                "paragraph_ref": chunk_payload.paragraph_ref,
                "content": chunk_payload.content,
                "keywords": chunk_payload.keywords,
                "embedding": deterministic_embedding(chunk_payload.content),
                "token_count": len(_normalized_text(chunk_payload.content)),
                "content_hash": _content_hash(chunk_payload.content),
                "security_status": security_status,
                "security_evidence": security_evidence,
                "metadata_json": {
                    "dataset_version": dataset.dataset_version,
                    "vectorizer_version": dataset.vectorizer_version,
                },
                "valuation_date": dataset.updated_at,
                "data_source": dataset.dataset_version,
                "is_user_confirmed": True,
                "is_deleted": False,
                "deleted_at": None,
            }
            chunk = session.scalar(
                select(KnowledgeChunk).where(KnowledgeChunk.code == chunk_payload.code)
            )
            if chunk is None:
                session.add(KnowledgeChunk(**chunk_values))
                changed_chunks += 1
            else:
                changed = False
                for field, value in chunk_values.items():
                    if getattr(chunk, field) != value:
                        setattr(chunk, field, value)
                        changed = True
                if changed:
                    chunk.version += 1
                    changed_chunks += 1

    controlled_chunks = list(
        session.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.data_source == dataset.dataset_version,
                KnowledgeChunk.is_deleted.is_(False),
            )
        ).all()
    )
    for stale in controlled_chunks:
        if stale.code not in expected_chunk_codes:
            stale.is_deleted = True
            stale.deleted_at = utc_now()
            stale.version += 1
            changed_chunks += 1
    session.commit()
    return KnowledgeSeedResult(
        dataset_version=dataset.dataset_version,
        document_count=len(dataset.documents),
        chunk_count=sum(len(document.chunks) for document in dataset.documents),
        quarantined_chunk_count=quarantined,
        changed_document_count=changed_documents,
        changed_chunk_count=changed_chunks,
    )


def _document_status(document: PolicyDocument, as_of: date) -> str:
    if document.effective_date > as_of:
        return "not_yet_effective"
    if document.expiry_date is not None and document.expiry_date < as_of:
        return "expired"
    return "active"


def knowledge_catalog(
    session: Session, configured_path: str, *, as_of: date
) -> KnowledgeCatalogResponse:
    dataset = load_knowledge_dataset(configured_path)
    documents = list(
        session.scalars(
            select(PolicyDocument)
            .where(
                PolicyDocument.data_source == dataset.dataset_version,
                PolicyDocument.is_deleted.is_(False),
            )
            .order_by(PolicyDocument.category, PolicyDocument.publication_date.desc())
        ).all()
    )
    chunks = list(
        session.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.data_source == dataset.dataset_version,
                KnowledgeChunk.is_deleted.is_(False),
            )
        ).all()
    )
    chunk_count_by_document: dict[str, int] = {}
    for chunk in chunks:
        chunk_count_by_document[chunk.document_id] = (
            chunk_count_by_document.get(chunk.document_id, 0) + 1
        )
    output_documents = [
        KnowledgeCatalogDocument(
            code=document.code or document.id,
            title=document.title,
            issuing_authority=document.issuing_authority,
            category=document.category,
            document_version=document.document_version,
            publication_date=document.publication_date,
            effective_date=document.effective_date,
            expiry_date=document.expiry_date,
            applicable_audiences=document.applicable_audiences,
            applicable_regions=document.applicable_regions,
            source_type=document.source_type,
            source_uri=document.source_uri,
            last_verified_date=document.last_verified_date,
            content_hash=document.content_hash,
            chunk_count=chunk_count_by_document.get(document.id, 0),
            status=_document_status(document, as_of),
        )
        for document in documents
    ]
    return KnowledgeCatalogResponse(
        dataset_version=dataset.dataset_version,
        updated_at=dataset.updated_at,
        retrieval_version=RETRIEVAL_VERSION,
        vectorizer_version=dataset.vectorizer_version,
        source_summary=dataset.source_summary,
        document_count=len(documents),
        active_document_count=sum(item.status == "active" for item in output_documents),
        chunk_count=len(chunks),
        quarantined_chunk_count=sum(chunk.security_status == "quarantined" for chunk in chunks),
        categories=sorted({document.category for document in documents}),
        documents=output_documents,
    )


def _keyword_score(query: str, content: str, keywords: list[str]) -> float:
    normalized_query = _normalized_text(query)
    normalized_content = _normalized_text(content)
    keyword_hits = sum(_normalized_text(keyword) in normalized_query for keyword in keywords)
    query_terms = {
        item
        for item in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,8}", query.casefold())
        if len(item) >= 2
    }
    content_hits = sum(_normalized_text(term) in normalized_content for term in query_terms)
    configured = min(1.0, keyword_hits / max(1, min(3, len(keywords))))
    lexical = min(1.0, content_hits / max(1, min(4, len(query_terms))))
    return max(configured, lexical)


def _metadata_matches(request: KnowledgeSearchRequest, document: PolicyDocument) -> bool:
    if request.categories and document.category not in request.categories:
        return False
    if request.audiences and not set(request.audiences).intersection(document.applicable_audiences):
        return False
    return not request.regions or (
        "全国" in document.applicable_regions
        or bool(set(request.regions).intersection(document.applicable_regions))
    )


def _citation(document: PolicyDocument, chunk: KnowledgeChunk) -> KnowledgeCitation:
    return KnowledgeCitation(
        citation_id=f"cite:{chunk.code}",
        chunk_id=chunk.id,
        chunk_code=chunk.code,
        document_code=document.code or document.id,
        title=document.title,
        issuing_authority=document.issuing_authority,
        category=document.category,
        source_uri=document.source_uri,
        source_type=document.source_type,
        publication_date=document.publication_date,
        effective_date=document.effective_date,
        expiry_date=document.expiry_date,
        last_verified_date=document.last_verified_date,
        applicable_audiences=document.applicable_audiences,
        applicable_regions=document.applicable_regions,
        page_ref=chunk.page_ref,
        paragraph_ref=chunk.paragraph_ref,
        document_version=document.document_version,
        content_hash=document.content_hash,
    )


def search_knowledge(
    session: Session,
    configured_path: str,
    request: KnowledgeSearchRequest,
    *,
    actor: ActorContext | None = None,
) -> KnowledgeSearchResponse:
    query_injection_evidence = scan_untrusted_instructions(request.query)
    dataset = load_knowledge_dataset(configured_path)
    as_of = request.as_of_date or date.today()
    rows = session.execute(
        select(KnowledgeChunk, PolicyDocument)
        .join(PolicyDocument, KnowledgeChunk.document_id == PolicyDocument.id)
        .where(
            KnowledgeChunk.data_source == dataset.dataset_version,
            KnowledgeChunk.is_deleted.is_(False),
            PolicyDocument.is_deleted.is_(False),
        )
    ).all()
    query_embedding = deterministic_embedding(request.query)
    candidates: list[tuple[float, float, float, KnowledgeChunk, PolicyDocument]] = []
    expired = 0
    not_yet = 0
    quarantined = 0
    for chunk, document in rows:
        if not _metadata_matches(request, document):
            continue
        status = _document_status(document, as_of)
        if status == "expired":
            expired += 1
            continue
        if status == "not_yet_effective":
            not_yet += 1
            continue
        if chunk.security_status != "clean":
            quarantined += 1
            continue
        keyword = _keyword_score(request.query, chunk.content, chunk.keywords)
        vector = _cosine(query_embedding, [float(value) for value in chunk.embedding])
        metadata = 1.0 if request.categories or request.audiences or request.regions else 0.5
        combined = (0.55 * keyword) + (0.35 * vector) + (0.10 * metadata)
        if combined >= MINIMUM_MATCH_SCORE:
            candidates.append((combined, keyword, vector, chunk, document))
    candidates.sort(key=lambda item: (-item[0], item[4].publication_date, item[3].code))
    selected = candidates[: request.limit]
    citations = [_citation(document, chunk) for _, _, _, chunk, document in selected]
    matches = [
        KnowledgeMatch(
            chunk_id=chunk.id,
            chunk_code=chunk.code,
            excerpt=chunk.content,
            keyword_score=round(keyword, 6),
            vector_score=round(vector, 6),
            metadata_score=1 if request.categories or request.audiences or request.regions else 0.5,
            combined_score=round(combined, 6),
            citation_id=f"cite:{chunk.code}",
        )
        for combined, keyword, vector, chunk, _document in selected
    ]
    claims = [
        KnowledgeClaim(text=chunk.content, citation_ids=[f"cite:{chunk.code}"])
        for _, _, _, chunk, _document in selected[:3]
    ]
    insufficient = not selected
    answer = (
        "受控知识库没有找到满足生效日期、适用范围和安全检查的依据。"
        "请补充问题或转人工核对，系统不会用模型常识补写政策。"
        if insufficient
        else "；".join(claim.text.rstrip("。") for claim in claims) + "。"
    )
    if actor is not None:
        record_model_run(
            session,
            household_id=None,
            actor=actor,
            provider="offline_hybrid_retrieval",
            model_name=RETRIEVAL_VERSION,
            task="rag",
            prompt_version=RETRIEVAL_VERSION,
            inputs={
                "intent": "controlled_policy_search",
                "citation_ids": [chunk.id for _, _, _, chunk, _ in selected],
                "risk_flags": query_injection_evidence,
            },
            output={
                "match_count": len(selected),
                "insufficient_information": insufficient,
                "quarantined_count": quarantined,
            },
            started_at=utc_now(),
            degraded=bool(query_injection_evidence) or insufficient,
            prompt_injection_detected=bool(query_injection_evidence),
            human_review_required=bool(query_injection_evidence) or insufficient,
            fallback_reason=(
                "prompt_injection_or_no_controlled_result"
                if query_injection_evidence or insufficient
                else None
            ),
        )
        event = AuditEvent(
            household_id=None,
            event_type=(
                AuditEventType.HALLUCINATION_BLOCKED
                if query_injection_evidence
                else AuditEventType.KNOWLEDGE_RETRIEVED
            ),
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="KnowledgeSearch",
            entity_id=None,
            event_version=1,
            summary=f"受控知识检索命中 {len(selected)} 个切片",
            evidence={
                "query_hash": hashlib.sha256(request.query.encode("utf-8")).hexdigest(),
                "as_of_date": as_of.isoformat(),
                "chunk_ids": [chunk.id for _, _, _, chunk, _ in selected],
                "insufficient_information": insufficient,
                "retrieval_version": RETRIEVAL_VERSION,
                "prompt_injection_evidence": query_injection_evidence,
            },
            occurred_at=utc_now(),
            valuation_date=as_of,
            data_source="deterministic_hybrid_retrieval",
            is_user_confirmed=True,
        )
        session.add(event)
        session.commit()
    return KnowledgeSearchResponse(
        query=request.query,
        as_of_date=as_of,
        answer=answer,
        claims=claims,
        matches=matches,
        citations=citations,
        insufficient_information=insufficient,
        filtered_expired_count=expired,
        filtered_not_yet_effective_count=not_yet,
        filtered_quarantined_count=quarantined,
        retrieval_version=RETRIEVAL_VERSION,
        vectorizer_version=dataset.vectorizer_version,
        limitations=[
            "比赛版仅检索受控本地快照；办理前需复核来源页是否更新。",
            "检索与解释不替代税务、社保、法律或产品销售人员的人工核验。",
            "任何金额、比率和配置仍必须来自确定性工具或用户确认事实。",
        ],
    )

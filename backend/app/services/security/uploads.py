from __future__ import annotations

import hashlib
import json
from pathlib import PurePath

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.core.privacy import scan_prompt_injection, stable_hash
from app.domain.enums import AuditEventType
from app.models.common import utc_now
from app.models.governance import AuditEvent
from app.schemas.security import FileInspectionResponse

ALLOWED_UPLOADS = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".json": {"application/json", "text/json", "text/plain"},
}


async def inspect_uploaded_document(
    session: Session,
    upload: UploadFile,
    actor: ActorContext,
    *,
    max_bytes: int,
) -> FileInspectionResponse:
    original_name = upload.filename or "unnamed"
    suffix = PurePath(original_name).suffix.casefold()
    media_type = (upload.content_type or "application/octet-stream").casefold()
    if suffix not in ALLOWED_UPLOADS or media_type not in ALLOWED_UPLOADS[suffix]:
        raise AppError(
            "upload_type_not_allowed",
            "只允许 UTF-8 TXT、Markdown 或 JSON 文档",
            status_code=415,
            details={"allowed_extensions": sorted(ALLOWED_UPLOADS)},
        )
    chunks: list[bytes] = []
    total = 0
    digest = hashlib.sha256()
    while True:
        chunk = await upload.read(65_536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppError(
                "upload_too_large",
                "上传文档超过允许大小",
                status_code=413,
                details={"max_bytes": max_bytes},
            )
        chunks.append(chunk)
        digest.update(chunk)
    payload = b"".join(chunks)
    if b"\x00" in payload:
        raise AppError("upload_binary_content", "文档包含二进制内容", status_code=415)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError("upload_encoding_invalid", "文档必须使用 UTF-8", status_code=415) from exc
    if suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise AppError("upload_json_invalid", "JSON 文档结构无效", status_code=422) from exc
    evidence = scan_prompt_injection(text)
    status = "quarantined" if evidence else "clean"
    now = utc_now()
    event = AuditEvent(
        household_id=None,
        event_type=AuditEventType.FILE_INSPECTION_RECORDED,
        actor_id=stable_hash(actor.actor_id)[:16],
        actor_role=actor.role,
        entity_type="EphemeralDocumentInspection",
        entity_id=None,
        event_version=1,
        summary=f"临时文档安全检查：{status}",
        evidence={
            "filename_hash": stable_hash(original_name),
            "media_type": media_type,
            "bytes": total,
            "sha256": digest.hexdigest(),
            "status": status,
            "injection_evidence": evidence,
            "document_persisted": False,
        },
        occurred_at=now,
        data_source="ephemeral_upload_inspector",
        is_user_confirmed=True,
    )
    session.add(event)
    session.flush()
    event.entity_id = event.id
    session.commit()
    return FileInspectionResponse(
        filename_hash=stable_hash(original_name),
        media_type=media_type,
        bytes_read=total,
        sha256=digest.hexdigest(),
        status=status,
        injection_evidence=evidence,
        boundary_note=("比赛版只在内存中检查允许类型，发现提示注入即隔离；原始文件不会持久化。"),
    )

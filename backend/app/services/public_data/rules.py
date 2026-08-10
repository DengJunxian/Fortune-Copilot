from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.core.errors import AppError
from app.services.public_data.models import (
    AuthoritativePublicDataSnapshot,
    PublicDataSnapshotResponse,
)

OFFICIAL_SOURCE_HOSTS = {
    "www.stats.gov.cn",
    "www.pbc.gov.cn",
    "www.nfra.gov.cn",
    "www.gov.cn",
    "www.icbc.com.cn",
    "gw.open.icbc.com.cn",
    "open.icbc.com.cn",
    "zfgb.hangzhou.gov.cn",
    "www.jiangsu.gov.cn",
    "jshrss.jiangsu.gov.cn",
    "www.gz.gov.cn",
    "cms.gz.gov.cn",
    "tjj.hangzhou.gov.cn",
    "tjj.nanjing.gov.cn",
    "tjj.gz.gov.cn",
}


def resolve_public_data_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4]
            / "data/public/authoritative_public_snapshot_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "public_data_snapshot_missing",
        "找不到权威公共数据快照",
        status_code=500,
        details={"configured_path": configured_path},
    )


def _all_source_references(snapshot: AuthoritativePublicDataSnapshot) -> list[str]:
    references = [
        str(snapshot.official_cpi.source_reference),
        str(snapshot.living_cost_observation.source_reference),
    ]
    references.extend(
        str(item.source_reference)
        for item in snapshot.regional_living_cost_observations.values()
    )
    for series in snapshot.regional_minimum_wages.values():
        references.append(str(series.source_reference))
        references.extend(str(point.source_reference) for point in series.values)
    references.extend(str(item.source_reference) for item in snapshot.policy_sources)
    references.extend(
        str(item.source_reference) for item in snapshot.integration_access_boundaries
    )
    return references


def _validate_official_hosts(snapshot: AuthoritativePublicDataSnapshot) -> None:
    rejected: list[str] = []
    for reference in _all_source_references(snapshot):
        parsed = urlsplit(reference)
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_SOURCE_HOSTS:
            rejected.append(reference)
    if rejected:
        raise AppError(
            "public_data_source_not_allowlisted",
            "公共数据快照包含未纳入治理白名单的来源",
            status_code=500,
            details={"rejected_hosts": sorted({urlsplit(item).hostname for item in rejected})},
        )


@lru_cache(maxsize=8)
def load_public_data_snapshot(configured_path: str) -> AuthoritativePublicDataSnapshot:
    path = resolve_public_data_path(configured_path)
    try:
        snapshot = AuthoritativePublicDataSnapshot.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise AppError(
            "public_data_snapshot_invalid",
            "权威公共数据快照未通过结构校验",
            status_code=500,
        ) from exc
    _validate_official_hosts(snapshot)
    return snapshot


def public_data_integrity_hash(snapshot: AuthoritativePublicDataSnapshot) -> str:
    canonical = json.dumps(
        snapshot.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_public_data_response(configured_path: str) -> PublicDataSnapshotResponse:
    snapshot = load_public_data_snapshot(configured_path)
    return PublicDataSnapshotResponse(
        snapshot=snapshot,
        integrity_hash=public_data_integrity_hash(snapshot),
        boundary_note=(
            "该接口返回截至 publication_cutoff 经人工复核的政府/银行公开网页快照；"
            "不是实时政府 API，也不包含工行客户、产品、交易或内部投研数据。"
        ),
    )

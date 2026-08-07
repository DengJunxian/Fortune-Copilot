from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.errors import AppError

ALLOWED_ENVIRONMENTS = {"development", "demo", "test"}
REQUIRED_TABLES = {"alembic_version", "households", "demo_runs", "experiment_suite_runs"}


@dataclass(frozen=True)
class DemoBackupResult:
    action: str
    database: str
    artifact: str
    recovery_artifact: str | None
    sha256: str
    bytes: int
    household_codes: list[str]
    synthetic_only: bool
    created_at: str


def _require_demo_environment(settings: Settings) -> None:
    if settings.app_env.casefold() not in ALLOWED_ENVIRONMENTS:
        raise AppError(
            "demo_backup_forbidden",
            "备份与恢复命令仅允许在隔离的 development、demo 或 test 环境运行",
            status_code=403,
        )


def _sqlite_path(settings: Settings) -> Path:
    _require_demo_environment(settings)
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise AppError(
            "demo_backup_sqlite_only",
            "内置备份工具仅处理文件型 SQLite；PostgreSQL 请按部署文档使用 pg_dump/pg_restore",
            status_code=409,
        )
    raw = Path(url.database)
    return (Path.cwd() / raw).resolve() if not raw.is_absolute() else raw.resolve()


def _inspect_database(path: Path) -> list[str]:
    if not path.is_file():
        raise AppError("demo_database_missing", f"数据库不存在：{path}", status_code=404)
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise AppError(
                    "demo_database_corrupt", "SQLite 完整性检查未通过", status_code=409
                )
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            missing = sorted(REQUIRED_TABLES - tables)
            if missing:
                raise AppError(
                    "demo_backup_schema_mismatch",
                    "备份缺少发布版必需数据表",
                    status_code=409,
                    details={"missing_tables": missing},
                )
            real_count = connection.execute(
                "SELECT COUNT(*) FROM households WHERE is_synthetic = 0 AND is_deleted = 0"
            ).fetchone()[0]
            if real_count:
                raise AppError(
                    "demo_backup_contains_non_synthetic",
                    "检测到非合成家庭，拒绝使用演示备份／恢复通道",
                    status_code=409,
                )
            rows = connection.execute(
                "SELECT code FROM households "
                "WHERE is_synthetic = 1 AND is_deleted = 0 ORDER BY code"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise AppError(
            "demo_database_invalid",
            "文件不是可验证的 Fortune Copilot SQLite 数据库",
            status_code=409,
        ) from exc
    codes = [str(row[0]) for row in rows]
    if codes != ["DEMO_A", "DEMO_B", "DEMO_C"]:
        raise AppError(
            "demo_backup_family_set_invalid",
            "备份必须且只能包含当前三套活动合成家庭",
            status_code=409,
            details={"household_codes": codes},
        )
    return codes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(path: Path, result: DemoBackupResult) -> None:
    manifest_path = Path(f"{path}.manifest.json")
    manifest_path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def backup_demo_database(
    settings: Settings, output: Path, *, overwrite: bool = False
) -> DemoBackupResult:
    source_path = _sqlite_path(settings)
    household_codes = _inspect_database(source_path)
    destination = output.expanduser().resolve()
    if destination == source_path:
        raise AppError("demo_backup_same_path", "备份路径不能与当前数据库相同", status_code=409)
    if destination.exists() and not overwrite:
        raise AppError(
            "demo_backup_exists", "备份文件已存在；如需覆盖请显式传入 --overwrite", status_code=409
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with sqlite3.connect(source_path) as source, sqlite3.connect(temporary_path) as target:
            source.backup(target)
        _inspect_database(temporary_path)
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    result = DemoBackupResult(
        action="backup",
        database=str(source_path),
        artifact=str(destination),
        recovery_artifact=None,
        sha256=_sha256(destination),
        bytes=destination.stat().st_size,
        household_codes=household_codes,
        synthetic_only=True,
        created_at=datetime.now(UTC).isoformat(),
    )
    _write_manifest(destination, result)
    return result


def restore_demo_database(
    settings: Settings, backup: Path, *, confirmation: str
) -> DemoBackupResult:
    if confirmation != "restore_synthetic_demo":
        raise AppError(
            "demo_restore_confirmation_required",
            "恢复前必须显式传入 --confirm restore_synthetic_demo",
            status_code=409,
        )
    target_path = _sqlite_path(settings)
    backup_path = backup.expanduser().resolve()
    if backup_path == target_path:
        raise AppError("demo_restore_same_path", "恢复文件不能是当前数据库本身", status_code=409)
    household_codes = _inspect_database(backup_path)
    _inspect_database(target_path)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    recovery_path = target_path.with_name(f"{target_path.name}.pre-restore-{timestamp}.sqlite")
    shutil.copy2(target_path, recovery_path)
    temporary_path = target_path.with_name(f".{target_path.name}.restore-{timestamp}.tmp")
    try:
        shutil.copy2(backup_path, temporary_path)
        _inspect_database(temporary_path)
        os.replace(temporary_path, target_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    result = DemoBackupResult(
        action="restore",
        database=str(target_path),
        artifact=str(backup_path),
        recovery_artifact=str(recovery_path),
        sha256=_sha256(target_path),
        bytes=target_path.stat().st_size,
        household_codes=household_codes,
        synthetic_only=True,
        created_at=datetime.now(UTC).isoformat(),
    )
    return result

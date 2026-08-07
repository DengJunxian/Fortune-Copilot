from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Header, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import AppError

ActorRole = Literal["client", "advisor", "compliance", "admin"]
AuthSource = Literal["signed_session", "demo_headers"]
ALLOWED_ROLES: set[ActorRole] = {"client", "advisor", "compliance", "admin"}
SESSION_AUDIENCE = "wealthtwin-api"
SESSION_ISSUER = "wealthtwin-session-v1"
DEMO_SIGNING_KEY = "wealthtwin-demo-only-signing-key-not-for-production"

# ``risk`` was the pre-stage-10 demo header value. Keep it as an input-only
# alias so recorded demo traffic remains replayable. Signed sessions never use it.
ROLE_ALIASES: dict[str, ActorRole] = {
    "client": "client",
    "advisor": "advisor",
    "risk": "compliance",
    "compliance": "compliance",
    "admin": "admin",
}


class ActorContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str
    role: ActorRole
    household_ids: tuple[str, ...] = ()
    issued_at: datetime
    expires_at: datetime
    auth_source: AuthSource

    @property
    def is_demo(self) -> bool:
        return self.auth_source == "demo_headers"

    def can_access_household(self, household_id: str) -> bool:
        return (
            self.role == "admin" or "*" in self.household_ids or household_id in self.household_ids
        )


class SessionClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sub: str = Field(min_length=1, max_length=80)
    role: ActorRole
    household_ids: list[str] = Field(default_factory=list, max_length=100)
    iat: int
    exp: int
    iss: Literal["wealthtwin-session-v1"] = "wealthtwin-session-v1"
    aud: Literal["wealthtwin-api"] = "wealthtwin-api"
    nonce: str = Field(min_length=16, max_length=80)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _signing_key(settings: Settings) -> bytes:
    if settings.session_signing_key is not None:
        return settings.session_signing_key.get_secret_value().encode("utf-8")
    if settings.is_production:
        raise AppError("security_configuration_error", "生产会话密钥未配置", status_code=503)
    return DEMO_SIGNING_KEY.encode("utf-8")


def create_session_token(
    actor_id: str,
    role: ActorRole,
    household_ids: Sequence[str],
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    nonce: str | None = None,
) -> str:
    """Create a short-lived, HMAC-authenticated application session envelope.

    This is not a login flow. Production deployments must issue it only after an
    external identity provider has authenticated the subject and resolved grants.
    """

    active = settings or get_settings()
    issued = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    claims = SessionClaims(
        sub=actor_id,
        role=role,
        household_ids=sorted(set(household_ids)),
        iat=int(issued.timestamp()),
        exp=int((issued + timedelta(minutes=active.session_timeout_minutes)).timestamp()),
        nonce=nonce or secrets.token_urlsafe(24),
    )
    payload = _b64url_encode(
        json.dumps(
            claims.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signature = _b64url_encode(
        hmac.new(_signing_key(active), payload.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{payload}.{signature}"


def verify_session_token(
    token: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> ActorContext:
    active = settings or get_settings()
    try:
        payload, signature = token.split(".", 1)
        expected = _b64url_encode(
            hmac.new(_signing_key(active), payload.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature mismatch")
        claims = SessionClaims.model_validate_json(_b64url_decode(payload))
    except (
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise AppError("invalid_session", "会话无效，请重新登录", status_code=401) from exc

    current = (now or datetime.now(UTC)).astimezone(UTC)
    issued = datetime.fromtimestamp(claims.iat, tz=UTC)
    expires = datetime.fromtimestamp(claims.exp, tz=UTC)
    maximum_expiry = issued + timedelta(minutes=active.session_timeout_minutes)
    if issued > current + timedelta(seconds=60) or expires > maximum_expiry:
        raise AppError("invalid_session", "会话时间范围无效", status_code=401)
    if current >= expires:
        raise AppError("session_expired", "会话已超时，请重新登录", status_code=401)
    return ActorContext(
        actor_id=claims.sub,
        role=claims.role,
        household_ids=tuple(claims.household_ids),
        issued_at=issued,
        expires_at=expires,
        auth_source="signed_session",
    )


def require_household_access(actor: ActorContext, household_id: str) -> None:
    if actor.can_access_household(household_id):
        return
    # Deliberately use 404 to avoid confirming that another household exists.
    raise AppError("resource_not_found", "资源不存在或无权访问", status_code=404)


def require_actor(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
    actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
) -> ActorContext:
    settings = get_settings()
    actor: ActorContext
    if authorization is not None:
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.casefold() != "bearer" or not token.strip():
            raise AppError("invalid_session", "Authorization 必须使用 Bearer 会话", status_code=401)
        actor = verify_session_token(token.strip(), settings=settings)
    elif settings.allow_demo_actor_headers:
        raw_actor_id = (actor_id or "local-demo").strip()
        normalized_role = (actor_role or "client").casefold()
        canonical_role = ROLE_ALIASES.get(normalized_role)
        if canonical_role is None:
            raise AppError(
                "forbidden_role",
                "当前角色无权访问该资源",
                status_code=403,
                details={"allowed_roles": sorted(ALLOWED_ROLES)},
            )
        if not raw_actor_id or len(raw_actor_id) > 80:
            raise AppError("invalid_actor", "调用方标识无效", status_code=400)
        now = datetime.now(UTC)
        actor = ActorContext(
            actor_id=raw_actor_id,
            role=canonical_role,
            # Legacy headers are isolated to test/demo and synthetic data. They
            # never establish production grants.
            household_ids=("*",),
            issued_at=now,
            expires_at=now + timedelta(minutes=settings.session_timeout_minutes),
            auth_source="demo_headers",
        )
    else:
        raise AppError("authentication_required", "需要有效会话", status_code=401)

    household_id = request.path_params.get("household_id")
    if household_id is not None:
        require_household_access(actor, str(household_id))
    request.state.actor = actor
    return actor


def require_roles(actor: ActorContext, allowed_roles: Iterable[ActorRole]) -> None:
    """Enforce endpoint-level least privilege with a stable 403 envelope."""

    allowed = set(allowed_roles)
    if actor.role not in allowed:
        raise AppError(
            "permission_denied",
            "当前账号没有执行此操作的最小权限",
            status_code=403,
            details={
                "current_role": actor.role,
                "required_roles": sorted(allowed),
            },
        )


def require_sensitive_confirmation(request: Request, expected_action: str) -> None:
    confirmation = request.headers.get("X-Confirm-Action", "")
    if not hmac.compare_digest(confirmation, expected_action):
        raise AppError(
            "sensitive_confirmation_required",
            "该敏感操作需要再次明确确认",
            status_code=409,
            details={"required_confirmation": expected_action},
        )

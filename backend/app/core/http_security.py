from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import defaultdict, deque
from collections.abc import MutableMapping
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings

UNSAFE_METHODS: Final = {"POST", "PUT", "PATCH", "DELETE"}
EXPENSIVE_PATH_MARKERS: Final = (
    "/twin/",
    "/trust-orchestrations",
    "/reports",
    "/evaluations/run",
    "/planning/runs",
    "/portfolio/runs",
    "/demo/",
)


def _json_error(status: int, code: str, message: str) -> bytes:
    return json.dumps(
        {"error": {"code": code, "message": message, "request_id": "middleware", "details": None}},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


async def _send_error(send: Send, status: int, code: str, message: str) -> None:
    body = _json_error(status, code, message)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RequestBodyLimitMiddleware:
    """Reject oversized bodies before Pydantic, multipart, or business logic runs."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > self.max_bytes:
                    await _send_error(send, 413, "request_too_large", "请求体超过允许大小")
                    return
            except ValueError:
                await _send_error(send, 400, "invalid_content_length", "Content-Length 无效")
                return

        consumed = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_bytes:
                    raise _RequestTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestTooLarge:
            if not response_started:
                await _send_error(send, 413, "request_too_large", "请求体超过允许大小")


class _RequestTooLarge(Exception):
    pass


class RateLimitMiddleware:
    """Competition-safe in-process limiter; production must also enforce at the edge."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.default_limit = settings.rate_limit_per_minute
        self.expensive_limit = settings.expensive_rate_limit_per_minute
        self._events: MutableMapping[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _client_key(scope: Scope, headers: dict[bytes, bytes]) -> str:
        authorization = headers.get(b"authorization")
        if authorization:
            return hashlib.sha256(authorization).hexdigest()[:24]
        actor = headers.get(b"x-actor-id")
        if actor:
            return hashlib.sha256(actor).hexdigest()[:24]
        client = scope.get("client")
        return str(client[0]) if client else "unknown"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if path.endswith("/health") or path.endswith("/meta/capabilities"):
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "GET")).upper()
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        expensive = method in UNSAFE_METHODS and any(
            marker in path for marker in EXPENSIVE_PATH_MARKERS
        )
        limit = self.expensive_limit if expensive else self.default_limit
        bucket = f"{self._client_key(scope, headers)}:{method}:{path}"
        current = time.monotonic()
        with self._lock:
            events = self._events[bucket]
            while events and events[0] <= current - 60:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(60 - (current - events[0])))
                allowed = False
                remaining = 0
            else:
                events.append(current)
                allowed = True
                remaining = max(0, limit - len(events))
                retry_after = 0
        if not allowed:
            body = _json_error(429, "rate_limit_exceeded", "请求过于频繁，请稍后重试")
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json; charset=utf-8"),
                        (b"content-length", str(len(body)).encode("ascii")),
                        (b"retry-after", str(retry_after).encode("ascii")),
                        (b"x-ratelimit-limit", str(limit).encode("ascii")),
                        (b"x-ratelimit-remaining", b"0"),
                        (b"cache-control", b"no-store"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def rate_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                mutable_headers = list(message.get("headers", []))
                mutable_headers.extend(
                    [
                        (b"x-ratelimit-limit", str(limit).encode("ascii")),
                        (b"x-ratelimit-remaining", str(remaining).encode("ascii")),
                    ]
                )
                message = {**message, "headers": mutable_headers}
            await send(message)

        await self.app(scope, receive, rate_send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.production = settings.is_production
        self.allowed_origins = set(settings.cors_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", ""))
        origin_raw = headers.get(b"origin")
        origin = origin_raw.decode("latin-1") if origin_raw else None
        if method in UNSAFE_METHODS and origin is not None and origin not in self.allowed_origins:
            await _send_error(send, 403, "origin_not_allowed", "请求来源未获授权")
            return

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (b"cache-control", b"no-store"),
                    ]
                )
                if self.production or not path.startswith(("/docs", "/redoc")):
                    response_headers.append(
                        (
                            b"content-security-policy",
                            b"default-src 'none'; frame-ancestors 'none'; "
                            b"base-uri 'none'; form-action 'self'",
                        )
                    )
                if self.production:
                    response_headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message = {**message, "headers": response_headers}
            await send(message)

        await self.app(scope, receive, secure_send)

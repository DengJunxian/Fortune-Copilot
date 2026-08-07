#!/usr/bin/env python3
"""Warm the local Fortune Copilot Demo without contacting external services."""

from __future__ import annotations

import argparse
import ipaddress
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def local_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise argparse.ArgumentTypeError("必须提供有效的 HTTP(S) 地址")
    host = parsed.hostname.casefold()
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise argparse.ArgumentTypeError("预热脚本只允许访问本机回环地址")
        except ValueError as exc:
            raise argparse.ArgumentTypeError("预热脚本只允许访问 localhost 或回环 IP") from exc
    return value.rstrip("/") + "/"


def request_json(base_url: str, path: str, *, method: str = "GET") -> Any:
    request = Request(
        urljoin(base_url, path.lstrip("/")),
        data=b"{}" if method == "POST" else None,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Actor-ID": "demo-warmup",
            "X-Actor-Role": "admin",
        },
    )
    try:
        with urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SystemExit(f"Demo 预热失败：{exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", type=local_base_url, default="http://127.0.0.1:8000")
    args = parser.parse_args()
    health = request_json(args.api_url, "/api/v1/health")
    if health.get("status") != "ok":
        raise SystemExit(f"数据库未就绪：{health}")
    loaded = request_json(args.api_url, "/api/v1/demo/load", method="POST")
    preheated = request_json(args.api_url, "/api/v1/demo/preheat", method="POST")
    comparison = request_json(args.api_url, "/api/v1/demo/families/comparison")
    if comparison.get("unique_configuration_count") != 3:
        raise SystemExit("三家庭预热结果不是三个唯一配置")
    print(
        json.dumps(
            {
                "status": "ready",
                "dataset_version": loaded.get("dataset_version"),
                "warmed_components": preheated.get("warmed_components"),
                "external_network_calls": preheated.get("external_network_calls"),
                "unique_family_configurations": comparison.get("unique_configuration_count"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check technical release metadata and public entry links without app dependencies."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    expected = (ROOT / "VERSION").read_text().strip()
    versions: dict[str, str] = {}
    for name in ("package.json", "frontend/package.json"):
        versions[name] = json.loads((ROOT / name).read_text())["version"]
    for name in ("package-lock.json", "frontend/package-lock.json"):
        lock = json.loads((ROOT / name).read_text())
        versions[name] = lock["version"]
        for key in ("", "frontend"):
            if key in lock["packages"]:
                versions[f"{name}:{key or 'root'}"] = lock["packages"][key]["version"]
    project = tomllib.loads((ROOT / "backend/pyproject.toml").read_text())
    versions["backend/pyproject.toml"] = project["project"]["version"]
    module = ast.parse((ROOT / "backend/app/__init__.py").read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            versions["backend/app/__init__.py"] = ast.literal_eval(node.value)
    patterns = {
        ".env.example": r"^APP_VERSION=(\S+)",
        "docker-compose.yml": r"APP_VERSION:\s*(\S+)",
        "render.yaml": r"key: APP_VERSION\s+value:\s*(\S+)",
        "frontend/src/api/capabilities.ts": r'version:\s*"([^"]+)"',
    }
    errors = []
    for name, pattern in patterns.items():
        match = re.search(pattern, (ROOT / name).read_text(), re.MULTILINE)
        if match:
            versions[name] = match[1]
        else:
            errors.append(f"{name}: release version missing")
    if "backend/app/__init__.py" not in versions:
        errors.append("backend/app/__init__.py: __version__ missing")
    for name, actual in versions.items():
        if actual != expected:
            errors.append(f"{name}: version {actual}, expected {expected}")

    files = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    ).decode().split("\0")
    published = {(ROOT / name).resolve() for name in files if name}
    link_count = 0
    for name in ("README.md", "docs/README.md", "docs/deployment.md"):
        source = ROOT / name
        body = re.sub(r"```.*?```", "", source.read_text(), flags=re.DOTALL)
        for target in re.findall(r"\[[^\]\n]+\]\(([^)\s]+)\)", body):
            url = urlsplit(target.strip("<>"))
            if url.scheme or url.netloc or not url.path:
                continue
            path = (source.parent / unquote(url.path)).resolve()
            link_count += 1
            if path not in published and not (
                path.is_dir() and any(path in item.parents for item in published)
            ):
                errors.append(f"{name}: link is missing or ignored: {target}")
    for error in errors:
        print(f"FAIL {error}")
    if errors:
        return 1
    print(f"OK release {expected}: {len(versions)} version markers, {link_count} local links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

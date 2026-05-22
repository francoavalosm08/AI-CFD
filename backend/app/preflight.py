from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.errors import FoamAgentError


@dataclass
class PreflightCheck:
    name: str
    ok: bool
    detail: str


@dataclass
class RealModePreflightResult:
    ok: bool
    checks: list[PreflightCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def run_real_mode_preflight(
    *,
    mcp_url: str,
    openai_api_key: str | None = None,
    app_runs_root: Path,
    timeout_seconds: float = 10,
) -> RealModePreflightResult:
    checks: list[PreflightCheck] = []
    errors: list[str] = []

    api_key = (openai_api_key if openai_api_key is not None else os.environ.get("OPENAI_API_KEY", "")).strip()
    if api_key:
        checks.append(PreflightCheck(name="openai_api_key", ok=True, detail="OPENAI_API_KEY is set"))
    else:
        message = "OPENAI_API_KEY is missing or empty"
        checks.append(PreflightCheck(name="openai_api_key", ok=False, detail=message))
        errors.append(message)

    try:
        app_runs_root.mkdir(parents=True, exist_ok=True)
        checks.append(
            PreflightCheck(
                name="shared_runs_directory",
                ok=True,
                detail=f"Shared Foam-Agent runs directory is available at {app_runs_root}",
            )
        )
    except OSError as exc:
        message = f"Shared Foam-Agent runs directory is not usable at {app_runs_root}: {exc}"
        checks.append(PreflightCheck(name="shared_runs_directory", ok=False, detail=message))
        errors.append(message)

    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                mcp_url,
                json=payload,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code >= 400:
            excerpt = response.text[:240].strip()
            message = f"Foam-Agent MCP endpoint {mcp_url} returned HTTP {response.status_code}: {excerpt}"
            checks.append(PreflightCheck(name="mcp_endpoint", ok=False, detail=message))
            errors.append(message)
        else:
            checks.append(
                PreflightCheck(
                    name="mcp_endpoint",
                    ok=True,
                    detail=f"Foam-Agent MCP endpoint responded at {mcp_url}",
                )
            )
    except Exception as exc:
        message = f"Foam-Agent MCP endpoint is unreachable at {mcp_url}: {exc}"
        checks.append(PreflightCheck(name="mcp_endpoint", ok=False, detail=message))
        errors.append(message)

    return RealModePreflightResult(ok=not errors, checks=checks, errors=errors)


def raise_if_preflight_failed(result: RealModePreflightResult) -> None:
    if result.ok:
        return
    raise FoamAgentError("; ".join(result.errors))

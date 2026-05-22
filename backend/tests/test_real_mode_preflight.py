from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.preflight import run_real_mode_preflight


@pytest.mark.asyncio
async def test_missing_openai_api_key_fails_preflight(tmp_path: Path) -> None:
    result = await run_real_mode_preflight(
        mcp_url="http://127.0.0.1:7860/mcp",
        openai_api_key="",
        app_runs_root=tmp_path / "foamagent-runs",
    )

    assert result.ok is False
    assert any("OPENAI_API_KEY" in error for error in result.errors)


@pytest.mark.asyncio
async def test_unreachable_mcp_endpoint_fails_preflight(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    ):
        result = await run_real_mode_preflight(
            mcp_url="http://127.0.0.1:7860/mcp",
            app_runs_root=tmp_path / "foamagent-runs",
        )

    assert result.ok is False
    assert any("http://127.0.0.1:7860/mcp" in error for error in result.errors)


@pytest.mark.asyncio
async def test_missing_shared_directory_is_reported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app_runs = tmp_path / "foamagent-runs"

    response = httpx.Response(
        200,
        text='{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}',
        request=httpx.Request("POST", "http://127.0.0.1:7860/mcp"),
    )

    with (
        patch.object(Path, "mkdir", side_effect=OSError("permission denied")),
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)),
    ):
        result = await run_real_mode_preflight(
            mcp_url="http://127.0.0.1:7860/mcp",
            app_runs_root=app_runs,
        )

    assert result.ok is False
    assert any(str(app_runs) in error for error in result.errors)

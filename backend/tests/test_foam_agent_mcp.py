from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.errors import FoamAgentError
from app.foam_agent import FoamAgentMcpClient


def _response(
    *,
    status_code: int = 200,
    text: str,
    content_type: str = "application/json",
) -> httpx.Response:
    return httpx.Response(
        status_code,
        text=text,
        headers={"content-type": content_type},
        request=httpx.Request("POST", "http://127.0.0.1:7860/mcp"),
    )


def test_decode_response_parses_json_rpc_success() -> None:
    client = FoamAgentMcpClient(url="http://127.0.0.1:7860/mcp")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"structuredContent": {"case_name": "wing_case"}},
    }
    decoded = client._decode_response(_response(text=json.dumps(payload)))
    assert decoded["result"]["structuredContent"]["case_name"] == "wing_case"


def test_decode_response_parses_sse_payload() -> None:
    client = FoamAgentMcpClient(url="http://127.0.0.1:7860/mcp")
    payload = {"jsonrpc": "2.0", "id": 2, "result": {"structuredContent": {"status": "ok"}}}
    sse = f"event: message\ndata: {json.dumps(payload)}\n\n"
    decoded = client._decode_response(
        _response(text=sse, content_type="text/event-stream")
    )
    assert decoded["result"]["structuredContent"]["status"] == "ok"


@pytest.mark.asyncio
async def test_call_tool_http_error_includes_tool_status_and_excerpt() -> None:
    client = FoamAgentMcpClient(url="http://127.0.0.1:7860/mcp")
    response = _response(status_code=500, text="internal solver failure " * 20)

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        with pytest.raises(FoamAgentError) as exc_info:
            await client._call_tool("plan", {"request": {"user_requirement": "test"}})

    message = str(exc_info.value)
    assert "plan" in message
    assert "HTTP 500" in message
    assert "internal solver failure" in message


@pytest.mark.asyncio
async def test_call_tool_json_rpc_error_includes_message() -> None:
    client = FoamAgentMcpClient(url="http://127.0.0.1:7860/mcp")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32601, "message": "Unknown tool"},
    }
    response = _response(text=json.dumps(payload))

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        with pytest.raises(FoamAgentError) as exc_info:
            await client._call_tool("input_writer", {"request": {}})

    message = str(exc_info.value)
    assert "input_writer" in message
    assert "Unknown tool" in message


class StubMcpClient(FoamAgentMcpClient):
    def __init__(self, *, responses: list[dict], app_runs_root: Path) -> None:
        super().__init__(
            url="http://127.0.0.1:7860/mcp",
            app_runs_root=app_runs_root,
        )
        self._responses = list(responses)

    async def preflight(self, emit) -> None:
        await emit("real_preflight", "skipped in stub")

    async def _call_tool(self, name: str, arguments: dict) -> dict:
        if not self._responses:
            raise AssertionError(f"Unexpected tool call: {name}")
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_run_external_aero_writes_provenance_files(tmp_path: Path) -> None:
    app_runs = tmp_path / "foamagent-runs"
    case_dir = app_runs / "case-1"
    case_dir.mkdir(parents=True)
    (case_dir / "solver.log").write_text("solver ok\n")

    client = StubMcpClient(
        app_runs_root=app_runs,
        responses=[
            {
                "case_name": "case-1",
                "subtasks": [],
                "case_solver": "simpleFoam",
                "case_domain": "external",
                "case_category": "aero",
            },
            {"case_dir": "/home/openfoam/Foam-Agent/runs/case-1"},
            {"status": "completed"},
            {"artifacts": [str(case_dir / "pressure.png")]},
            {"artifacts": [str(case_dir / "velocity.png")]},
        ],
    )
    (case_dir / "pressure.png").write_bytes(b"png")
    (case_dir / "velocity.png").write_bytes(b"png2")

    output_dir = tmp_path / "runs" / "run-1"
    events: list[tuple[str, str]] = []

    async def emit(status: str, message: str) -> None:
        events.append((status, message))

    await client.run_external_aero(
        prompt="steady external aero",
        mesh_path="/workspace/data/uploads/wing.msh",
        output_dir=str(output_dir),
        emit=emit,
    )

    assert (output_dir / "foamagent-plan.json").exists()
    assert (output_dir / "foamagent-input-writer.json").exists()
    assert (output_dir / "foamagent-run.json").exists()
    assert (output_dir / "foamagent-visualization-pressure.json").exists()
    assert (output_dir / "foamagent-visualization-velocity.json").exists()
    assert not (output_dir / "foamagent-review.json").exists()


@pytest.mark.asyncio
async def test_run_external_aero_writes_review_provenance_only_on_failure(tmp_path: Path) -> None:
    app_runs = tmp_path / "foamagent-runs"
    case_dir = app_runs / "case-2"
    case_dir.mkdir(parents=True)

    client = StubMcpClient(
        app_runs_root=app_runs,
        responses=[
            {
                "case_name": "case-2",
                "subtasks": [],
                "case_solver": "simpleFoam",
                "case_domain": "external",
                "case_category": "aero",
            },
            {"case_dir": "/home/openfoam/Foam-Agent/runs/case-2"},
            {"status": "failed", "errors": ["bad mesh"]},
            {"analysis": "increase inlet patch area"},
            {"status": "ok"},
            {"status": "completed"},
            {"artifacts": []},
            {"artifacts": []},
        ],
    )

    output_dir = tmp_path / "runs" / "run-2"

    async def emit(_status: str, _message: str) -> None:
        return None

    await client.run_external_aero(
        prompt="steady external aero",
        mesh_path=None,
        output_dir=str(output_dir),
        emit=emit,
    )

    assert (output_dir / "foamagent-review.json").exists()
    assert (output_dir / "foamagent-run-rerun.json").exists()

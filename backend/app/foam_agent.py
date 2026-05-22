from __future__ import annotations

import json
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from app.errors import FoamAgentError
from app.jobs import FoamAgentRunner
from app.preflight import raise_if_preflight_failed, run_real_mode_preflight


class FakeFoamAgentRunner(FoamAgentRunner):
    async def run_external_aero(
        self,
        *,
        prompt: str,
        mesh_path: str | None,
        output_dir: str,
        emit: Callable[[str, str], Awaitable[None]],
    ) -> dict:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        await emit("planning", "Fake Foam-Agent planned a steady RANS external-aero case")
        await emit("running", "Fake OpenFOAM solver completed")
        (output / "solver.log").write_text("Fake solver log\nFinal residual Ux: 1e-5\n")
        (output / "residuals.csv").write_text("iteration,Ux,p\n1,0.1,0.2\n25,0.00001,0.00002\n")
        (output / "pressure.png").write_bytes(_tiny_png())
        await emit("visualizing", "Fake PyVista visualization generated")
        return {
            "mode": "fake",
            "mesh_path": mesh_path,
            "prompt_excerpt": prompt[:240],
        }


class FoamAgentMcpClient(FoamAgentRunner):
    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: int = 3600,
        run_timeout_seconds: int | None = None,
        agent_runs_root: str = "/home/openfoam/Foam-Agent/runs",
        app_runs_root: Path | None = None,
        openai_api_key: str | None = None,
        preflight_timeout_seconds: float = 10,
    ) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.run_timeout_seconds = run_timeout_seconds or timeout_seconds
        self._request_id = 0
        self.agent_runs_root = agent_runs_root.rstrip("/")
        self.app_runs_root = app_runs_root
        self.openai_api_key = openai_api_key
        self.preflight_timeout_seconds = preflight_timeout_seconds

    async def preflight(self, emit: Callable[[str, str], Awaitable[None]]) -> None:
        if not self.app_runs_root:
            raise FoamAgentError("FOAM_AGENT_APP_RUNS_ROOT is not configured for MCP mode")
        result = await run_real_mode_preflight(
            mcp_url=self.url,
            openai_api_key=self.openai_api_key,
            app_runs_root=self.app_runs_root,
            timeout_seconds=self.preflight_timeout_seconds,
        )
        raise_if_preflight_failed(result)
        await emit("real_preflight", "Real-mode preflight checks passed")

    async def run_external_aero(
        self,
        *,
        prompt: str,
        mesh_path: str | None,
        output_dir: str,
        emit: Callable[[str, str], Awaitable[None]],
    ) -> dict:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        await emit("planning", "Calling Foam-Agent plan tool")
        plan = await self._call_tool("plan", {"request": {"user_requirement": prompt}})
        self._write_provenance(output, "foamagent-plan.json", plan)

        await emit("meshing", "Calling Foam-Agent input writer")
        generated = await self._call_tool(
            "input_writer",
            {
                "request": {
                    "case_name": plan["case_name"],
                    "subtasks": plan["subtasks"],
                    "user_requirement": prompt,
                    "case_solver": plan["case_solver"],
                    "case_domain": plan["case_domain"],
                    "case_category": plan["case_category"],
                }
            },
        )
        self._write_provenance(output, "foamagent-input-writer.json", generated)
        case_dir = generated["case_dir"]

        await emit("running", f"Running OpenFOAM case at {case_dir}")
        run_result = await self._call_tool(
            "run",
            {"request": {"case_dir": case_dir, "timeout": self.run_timeout_seconds}},
        )
        self._write_provenance(output, "foamagent-run.json", run_result)

        review_written = False
        if run_result.get("status") == "failed":
            await emit("reviewing", "Reviewing Foam-Agent run errors")
            review = await self._call_tool(
                "review",
                {
                    "request": {
                        "case_dir": case_dir,
                        "errors": run_result.get("errors", []),
                        "user_requirement": prompt,
                    }
                },
            )
            self._write_provenance(output, "foamagent-review.json", review)
            review_written = True
            await self._call_tool(
                "apply_fixes",
                {
                    "request": {
                        "case_dir": case_dir,
                        "error_logs": run_result.get("errors", []),
                        "review_analysis": review["analysis"],
                        "user_requirement": prompt,
                    }
                },
            )
            await emit("running", "Re-running case after Foam-Agent fixes")
            run_result = await self._call_tool(
                "run",
                {"request": {"case_dir": case_dir, "timeout": self.run_timeout_seconds}},
            )
            self._write_provenance(output, "foamagent-run-rerun.json", run_result)

        await emit("visualizing", "Generating pressure and velocity visualizations")
        pressure = await self._call_tool(
            "visualization",
            {"request": {"case_dir": case_dir, "quantity": "pressure", "visualization_type": "pyvista"}},
        )
        self._write_provenance(output, "foamagent-visualization-pressure.json", pressure)
        velocity = await self._call_tool(
            "visualization",
            {"request": {"case_dir": case_dir, "quantity": "velocity", "visualization_type": "pyvista"}},
        )
        self._write_provenance(output, "foamagent-visualization-velocity.json", velocity)
        mirrored = self._mirror_case_artifacts(
            case_dir=case_dir,
            output_dir=output,
            explicit_paths=pressure.get("artifacts", []) + velocity.get("artifacts", []),
        )
        return {
            "mode": "mcp",
            "case_dir": case_dir,
            "mesh_path": mesh_path,
            "run": run_result,
            "review_written": review_written,
            "visualizations": pressure.get("artifacts", []) + velocity.get("artifacts", []),
            "mirrored_artifacts": [str(path) for path in mirrored],
        }

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code >= 400:
            excerpt = response.text[:240].strip()
            raise FoamAgentError(
                f"Foam-Agent tool '{name}' failed with HTTP {response.status_code}: {excerpt}"
            )
        decoded = self._decode_response(response)
        if "error" in decoded:
            error = decoded["error"]
            message = error.get("message", error) if isinstance(error, dict) else str(error)
            raise FoamAgentError(f"Foam-Agent tool '{name}' returned MCP error: {message}")
        return self._extract_tool_payload(decoded.get("result", {}))

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _decode_response(self, response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        text = response.text.strip()
        if "text/event-stream" in content_type or text.startswith("data:"):
            for line in text.splitlines():
                if line.startswith("data:"):
                    payload = line.removeprefix("data:").strip()
                    if payload:
                        return json.loads(payload)
        return response.json()

    def _extract_tool_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        if "structuredContent" in result and isinstance(result["structuredContent"], dict):
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list) and content:
            text = content[0].get("text") if isinstance(content[0], dict) else None
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"text": text}
        if isinstance(result, dict):
            return result
        return {"result": result}

    def _write_provenance(self, output_dir: Path, filename: str, payload: dict[str, Any]) -> Path:
        path = output_dir / filename
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _mirror_case_artifacts(
        self, *, case_dir: str, output_dir: Path, explicit_paths: list[str]
    ) -> list[Path]:
        if not self.app_runs_root:
            return []
        app_case_dir = self._map_agent_path(case_dir)
        if not app_case_dir or not app_case_dir.exists():
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        candidates = set()
        for item in explicit_paths:
            mapped = self._map_agent_path(item)
            if mapped and mapped.exists() and mapped.is_file():
                candidates.add(mapped)
        for extension in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.csv", "*.log", "*.out", "*.err", "*.vtk", "*.foam"):
            candidates.update(app_case_dir.rglob(extension))

        mirrored: list[Path] = []
        for source in sorted(candidates):
            destination = output_dir / source.name
            if destination.resolve() == source.resolve():
                continue
            shutil.copy2(source, destination)
            mirrored.append(destination)

        archive_path = output_dir / "openfoam-case.zip"
        if not archive_path.exists():
            shutil.make_archive(str(archive_path.with_suffix("")), "zip", app_case_dir)
            mirrored.append(archive_path)
        return mirrored

    def _map_agent_path(self, path: str) -> Path | None:
        normalized = path.replace("\\", "/")
        if not normalized.startswith(self.agent_runs_root):
            return None
        if not self.app_runs_root:
            return None
        relative = normalized.removeprefix(self.agent_runs_root).lstrip("/")
        return self.app_runs_root / Path(*relative.split("/")) if relative else self.app_runs_root


def _tiny_png() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
        "0000000c49444154789c63606060000000040001f61738550000000049454e44ae426082"
    )

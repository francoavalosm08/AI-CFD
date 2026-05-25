import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "../src/App";
import type { RunRecord } from "../src/types";

describe("App", () => {
  it("renders the upload-first CFD workbench", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI CFD Workbench" })).toBeInTheDocument();
    expect(screen.getByText("Drop STEP, STL, Gmsh mesh, or OpenFOAM ZIP")).toBeInTheDocument();
    expect(screen.getByText(/STEP\/STL import is best-effort/i)).toBeInTheDocument();
    expect(screen.getByText(/airfoil, inlet, outlet, farfield, frontAndBack, and internal/i)).toBeInTheDocument();
    expect(screen.getByText(/obstacle, inlet, outlet, farfield, frontAndBack, and internal/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Velocity/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Start CFD run/i })).toBeDisabled();
    expect(screen.getByText(/Runner:/i)).toBeInTheDocument();
  });

  it("renders real-run summary metrics from run metadata", async () => {
    const run: RunRecord = {
      id: "run-123456",
      upload_id: "upload-1",
      status: "completed",
      spec: {
        upload_id: "upload-1",
        units: "m",
        length_scale: 1,
        velocity: 25,
        mach: null,
        angle_of_attack: 2,
        fluid_preset: "air_15c",
        turbulence_preset: "steady_rans_sst",
        mesh_quality: "balanced",
        requested_outputs: ["residuals", "pressure", "velocity", "forces"],
        max_runtime_minutes: 60
      },
      created_at: "2026-05-22T00:00:00Z",
      updated_at: "2026-05-22T00:00:00Z",
      completed_at: "2026-05-22T00:00:00Z",
      summary: {
        check_mesh_summary: { passed: true, cells: 57292 },
        manifest: { reynolds_number: 1666666.666667 },
        final_coefficients: { Cl: 0.45, Cd: 0.032, Cm: -0.014 }
      },
      artifacts: []
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/health") {
          return Response.json({ status: "ok", runner_mode: "local_openfoam" });
        }
        if (url === "/api/runs/run-123456") {
          return Response.json(run);
        }
        if (url === "/api/runs/run-123456/artifacts") {
          return Response.json({ artifacts: [] });
        }
        return Response.json({}, { status: 404 });
      })
    );

    render(<App initialRunId="run-123456" />);

    expect(await screen.findByText("57,292")).toBeInTheDocument();
    expect(screen.getByText("1.667e+6")).toBeInTheDocument();
    expect(screen.getByText("0.45")).toBeInTheDocument();
    expect(screen.getByText("0.032")).toBeInTheDocument();
    expect(screen.getByText("-0.014")).toBeInTheDocument();
    expect(screen.getByText("Pass")).toBeInTheDocument();

    vi.unstubAllGlobals();
  });

  it("renders simple obstacle case metadata from run summary", async () => {
    const run: RunRecord = {
      ...completedRun(),
      id: "run-obstacle",
      summary: {
        check_mesh_summary: { passed: true, cells: 4456 },
        manifest: { case_type: "external_2d_obstacle", reynolds_number: 1000000 },
        force_coefficients: { enabled: true, patches: ["obstacle"] },
        final_coefficients: { Cl: 2.78, Cd: 3.49, Cm: -0.697 }
      }
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/health") {
          return Response.json({ status: "ok", runner_mode: "local_openfoam" });
        }
        if (url === "/api/runs/run-obstacle") {
          return Response.json(run);
        }
        if (url === "/api/runs/run-obstacle/artifacts") {
          return Response.json({ artifacts: [] });
        }
        return Response.json({}, { status: 404 });
      })
    );

    render(<App initialRunId="run-obstacle" />);

    expect(await screen.findByText("External obstacle")).toBeInTheDocument();
    expect(screen.getByText("obstacle")).toBeInTheDocument();

    vi.unstubAllGlobals();
  });

  it("renders geometry readiness, repair mode, mesh quality, and report link", async () => {
    const run: RunRecord = {
      ...completedRun(),
      id: "run-quality",
      summary: {
        geometry_readiness: {
          status: "repaired_ready",
          repair_mode: "meshfix",
          meshfix_attempted: true,
          passed: true
        },
        mesh_quality: {
          cells: 45000,
          max_non_orthogonality: 29.1,
          max_skewness: 0.35,
          max_aspect_ratio: 1.2
        },
        check_mesh_summary: { passed: true, cells: 45000 },
        manifest: { case_type: "external_3d_stl_snappy", reynolds_number: 1000000 }
      }
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/health") {
          return Response.json({ status: "ok", runner_mode: "local_openfoam" });
        }
        if (url === "/api/runs/run-quality") {
          return Response.json(run);
        }
        if (url === "/api/runs/run-quality/artifacts") {
          return Response.json({
            artifacts: [
              {
                id: "artifact-report",
                run_id: "run-quality",
                type: "other",
                path: "openfoam-report.html",
                display_name: "openfoam-report.html",
                mime_type: "text/html",
                created_at: "2026-05-22T00:00:00Z"
              }
            ]
          });
        }
        return Response.json({}, { status: 404 });
      })
    );

    render(<App initialRunId="run-quality" />);

    expect(await screen.findByText("Repaired ready")).toBeInTheDocument();
    expect(screen.getByText("meshfix")).toBeInTheDocument();
    expect(screen.getByText("29.1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open full report/i })).toHaveAttribute("href", "/api/artifacts/artifact-report");

    vi.unstubAllGlobals();
  });

  it("opens solver image artifacts in a larger preview dialog", async () => {
    const run = completedRun();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/health") {
          return Response.json({ status: "ok", runner_mode: "local_openfoam" });
        }
        if (url === "/api/runs/run-visuals") {
          return Response.json(run);
        }
        if (url === "/api/runs/run-visuals/artifacts") {
          return Response.json({
            artifacts: [
              {
                id: "artifact-pressure",
                run_id: "run-visuals",
                type: "image",
                path: "pressure.png",
                display_name: "pressure.png",
                mime_type: "image/png",
                created_at: "2026-05-22T00:00:00Z"
              },
              {
                id: "artifact-log",
                run_id: "run-visuals",
                type: "log",
                path: "solver.log",
                display_name: "solver.log",
                mime_type: "text/plain",
                created_at: "2026-05-22T00:00:00Z"
              }
            ]
          });
        }
        return Response.json({}, { status: 404 });
      })
    );

    render(<App initialRunId="run-visuals" />);

    fireEvent.click(await screen.findByRole("button", { name: "Inspect pressure.png" }));

    expect(screen.getByRole("dialog", { name: "pressure.png preview" })).toBeInTheDocument();
    expect(screen.getByAltText("pressure.png enlarged preview")).toHaveAttribute("src", "/api/artifacts/artifact-pressure");
    expect(screen.getByRole("link", { name: /Open image/i })).toHaveAttribute("href", "/api/artifacts/artifact-pressure");

    fireEvent.click(screen.getByRole("button", { name: "Close visual preview" }));

    expect(screen.queryByRole("dialog", { name: "pressure.png preview" })).not.toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});


function completedRun(): RunRecord {
  return {
    id: "run-visuals",
    upload_id: "upload-1",
    status: "completed",
    spec: {
      upload_id: "upload-1",
      units: "m",
      length_scale: 1,
      velocity: 25,
      mach: null,
      angle_of_attack: 2,
      fluid_preset: "air_15c",
      turbulence_preset: "steady_rans_sst",
      mesh_quality: "balanced",
      requested_outputs: ["residuals", "pressure", "velocity", "forces"],
      max_runtime_minutes: 60
    },
    created_at: "2026-05-22T00:00:00Z",
    updated_at: "2026-05-22T00:00:00Z",
    completed_at: "2026-05-22T00:00:00Z",
    summary: {},
    artifacts: []
  };
}

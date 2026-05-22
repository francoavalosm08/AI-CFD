import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "../src/App";
import type { RunRecord } from "../src/types";

describe("App", () => {
  it("renders the upload-first CFD workbench", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI CFD Workbench" })).toBeInTheDocument();
    expect(screen.getByText("Drop STEP, STL, Gmsh mesh, or OpenFOAM ZIP")).toBeInTheDocument();
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
});

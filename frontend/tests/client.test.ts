import { describe, expect, it } from "vitest";

import { artifactUrl, defaultSpec, formatRunnerMode, formatStatus } from "../src/client";

describe("client helpers", () => {
  it("builds artifact URLs from artifact ids", () => {
    expect(artifactUrl("artifact-1")).toBe("/api/artifacts/artifact-1");
  });

  it("creates external-aero defaults for an uploaded file", () => {
    const spec = defaultSpec("upload-1");

    expect(spec).toMatchObject({
      upload_id: "upload-1",
      units: "m",
      length_scale: 1,
      velocity: 25,
      angle_of_attack: 0,
      fluid_preset: "air_15c",
      turbulence_preset: "steady_rans_sst",
      mesh_quality: "balanced",
      requested_outputs: ["residuals", "pressure", "velocity", "forces"],
      max_runtime_minutes: 60
    });
  });

  it("formats run statuses for display", () => {
    expect(formatStatus("queued")).toBe("Queued");
    expect(formatStatus("visualizing")).toBe("Visualizing");
  });

  it("formats runner modes for display", () => {
    expect(formatRunnerMode("fake")).toBe("Fake");
    expect(formatRunnerMode("local_openfoam")).toBe("Local OpenFOAM");
    expect(formatRunnerMode("mcp")).toBe("Foam-Agent MCP");
  });
});

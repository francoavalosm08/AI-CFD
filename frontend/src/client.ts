import type { Artifact, HealthResponse, RunRecord, RunStatus, SimulationSpec, UploadRecord } from "./types";

export function artifactUrl(artifactId: string): string {
  return `/api/artifacts/${artifactId}`;
}

export function defaultSpec(uploadId: string): SimulationSpec {
  return {
    upload_id: uploadId,
    units: "m",
    length_scale: 1,
    velocity: 25,
    mach: null,
    angle_of_attack: 0,
    fluid_preset: "air_15c",
    turbulence_preset: "steady_rans_sst",
    mesh_quality: "balanced",
    requested_outputs: ["residuals", "pressure", "velocity", "forces"],
    max_runtime_minutes: 60
  };
}

export function formatStatus(status: RunStatus): string {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatRunnerMode(mode: string | null | undefined): string {
  if (!mode) return "Checking";
  if (mode === "fake") return "Fake";
  if (mode === "local_openfoam") return "Local OpenFOAM";
  if (mode === "mcp") return "Foam-Agent MCP";
  return mode
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch("/api/health");
  return parseJsonResponse(response);
}

export async function uploadGeometry(file: File): Promise<UploadRecord> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/uploads", { method: "POST", body: form });
  return parseJsonResponse(response);
}

export async function createRun(spec: SimulationSpec): Promise<RunRecord> {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec })
  });
  return parseJsonResponse(response);
}

export async function fetchRun(runId: string): Promise<RunRecord> {
  const response = await fetch(`/api/runs/${runId}`);
  return parseJsonResponse(response);
}

export async function fetchArtifacts(runId: string): Promise<Artifact[]> {
  const response = await fetch(`/api/runs/${runId}/artifacts`);
  const body = await parseJsonResponse<{ artifacts: Artifact[] }>(response);
  return body.artifacts;
}

export async function cancelRun(runId: string): Promise<RunRecord> {
  const response = await fetch(`/api/runs/${runId}/cancel`, { method: "POST" });
  return parseJsonResponse(response);
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : response.statusText;
    throw new Error(detail);
  }
  return body as T;
}

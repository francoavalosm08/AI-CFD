export type UploadKind = "gmsh_mesh" | "surface_mesh" | "cad" | "openfoam_case";

export type RunStatus =
  | "queued"
  | "preprocessing"
  | "planning"
  | "meshing"
  | "running"
  | "reviewing"
  | "visualizing"
  | "completed"
  | "failed"
  | "cancelled";

export type SimulationSpec = {
  upload_id: string;
  units: "m" | "cm" | "mm" | "in" | "ft";
  length_scale: number;
  velocity: number;
  mach?: number | null;
  angle_of_attack: number;
  fluid_preset: string;
  turbulence_preset: string;
  mesh_quality: "coarse" | "balanced" | "fine";
  requested_outputs: string[];
  max_runtime_minutes: number;
};

export type UploadRecord = {
  id: string;
  original_name: string;
  stored_path: string;
  kind: UploadKind;
  created_at: string;
};

export type GeometryPreflightArtifact = {
  display_name: string;
  type: Artifact["type"];
  path?: string;
};

export type GeometryPreflightResponse = {
  upload_id: string;
  status: string;
  passed: boolean;
  repair_mode?: string | null;
  meshfix_attempted?: boolean;
  recommendations: string[];
  artifacts: GeometryPreflightArtifact[];
  readiness?: Record<string, unknown>;
};

export type Artifact = {
  id: string;
  run_id: string;
  type: "image" | "log" | "plot_data" | "download" | "vtk" | "other";
  path: string;
  display_name: string;
  mime_type: string;
  created_at: string;
};

export type RunRecord = {
  id: string;
  upload_id: string;
  status: RunStatus;
  spec: SimulationSpec;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  prompt_used?: string | null;
  summary: Record<string, unknown>;
  artifacts: Artifact[];
};

export type HealthResponse = {
  status: "ok" | string;
  foam_agent_mode?: string;
  runner_mode?: string;
};

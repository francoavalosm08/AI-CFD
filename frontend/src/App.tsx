import { Activity, Box, FileUp, Gauge, Play, RotateCcw, Square, Wind } from "lucide-react";
import { ExternalLink, X, ZoomIn } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  artifactUrl,
  cancelRun,
  createRun,
  defaultSpec,
  fetchArtifacts,
  fetchHealth,
  fetchRun,
  formatRunnerMode,
  formatStatus,
  runGeometryPreflight,
  uploadGeometry
} from "./client";
import type { Artifact, GeometryPreflightResponse, HealthResponse, RunRecord, SimulationSpec, UploadRecord } from "./types";

type EventLine = {
  status: string;
  message: string;
};

const finalStatuses = new Set(["completed", "failed", "cancelled"]);

type AppProps = {
  initialRunId?: string;
};

type SummaryMetric = {
  label: string;
  value: string;
};

export default function App({ initialRunId }: AppProps = {}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [upload, setUpload] = useState<UploadRecord | null>(null);
  const [spec, setSpec] = useState<SimulationSpec | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [events, setEvents] = useState<EventLine[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [preflightBusy, setPreflightBusy] = useState(false);
  const [geometryPreflight, setGeometryPreflight] = useState<GeometryPreflightResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);

  const images = useMemo(() => artifacts.filter((artifact) => artifact.type === "image"), [artifacts]);
  const logs = useMemo(() => artifacts.filter((artifact) => artifact.type === "log"), [artifacts]);
  const reportArtifact = useMemo(
    () => artifacts.find((artifact) => artifact.display_name === "openfoam-report.html") ?? null,
    [artifacts]
  );
  const downloads = useMemo(
    () => artifacts.filter((artifact) => artifact.type === "download" || artifact.type === "plot_data" || artifact.type === "vtk"),
    [artifacts]
  );
  const runnerMode = health?.runner_mode ?? health?.foam_agent_mode;
  const selectedImage = useMemo(
    () => images.find((artifact) => artifact.id === selectedImageId) ?? null,
    [images, selectedImageId]
  );

  useEffect(() => {
    void fetchHealth()
      .then(setHealth)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!initialRunId) return;
    void refreshRun(initialRunId).catch((err) => {
      setError(err instanceof Error ? err.message : "Could not load the run");
    });
  }, [initialRunId]);

  useEffect(() => {
    if (selectedImageId && !selectedImage) {
      setSelectedImageId(null);
    }
  }, [selectedImage, selectedImageId]);

  const summaryMetrics = useMemo(() => buildSummaryMetrics(run), [run]);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    setRun(null);
    setArtifacts([]);
    setEvents([]);
    setGeometryPreflight(null);
    setPreflightBusy(false);
    try {
      const uploaded = await uploadGeometry(file);
      setUpload(uploaded);
      setSpec(defaultSpec(uploaded.id));
      if (uploaded.kind === "surface_mesh" || uploaded.kind === "cad") {
        setPreflightBusy(true);
        try {
          setGeometryPreflight(await runGeometryPreflight(uploaded.id));
        } catch (err) {
          setGeometryPreflight({
            upload_id: uploaded.id,
            status: "failed_geometry",
            passed: false,
            recommendations: [err instanceof Error ? err.message : "Geometry preflight failed."],
            artifacts: []
          });
        } finally {
          setPreflightBusy(false);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function patchSpec(patch: Partial<SimulationSpec>) {
    setSpec((current) => (current ? { ...current, ...patch } : current));
  }

  async function handleStart(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spec) return;
    setBusy(true);
    setError(null);
    setEvents([]);
    setArtifacts([]);
    try {
      const created = await createRun(spec);
      setRun(created);
      subscribeToRun(created.id);
      await refreshRun(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the run");
    } finally {
      setBusy(false);
    }
  }

  function subscribeToRun(runId: string) {
    const source = new EventSource(`/api/runs/${runId}/events`);
    source.addEventListener("status", (event) => {
      const [status, ...messageParts] = String(event.data).split("|");
      setEvents((current) => [...current, { status, message: messageParts.join("|") }]);
      void refreshRun(runId);
      if (finalStatuses.has(status)) {
        source.close();
      }
    });
    source.onerror = () => source.close();
  }

  async function refreshRun(runId: string) {
    const nextRun = await fetchRun(runId);
    setRun(nextRun);
    setArtifacts(await fetchArtifacts(runId));
  }

  async function handleCancel() {
    if (!run) return;
    setRun(await cancelRun(run.id));
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <h1>AI CFD Workbench</h1>
          <p>Local external-aerodynamics runs with fake, local OpenFOAM, or optional Foam-Agent MCP modes.</p>
        </div>
        <div className="topbar-actions">
          <div className="status-chip">
            <Activity size={18} />
            {run ? formatStatus(run.status) : "Ready"}
          </div>
          <div className="status-chip">Runner: {formatRunnerMode(runnerMode)}</div>
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="workspace">
        <div
          className="dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            const file = event.dataTransfer.files.item(0);
            if (file) void handleFile(file);
          }}
        >
          <div className="dropzone-icon">
            <FileUp size={28} />
          </div>
          <h2>Drop STEP, STL, Gmsh mesh, or OpenFOAM ZIP</h2>
          <p>Premeshed .msh is the supported V1 path. STEP/STL import is best-effort and requires clean geometry plus Gmsh.</p>
          <p className="mesh-copy">
            Airfoil meshes need physical names: airfoil, inlet, outlet, farfield, frontAndBack, and internal.
            Simple obstacle meshes can use: obstacle, inlet, outlet, farfield, frontAndBack, and internal.
          </p>
          <input
            ref={fileInput}
            type="file"
            accept=".msh,.stl,.step,.stp,.zip"
            hidden
            onChange={(event) => {
              const file = event.target.files?.item(0);
              if (file) void handleFile(file);
            }}
          />
          <button type="button" className="primary-action" onClick={() => fileInput.current?.click()} disabled={busy}>
            <FileUp size={18} />
            Select file
          </button>
          {upload && (
            <div className="upload-summary">
              <Box size={18} />
              <span>{upload.original_name}</span>
              <strong>{upload.kind.replace("_", " ")}</strong>
            </div>
          )}
          {preflightBusy && (
            <div className="preflight-card">
              <strong>Geometry readiness</strong>
              <span>Checking STL/STEP geometry before solver setup...</span>
            </div>
          )}
          {geometryPreflight && (
            <div className={`preflight-card ${geometryPreflight.passed ? "preflight-pass" : "preflight-fail"}`}>
              <strong>Geometry readiness</strong>
              <span>{formatReadiness(geometryPreflight.status)}</span>
              {geometryPreflight.repair_mode && <span>Repair mode: {formatToken(geometryPreflight.repair_mode)}</span>}
              {geometryPreflight.recommendations.length > 0 && (
                <ul className="recommendation-list">
                  {geometryPreflight.recommendations.map((recommendation) => (
                    <li key={recommendation}>{recommendation}</li>
                  ))}
                </ul>
              )}
              {geometryPreflight.artifacts.length > 0 && (
                <span className="preflight-artifacts">
                  Preflight artifacts: {geometryPreflight.artifacts.map((artifact) => artifact.display_name).join(", ")}
                </span>
              )}
            </div>
          )}
        </div>

        <form className="setup-panel" onSubmit={handleStart}>
          <div className="panel-heading">
            <Wind size={20} />
            <h2>External Aero Setup</h2>
          </div>

          <label>
            Velocity
            <div className="input-row">
              <input
                type="number"
                min="0.01"
                step="any"
                value={spec?.velocity ?? 25}
                onChange={(event) => patchSpec({ velocity: Number(event.target.value) })}
                disabled={!spec || busy}
              />
              <span>m/s</span>
            </div>
          </label>

          <label>
            Angle of attack
            <div className="input-row">
              <input
                type="number"
                step="0.1"
                value={spec?.angle_of_attack ?? 0}
                onChange={(event) => patchSpec({ angle_of_attack: Number(event.target.value) })}
                disabled={!spec || busy}
              />
              <span>deg</span>
            </div>
          </label>

          <label>
            Geometry units
            <select
              value={spec?.units ?? "m"}
              onChange={(event) => patchSpec({ units: event.target.value as SimulationSpec["units"] })}
              disabled={!spec || busy}
            >
              <option value="m">meters</option>
              <option value="cm">centimeters</option>
              <option value="mm">millimeters</option>
              <option value="in">inches</option>
              <option value="ft">feet</option>
            </select>
          </label>

          <label>
            Scale to meters
            <input
              type="number"
              min="0.000001"
              step="any"
              value={spec?.length_scale ?? 1}
              onChange={(event) => patchSpec({ length_scale: Number(event.target.value) })}
              disabled={!spec || busy}
            />
          </label>

          <label>
            Mesh quality
            <select
              value={spec?.mesh_quality ?? "balanced"}
              onChange={(event) => patchSpec({ mesh_quality: event.target.value as SimulationSpec["mesh_quality"] })}
              disabled={!spec || busy}
            >
              <option value="coarse">coarse</option>
              <option value="balanced">balanced</option>
              <option value="fine">fine</option>
            </select>
          </label>

          <label>
            Runtime limit
            <div className="input-row">
              <input
                type="number"
                min="1"
                max="1440"
                value={spec?.max_runtime_minutes ?? 60}
                onChange={(event) => patchSpec({ max_runtime_minutes: Number(event.target.value) })}
                disabled={!spec || busy}
              />
              <span>min</span>
            </div>
          </label>

          <button className="run-button" type="submit" disabled={!spec || busy || preflightBusy || geometryPreflight?.passed === false}>
            <Play size={18} />
            Start CFD run
          </button>
        </form>
      </section>

      <section className="results-band">
        <div className="run-summary">
          <div>
            <span>Run</span>
            <strong>{run ? run.id.slice(0, 8) : "Not started"}</strong>
          </div>
          <div>
            <span>Status</span>
            <strong>{run ? formatStatus(run.status) : "Ready"}</strong>
          </div>
          <div>
            <span>Artifacts</span>
            <strong>{artifacts.length}</strong>
          </div>
          <button type="button" onClick={() => run && void refreshRun(run.id)} disabled={!run}>
            <RotateCcw size={16} />
            Refresh
          </button>
          <button type="button" onClick={() => void handleCancel()} disabled={!run || finalStatuses.has(run.status)}>
            <Square size={16} />
            Cancel
          </button>
          {reportArtifact && (
            <a className="report-link" href={artifactUrl(reportArtifact.id)} target="_blank" rel="noreferrer">
              <ExternalLink size={16} />
              Open full report
            </a>
          )}
        </div>

        {run?.error && <div className="error-banner">{run.error}</div>}

        {summaryMetrics.length > 0 && (
          <div className="result-metrics">
            {summaryMetrics.map((metric) => (
              <div key={metric.label}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
              </div>
            ))}
          </div>
        )}

        <div className="results-grid">
          <div className="artifact-panel">
            <div className="panel-heading">
              <Gauge size={20} />
              <h2>Visualizations</h2>
            </div>
            <div className="image-grid">
              {images.length === 0 && <p className="muted">OpenFOAM-derived images will appear here after visualization.</p>}
              {images.map((artifact) => (
                <figure key={artifact.id}>
                  <img src={artifactUrl(artifact.id)} alt={artifact.display_name} />
                  <figcaption>
                    <span>{artifact.display_name}</span>
                    <button type="button" onClick={() => setSelectedImageId(artifact.id)} aria-label={`Inspect ${artifact.display_name}`}>
                      <ZoomIn size={15} />
                      Inspect
                    </button>
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>

          <div className="artifact-panel">
            <h2>Progress</h2>
            <ol className="event-list">
              {events.length === 0 && <li className="muted">No run events yet.</li>}
              {events.map((line, index) => (
                <li key={`${line.status}-${index}`}>
                  <strong>{formatStatus(line.status as never)}</strong>
                  <span>{line.message}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="artifact-panel">
            <h2>Files</h2>
            <ul className="file-list">
              {[...logs, ...downloads].length === 0 && <li className="muted">Logs and downloads will appear here.</li>}
              {[...logs, ...downloads].map((artifact) => (
                <li key={artifact.id}>
                  <a href={artifactUrl(artifact.id)} target="_blank" rel="noreferrer">
                    {artifact.display_name}
                  </a>
                  <span>{artifact.type}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {selectedImage && (
        <div className="image-modal" role="dialog" aria-modal="true" aria-label={`${selectedImage.display_name} preview`}>
          <div className="image-modal-header">
            <h2>{selectedImage.display_name}</h2>
            <div>
              <a href={artifactUrl(selectedImage.id)} target="_blank" rel="noreferrer">
                <ExternalLink size={16} />
                Open image
              </a>
              <button type="button" onClick={() => setSelectedImageId(null)} aria-label="Close visual preview">
                <X size={18} />
              </button>
            </div>
          </div>
          <div className="image-modal-body">
            <img src={artifactUrl(selectedImage.id)} alt={`${selectedImage.display_name} enlarged preview`} />
          </div>
        </div>
      )}
    </main>
  );
}


function buildSummaryMetrics(run: RunRecord | null): SummaryMetric[] {
  if (!run) return [];
  const summary = run.summary;
  const manifest = asRecord(summary.manifest);
  const checkMesh = asRecord(summary.check_mesh_summary);
  const geometryReadiness = asRecord(summary.geometry_readiness);
  const meshQuality = asRecord(summary.mesh_quality);
  const finalCoefficients = asRecord(summary.final_coefficients);
  const forceCoefficients = asRecord(summary.force_coefficients);
  const metrics: SummaryMetric[] = [];

  const caseType = asString(manifest.case_type);
  if (caseType) metrics.push({ label: "Case", value: formatCaseType(caseType) });

  const readinessStatus = asString(geometryReadiness.status);
  if (readinessStatus) metrics.push({ label: "Geometry readiness", value: formatReadiness(readinessStatus) });

  const repairMode = asString(geometryReadiness.repair_mode);
  if (repairMode) metrics.push({ label: "Repair mode", value: repairMode });

  const archiveMode = asString(summary.archive_mode);
  if (archiveMode) metrics.push({ label: "Archive", value: formatToken(archiveMode) });

  const snappyProfile = asString(summary.snappy_profile ?? geometryReadiness.snappy_profile);
  if (snappyProfile) metrics.push({ label: "snappyHexMesh", value: formatToken(snappyProfile) });

  const patches = forceCoefficients.patches;
  if (Array.isArray(patches) && typeof patches[0] === "string") {
    metrics.push({ label: "Force patch", value: patches[0] });
  }

  const cells = asNumber(checkMesh.cells);
  if (cells !== null) metrics.push({ label: "Cells", value: cells.toLocaleString() });

  const maxNonOrthogonality = asNumber(meshQuality.max_non_orthogonality ?? checkMesh.max_non_orthogonality);
  if (maxNonOrthogonality !== null) metrics.push({ label: "Max non-orthogonality", value: formatCoefficient(maxNonOrthogonality) });

  const maxSkewness = asNumber(meshQuality.max_skewness ?? checkMesh.max_skewness);
  if (maxSkewness !== null) metrics.push({ label: "Max skewness", value: formatCoefficient(maxSkewness) });

  const reynolds = asNumber(manifest.reynolds_number);
  if (reynolds !== null) metrics.push({ label: "Re", value: reynolds.toExponential(3) });

  if (typeof checkMesh.passed === "boolean") {
    metrics.push({ label: "checkMesh", value: checkMesh.passed ? "Pass" : "Fail" });
  }

  for (const key of ["Cl", "Cd", "Cm"]) {
    const value = asNumber(finalCoefficients[key]);
    if (value !== null) metrics.push({ label: key, value: formatCoefficient(value) });
  }

  return metrics;
}


function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}


function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}


function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}


function formatCaseType(value: string): string {
  if (value === "airfoil_2d") return "2D airfoil";
  if (value === "external_2d_obstacle") return "External obstacle";
  return value.replaceAll("_", " ");
}


function formatCoefficient(value: number): string {
  return Number(value.toPrecision(4)).toString();
}


function formatReadiness(value: string): string {
  const text = value.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}


function formatToken(value: string): string {
  return value.replaceAll("_", " ");
}



import { Activity, Box, FileUp, Gauge, Play, RotateCcw, Square, Wind } from "lucide-react";
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
  uploadGeometry
} from "./client";
import type { Artifact, HealthResponse, RunRecord, SimulationSpec, UploadRecord } from "./types";

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
  const [error, setError] = useState<string | null>(null);

  const images = useMemo(() => artifacts.filter((artifact) => artifact.type === "image"), [artifacts]);
  const logs = useMemo(() => artifacts.filter((artifact) => artifact.type === "log"), [artifacts]);
  const downloads = useMemo(
    () => artifacts.filter((artifact) => artifact.type === "download" || artifact.type === "plot_data" || artifact.type === "vtk"),
    [artifacts]
  );
  const runnerMode = health?.runner_mode ?? health?.foam_agent_mode;

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

  const summaryMetrics = useMemo(() => buildSummaryMetrics(run), [run]);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    setRun(null);
    setArtifacts([]);
    setEvents([]);
    try {
      const uploaded = await uploadGeometry(file);
      setUpload(uploaded);
      setSpec(defaultSpec(uploaded.id));
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
            Production Gmsh MSH files should define physical names: airfoil, inlet, outlet, farfield, frontAndBack, and internal.
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

          <button className="run-button" type="submit" disabled={!spec || busy}>
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
              {images.length === 0 && <p className="muted">PyVista images will appear here after visualization.</p>}
              {images.map((artifact) => (
                <figure key={artifact.id}>
                  <img src={artifactUrl(artifact.id)} alt={artifact.display_name} />
                  <figcaption>{artifact.display_name}</figcaption>
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
    </main>
  );
}


function buildSummaryMetrics(run: RunRecord | null): SummaryMetric[] {
  if (!run) return [];
  const summary = run.summary;
  const manifest = asRecord(summary.manifest);
  const checkMesh = asRecord(summary.check_mesh_summary);
  const finalCoefficients = asRecord(summary.final_coefficients);
  const metrics: SummaryMetric[] = [];

  const cells = asNumber(checkMesh.cells);
  if (cells !== null) metrics.push({ label: "Cells", value: cells.toLocaleString() });

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


function formatCoefficient(value: number): string {
  return Number(value.toPrecision(4)).toString();
}



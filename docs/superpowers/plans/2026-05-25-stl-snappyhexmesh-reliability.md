# STL SnappyHexMesh Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first reliable local STL path by generating deterministic OpenFOAM snappyHexMesh cases and checking the required tools/runtime.

**Architecture:** Keep `.msh` as the V1 production path. Route uploaded STL files in local OpenFOAM mode to a dedicated snappyHexMesh case builder instead of forcing weak Gmsh conversion. The first acceptance slice is external 3D obstacle meshing and solver scaffolding with clear artifacts and preflight checks.

**Tech Stack:** Python/FastAPI backend, OpenFOAM `surfaceCheck`, `blockMesh`, `surfaceFeatures`, `snappyHexMesh`, `checkMesh`, PowerShell scripts, WSL2.

---

### Task 1: Snappy Case Builder

**Files:**
- Create: `backend/app/openfoam/snappy.py`
- Test: `backend/tests/test_openfoam_snappy.py`

- [ ] Write tests proving an STL is copied into `constant/triSurface/obstacle.stl` and OpenFOAM dictionaries are generated.
- [ ] Implement deterministic external 3D obstacle snappy case files.
- [ ] Include a manifest with domain, commands, and limitations.

### Task 2: Wire STL Uploads In Local OpenFOAM Mode

**Files:**
- Modify: `backend/app/jobs.py`
- Modify: `backend/app/openfoam/runner.py`
- Test: `backend/tests/test_jobs.py`
- Test: `backend/tests/test_openfoam_runner.py`

- [ ] Add tests proving STL uploads reach the local runner raw instead of Gmsh conversion.
- [ ] Add tests proving STL dry-run returns snappy commands/artifacts.
- [ ] Keep `.msh`, STEP, fake mode, and MCP behavior unchanged.

### Task 3: Runtime/Script Coverage

**Files:**
- Modify: `scripts/dev-openfoam-wsl.ps1`
- Modify: `scripts/runtime-report.ps1`
- Create: `scripts/generate-snappy-stl-case.ps1`
- Test: `backend/tests/test_phase45_release_contract.py`

- [ ] Require/report `surfaceCheck`, `blockMesh`, `surfaceFeatures`, and `snappyHexMesh` for the STL path.
- [ ] Add a script to generate a local snappy case from STL for IDE/manual inspection.
- [ ] Document the STL route as a reliability upgrade, not a 100% guarantee.

### Task 4: Verification

- [ ] Run targeted red/green tests.
- [ ] Run `py -m pytest backend`.
- [ ] Run OpenFOAM WSL preflight.
- [ ] Report the updated reliability table with exact evidence.


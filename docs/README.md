# AI CFD Workbench Docs

Read these docs in this order when picking up the project.

1. `../AGENTS.md` - fresh LLM/coding-agent handoff, current state, next milestone, and verification rules.
2. `PROJECT_OVERVIEW_AND_RUNBOOK.md` - architecture, run commands, environment notes, and operating procedures.
3. `PHASES_SUMMARY.md` - compact phase-by-phase record of what has been done.
4. `EXTERNAL_AERO_V1_ROADMAP.md` - active roadmap from the current prototype to usable external-aero V1.
5. `PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md` - detailed Phase 3 plan, now focused on local OpenFOAM without runtime API keys.
6. `LOCAL_OPENFOAM_NO_API_RUNBOOK.md` - no-API local OpenFOAM workflow and troubleshooting.
7. `REAL_MODE_RUNBOOK.md` - optional Foam-Agent/MCP startup, health checks, and troubleshooting.
8. `PHASE_2_PLANNING_DRAFT.md` - earlier planning details and risk analysis.

## Current Product Direction

Keep V1 focused on external aerodynamics. The app already has upload, spec capture, fake-mode execution, local OpenFOAM dry-run/case generation, live run events, artifacts, dashboard viewing, WSL/OpenFOAM preflight, NACA 4412 validation, mesh physical-name validation, and OpenFOAM-derived force coefficient artifacts. The next milestone is finishing `.msh` production workflow hardening for user-provided aircraft/vehicle meshes. Foam-Agent/MCP remains optional.

## Verification Before Handoff

Use this command for the full local confidence check:

```powershell
.\scripts\release-check.ps1
```

For backend-only changes, this is the smaller check:

```powershell
.\scripts\local-verify.ps1 -Scope backend
```

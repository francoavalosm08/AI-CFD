# AI CFD Workbench Docs

Read these docs in this order when picking up the project.

1. `../AGENTS.md` - fresh LLM/coding-agent handoff, current state, next milestone, and verification rules.
2. `PROJECT_OVERVIEW_AND_RUNBOOK.md` - architecture, run commands, environment notes, and operating procedures.
3. `PHASES_SUMMARY.md` - compact phase-by-phase record of what has been done.
4. `PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md` - detailed next milestone plan for real Foam-Agent/OpenFOAM integration.
5. `PHASE_2_PLANNING_DRAFT.md` - earlier planning details and risk analysis.

## Current Product Direction

Keep V1 focused on external aerodynamics. The app already has upload, spec capture, fake-mode execution, live run events, artifacts, and dashboard viewing. The next milestone is real Foam-Agent/OpenFOAM execution through Docker while preserving fake mode for tests.

## Verification Before Handoff

Use this command for the full local confidence check:

```powershell
.\scripts\release-check.ps1
```

For backend-only changes, this is the smaller check:

```powershell
.\scripts\local-verify.ps1 -Scope backend
```
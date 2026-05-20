# Phase 2 Planning Draft: Solidify Local Workflow

## Objective

Turn the current Phase 1 setup into a reliable, repeatable developer workflow for multiple users, while keeping the non-Docker-first strategy.

## Proposed Scope

1. **Script hardening**
- Improve guardrails and failure hints in `scripts/*.ps1`.
- Add clearer exit codes and troubleshooting output for common failures (missing tools, port conflicts, backend not healthy).

2. **Verification hardening**
- Add one command path to verify local baseline quickly (backend tests + smoke flow prerequisites).
- Keep fake-mode flow deterministic and easy to rerun.

3. **Documentation hardening**
- Add a short "first day setup" section and "common errors" section.
- Add explicit split between:
  - fast local iteration (non-Docker),
  - later integration/repro checks (Docker).

4. **No contract breakage**
- Keep existing `/api/*` contracts unchanged in this phase.
- No Dockerfile/Compose behavior changes unless explicitly approved.

## Out of Scope (for this phase)

- Real Foam-Agent/OpenFOAM solver behavior changes.
- New CFD feature requests outside current V1 flow.
- Broad frontend redesign.

## Candidate Deliverables

- `scripts/local-verify.ps1` (single local verification entrypoint).
- `scripts/release-check.ps1` (single release-readiness command).
- README troubleshooting table for known setup failures.
- Optional small backend/frontend tests targeting local script assumptions.

## Acceptance Criteria (Draft)

- New contributor on Windows can follow docs and reach:
  - backend running in fake mode,
  - frontend running via Vite proxy,
  - smoke flow passing with sample mesh.
- Failures produce actionable messages (what failed + exact next command).
- Existing backend tests continue to pass.

## Decisions Locked (May 19, 2026)

1. **Sequence:** Start by solidifying Phase 1 before real MCP/OpenFOAM expansion.
2. **Verification entrypoint:** Add `scripts/local-verify.ps1`.
3. **Frontend tests:** Optional for now; priority is getting this machine running first.
4. **Platform:** Keep Phase 2 Windows-first (PowerShell). Defer bash parity.
5. **Docker:** Allow minimal Docker validation guidance while keeping non-Docker as primary.

## Immediate Next Implementation Items

1. Land script hardening + local verify workflow.
2. Add release-check command for backend + frontend + smoke.
3. Improve onboarding/troubleshooting docs for first-run success.
4. Re-run backend/frontend tests and fake-mode smoke verification after changes.

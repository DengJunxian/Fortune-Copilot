# Fortune Copilot V6 Changelog

## Phase 0 — Repository Audit

- Added `V6_AUDIT.md` with the V5 reuse boundary, V6 gaps, CI findings and expected file impact.
- Confirmed that CHFH, ELTC, GRB, CFS, product ontology, intake confirmation, financial twin, monitoring and decision evidence can be reused.
- Recorded the existing uncommitted Competition Edition work without overwriting it.

## Phase 1 — Engineering Baseline

- Stabilized the three frontend tests that failed in PR #1 by waiting for their final asynchronous UI states.
- Preserved all original product assertions; no test was deleted or weakened to a generic render check.
- Recorded local backend, frontend, lint, typecheck, build and Playwright results in `V6_AUDIT.md`.

## Phase 2 — Narrative & Information Architecture

- Reframed the homepage around “每个家庭都有自己的财富答案”, ELTC and the three household questions.
- Reorganized the Wealth Dashboard first screen around safety, goals, ELTC and Next Best Action using existing deterministic APIs.
- Rewrote the README opening for judges, mentors, financial practitioners and partners before engineering readers.
- Added the V6 product narrative and retained explicit synthetic, public snapshot, mock and non-live boundaries.

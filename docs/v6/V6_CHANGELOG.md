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

## Phase 3 — Core Wealth Experience

- Elevated the existing deterministic bridge to “长期可投资资本 ELTC” and added a capital-investment-eligibility view without creating a second calculator.
- Added simple, standard and professional ELTC explanations; every amount still comes from the eligible-capital response.
- Productized GRB as a four-layer Family Risk Profile: capacity, willingness, behavior constraint and final family risk budget.
- Made the one-way behavior guardrail explicit and added regression assertions that the final budget never exceeds capacity, willingness or behavior limits.
- Reordered the portfolio experience into ELTC, family risk budget, goal, asset direction and explanation before showing allocation detail.

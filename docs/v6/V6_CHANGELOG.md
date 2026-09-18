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

## Phase 4 — Product Intelligence

- Added a deterministic Product Candidate Funnel to the existing ontology, eligibility and buy-side ranking engine.
- Funnel counts now come from the real product pool and sequential purpose, horizon, risk, liquidity and hard-eligibility filters; the UI contains no fixed counts.
- Renamed product output to “当前家庭约束下的候选产品” and exposed Why Selected, Why Not Others and per-product exclusion reasons.
- Kept the verified public catalog at eight products because expanding it without additional official evidence would weaken the data boundary; public evidence remains distinct from a live ICBC shelf.

## Phase 5 — Controlled AI Experience

- Expanded deterministic Chinese intake extraction for spouse, after-tax joint income, mortgage balance, child age/lifecycle stage, household location and overseas-education intent.
- Replaced the default example with the competition household sentence and kept every extracted value in a pending-confirmation draft.
- Added impact-ranked follow-up questions for cash flow, assets, protection, education stage/destination/prepared capital and debt details.
- Retained the canonical-fact boundary: confirming a draft records reviewed values but does not silently write or overwrite formal Household Facts.
- Reused the ELTC explanation modes added in Phase 3; AI changes wording depth but never recalculates the amount.

## Phase 6 — Advisor & Compliance

- Reframed the Advisor Action Center around “今天为什么需要联系这些客户？” instead of system modules.
- Each expanded household now shows Why Now, What Changed, What Matters, Suggested Discussion and What Not To Sell.
- Kept the advisor boundary as planning follow-up rather than automated marketing or Next Best Sale.
- Added a four-question compliance overview: Why This Advice, Suitability, Evidence and Replay.
- Moved production-readiness, security-quality, guardrail and specialist technical material behind an explicit evidence drawer.

## Phase 7 — Competition Delivery

- Added the five-engine V6 architecture, one-household three-minute Demo script and evidence-based acceptance matrix.
- Reframed the technical whitepaper, defense Q&A and ICBC business-value narrative around household constraints, ELTC, GRB and continuous wealth management.
- Lowered the experimental `/competition` page from primary navigation and reframed its opening around household safety and long-term-capital eligibility.
- Updated the existing presentation generator without replacing its design system; the 15-slide deck now leads with CHFH, ELTC and GRB, adds a deterministic Product Candidate Funnel, and presents the five engines under a Trust & Compliance Layer.
- Kept the public verified product catalog at eight items because no additional official evidence was introduced; Public Verified remains distinct from a live ICBC shelf.
- Removed a cross-platform currency-symbol assumption from the dashboard test and gave the interaction-heavy Twin accessibility test an explicit CI timeout after GitHub Actions exposed Linux/runner-only failures.

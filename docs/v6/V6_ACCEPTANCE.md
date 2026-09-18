# Fortune Copilot V6 Acceptance

## Acceptance policy

This document separates product evidence from the final engineering execution record. A check is accepted only when its named test, page or replay was actually inspected. Final command outcomes are recorded in the “Execution record” section after the release run; no result is pre-declared.

## Product acceptance matrix

| Area | Acceptance statement | Evidence path |
| --- | --- | --- |
| Product | A user can find household position, goals, ELTC, Risk Budget, portfolio, product candidates and Next Best Action | `/wealth`, `/wealth/cfs`, dashboard and component tests |
| ELTC logic | Changing a household responsibility changes ELTC or its uncovered requirement through deterministic recalculation | Eligible-capital bridge tests and financial/planning API |
| GRB | Behavioral evidence cannot increase Family Risk Budget | CFS risk-budget backend regression and Family Risk Profile UI |
| Product | An unsuitable product cannot enter the final executable candidate set | product ontology eligibility/ranking tests |
| AI intake | An extracted intake draft cannot silently overwrite canonical Household Facts without confirmation | bounded-intake tests and confirmation UI |
| Explainability | At least one candidate exposes Why Selected and an excluded candidate exposes Why Not Others | product-candidate UI test |
| Monitoring | A material household event can create a review/action and a Before → Event → After comparison | monitoring, action-center and Twin tests |
| Compliance | A decision can be traced to inputs, rules, product snapshot and decision evidence/replay | `/risk`, workflow tests and replay tests |

## Narrative acceptance

- The homepage explains within its first screen that Fortune Copilot starts with household responsibility and long-term-capital eligibility.
- The dashboard’s first screen answers safety, goals, ELTC and next action before specialist engineering metrics.
- ELTC is named “长期可投资资本 ELTC” and the UI explains why not all financial assets are investable.
- The risk view visibly separates Capacity, Willingness, Behavior and the final Budget.
- The product funnel displays calculated counts rather than hard-coded marketing numbers.
- Advisor language uses Next Best Action and What Not To Sell, not Next Best Product/Sale.
- Compliance begins with Why This Advice, Suitability, Evidence and Replay.
- Synthetic, Public Verified, Mock and Live are not conflated.

## Final engineering commands

The final release run must execute:

```bash
cd backend && PYTHONPATH="$PWD" ../.venv/bin/python -m pytest -q
cd backend && PYTHONPATH="$PWD" ../.venv/bin/python -m ruff check app tests alembic
cd backend && PYTHONPATH="$PWD" ../.venv/bin/python -m mypy app
npm --workspace frontend test -- --run
npm --workspace frontend run lint
npm --workspace frontend run typecheck
npm --workspace frontend run build
npm --workspace frontend run test:e2e
```

## Execution record

Final Phase 7 execution date: **2026-09-18** (Asia/Shanghai).

| Gate | Observed result | Notes |
| --- | --- | --- |
| Backend unit/integration tests | **198 passed** | `pytest -q`; one upstream Starlette deprecation warning |
| Backend lint | **Passed** | `ruff check app tests alembic` |
| Backend typecheck | **Passed** | `mypy app`; 262 source files checked |
| Frontend unit/component tests | **66 passed in 14 files** | Vitest run completed without failed or skipped tests |
| Frontend lint | **Passed** | ESLint completed successfully |
| Frontend typecheck | **Passed** | TypeScript completed successfully |
| Frontend production build | **Passed** | Vite emitted one non-blocking warning for the 596.68 kB `chartTheme` chunk |
| Connected browser regression | **21 passed** | Playwright ran against a migrated, seeded SQLite backend with `LLM_PROVIDER=mock` and the production preview server |
| Synthetic competition benchmark | **60 profiles completed** | B/C/D deterministic offline baselines measured; A general-LLM arm remains explicitly unmeasured |
| Competition presentation | **Passed finalizer and visual review** | 15 slides rendered; all slides were inspected for clipping and overlap |

Docker Compose was also attempted, but the local Docker daemon was unavailable at the configured Colima socket. This is an environment limitation, not recorded as a Compose pass. The connected Playwright suite was therefore run against the same migrated application stack started directly on the host. No Playwright scenario was skipped in the final run.

## Acceptance conclusion

The implemented V6 scope satisfies the product, logic, GRB, product-suitability, controlled-intake, explainability, monitoring and replay checks listed above in the local release environment. This conclusion does not imply production readiness, live ICBC connectivity, investment performance, customer conversion or operational SLA validation.

GitHub Actions run `35299965812` independently passed both PR jobs for release-candidate commit `faffdb8`: Backend completed lint, typecheck, 198 tests and empty-database migration; Frontend completed lint, typecheck, 66 tests, build and Playwright smoke. Runner notices about the Actions Node runtime and a future `ubuntu-latest` image migration remain informational warnings.

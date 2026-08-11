# Changelog

All notable release changes are recorded here. The project follows semantic versioning for Demo releases.

## 0.14.0 — 2026-08-11 — V5 comprehensive financial solution

- Rebuilt the public homepage around a Chinese-family wealth-management thesis, an original bank-grade red and charcoal hero visual, a restrained ICBC-adjacent design language without official brand assets, and productized navigation and service copy across client, advisor and risk surfaces.
- Added explicit comparison between generic overseas allocation templates and Chinese household realities, followed by the family-facts, goal-liability, eligible-capital, persistent-twin and comprehensive-solution theory stack.
- Added Canonical Persona V2 with eight heterogeneous synthetic archetypes A-H covering new-citizen, Shanghai dual-income, high-income professional, founder, scientist/equity-incentive, multigenerational HNW, cross-border and retired-family cases.
- Added stable member and enterprise references that seed all personas through the same Financial Graph, Profile, Need, Liability, ELTC, Twin, CFS, Product, Specialized and Monitoring services without persona-specific business branches.
- Added structural Golden Outcomes V2, which validates states, need types, gates, alerts and professional routes without hardcoding final planning amounts.
- Added Release Benchmark V2 with nine deterministic quality metrics and conflict-independence verification for product ranking.
- Added the 14-stage founder financing-event story from initial twin through valuation/dilution, exposure and risk-budget change, scenario/CFS recalculation, human review, approval, client confirmation and final snapshot.
- Added guarded admin endpoints for the V5 benchmark and founder story, black-box acceptance coverage and release documentation. E14 adds no migration; the migration head remains `0027_v5_calibration_registry`.

- Added all V5 feature flags with safe-off development defaults and enabled the completed Financial Graph, Client Profile, Liability Streams／ELTC, Persistent Twin, Family–Enterprise Twin, CFS and Product Ontology only in the isolated Docker demo.
- Added migration `0016_v5_financial_graph_core`, canonical financial entities, accounts, positions and ownership edges, plus additive backfill from V4 households, members and assets.
- Added migration `0017_v5_client_profile_and_needs` with versioned wealth profiles, evidence-bearing multi-tags, wealth needs and deterministic priorities.
- Added migration `0018_v5_liability_streams_eltc` with versioned liability streams and dated cash-flow schedules derived from goals and responsibilities.
- Added migration `0019_v5_persistent_financial_twin` with chained household snapshots, idempotent financial and life-event ledgers, and an optional persistent-snapshot link on existing simulation runs.
- Added migration `0020_v5_family_enterprise` with enterprise profiles, ownerships, valuations, cash flows, guarantees, liquidity events and optional enterprise-linked positions.
- Added migration `0021_v5_cfs_orchestration` with versioned CFS solutions, auditable solution components and controlled professional-service referrals.
- Added migration `0022_v5_product_ontology`, extending the existing Product model and adding evidence-bearing product snapshots without creating a parallel product table.
- Added migration `0023_v5_decision_evidence_v2` with searchable Recommendation／PlanReport evidence bindings and PlanReport evidence JSON.
- Added migrations `0024_v5_retirement_cross_border` and `0025_v5_trust_philanthropy` for normalized institutional entitlements, source-traceable currency exposures, evidence-triggered family-continuity needs and explicit philanthropy goals.
- Added migration `0026_v5_monitoring_and_triggers` for versioned monitoring policies, client-impact alerts, advisor triggers and longitudinal behavior observations, while extending the existing ActionItem instead of creating a parallel advisor-action table.
- Added deterministic graph integrity checks, V4 `HouseholdFacts` compatibility projection and non-blocking shadow parity diagnostics.
- Added fact-driven profile classification, completeness gaps, input hashes, all 14 V5 wealth-need types and professional-review boundaries without static persona lookup.
- Added RBAC-, confirmation-, valuation- and audit-aware Financial Graph position APIs.
- Added flagged profile and wealth-needs GET／recalculate APIs plus the client-facing `/wealth/profile` workspace.
- Added the flagged liability calendar, confirmed custom-stream and eligible-capital APIs plus the client-facing `/wealth/goals` workspace.
- Added flagged wealth-twin, life-event, event-timeline and historical-snapshot APIs plus the client-facing `/wealth/twin` workspace.
- Added confirmed family-enterprise write APIs, a deterministic family-enterprise view and the client-facing `/wealth/family-enterprise` cockpit.
- Added confirmed CFS create／read／recalculate and professional-referral APIs plus the client-facing `/wealth/cfs` decision ledger.
- Added a seven-factor household economic risk budget spanning capacity, willingness, behavior, existing economic exposure, liquidity, liability rigidity and time horizon.
- Added formal `NO_ACTION_REQUIRED` handling that preserves the deferred need amount, blocks product mapping and never fabricates a zero-value portfolio.
- Added Wealth Orchestrator routing from purpose and allowed risk to existing deterministic tools, controlled specialist services or an E07 0—N product-candidate layer.
- Added the verified-fund ontology adapter, five-state eligibility engine, buy-side ranking, product search／detail／eligibility／rank APIs and explicit stale-catalog education-only behavior.
- Added CFS product comparison UI with total-cost, liquidity, risk, alternative and conflict disclosure; `NO PRODUCT` is a first-class result and no purchase action is exposed.
- Added the 14-domain Decision Evidence V2 package, decision-material-only hashing, CFS approval snapshots and frozen historical replay APIs.
- Added the compliance-side evidence ledger and replay result that expose CFS, product-snapshot and hash integrity without dumping raw audit JSON into the primary workflow.
- Added deterministic retirement-floor and longevity／liquidity-gap calculations, source-currency exposure matching, trust／succession complexity detection and explicit philanthropy-goal materialization.
- Reused the E06 component and professional-referral chain as `Need → Complexity Gate → Professional Referral → Advisor Workflow`, with legal, tax, FX, trust-formation and return-promise boundaries.
- Added `/wealth/retirement`, `/wealth/global` and `/wealth/family`; specialized links appear only when the current CFS contains the corresponding need, so young single households never receive a default trust-center experience.
- Added eleven deterministic monitoring policies, seven behavior-signal types, reusable BehaviorIntervention cooling／education records, formal `NO_ACTION_REQUIRED`, non-sales Next Best Action and five flagged monitoring／advisor APIs.
- Made every monitoring action `do_not_sell`; market rises cannot produce hot-fund chasing, enterprise dependency routes to a family-enterprise review, and product maturity only triggers a purpose／suitability review without automatic replacement.
- Added the ordered ELTC bridge, suitability and safety gates, and made the former regional amount threshold reference-only for V5 eligibility.
- Added Purchasing Power V2 with household cost inflation, per-goal cost inflation and income adequacy; minimum-wage trends are restricted to income adequacy context.
- Made first-read graph materialization concurrency-safe with process coordination and database uniqueness constraints.
- Added the optional position-level intake step with loading, error, refinement, add and inline-delete-confirmation states.
- Added V4 A/B/C contract regression fixtures and real `0015 → head → 0015` migration coverage.
- Added six fact-composed profile scenarios, profile-hash invalidation tests and real `0016 → 0017 → 0016` rollback coverage.
- Added education installment, liability idempotency, ELTC A／B, V4 compatibility, RBAC and real `0017 → 0018 → 0017` migration coverage.
- Added canonical salary-event processing with confirmation and audit evidence, deterministic profile／needs／liability／ELTC recalculation, snapshot comparisons and replay-safe no-double-application behavior.
- Reused the existing Twin Simulator with an exact historical `TwinModelInput`, while preserving the legacy simulation path when no persistent snapshot is selected.
- Added real `0018 → 0019 → 0018` migration coverage and full desktop／mobile browser acceptance for the salary -30% scenario.
- Added five-component Enterprise–Household Dependency, economic equity exposure across private equity／employer stock／incentives／brokerage holdings, and high-dependency blocking of mechanical equity increases.
- Added enterprise valuation, dividend, cash-flow, guarantee and liquidity events to the shared Financial Event Ledger and persistent risk-budget snapshots with replay-safe idempotency.
- Added real `0019 → 0020 → 0019 → 0020` migration coverage and desktop／mobile browser acceptance for the 17 million CNY founder-equity hero scenario.
- Added real `0020 → 0021 → 0020` migration coverage, three CFS acceptance cases, full RBAC／confirmation／idempotency tests and desktop／mobile browser acceptance.
- Added real `0021 → 0022 → 0021` migration coverage, distribution-incentive non-improvement tests and desktop／mobile browser acceptance for both no-product and ranked-candidate paths.
- Added real `0022 → 0023 → 0022` migration coverage plus hash stability／invalidation and no-latest-product replay tests.
- Added real `0023 → 0024 → 0025 → 0024 → 0023` migration coverage, specialized-engine idempotency tests and desktop／mobile-ready client workspaces.
- Added real `0025 → 0026 → 0025` migration coverage plus alert／trigger／ActionItem replay idempotency, RBAC, confirmation and consumer-protection acceptance tests.
- Aligned the earlier enterprise-ratio and persistent-snapshot ORM metadata with their applied migrations; the migration head is now `0026`.
- Added real Compose desktop／mobile acceptance for the compliance evidence ledger and frozen replay, including zero browser errors or warnings.
- Replaced the path switch with a controlled route registry and added `/wealth`, `/wealth/history` and `/advisor/actions` while preserving V4 and earlier V5 compatibility routes.
- Added the client Wealth Dashboard, answering family safety, goal gap, next-money priority and replan need from Financial Analysis, Needs, Liability, ELTC, Twin and E10 monitoring evidence with domain-level failure states.
- Added Need Graph, CFS overview／component／candidate／professional-referral views, a five-option Scenario Lab, and a Twin Snapshot Report that binds snapshot, profile, liability, CFS and decision versions without adding a ninth report chapter.
- Upgraded `/advisor` to open on the five-group Action Center and expose Trigger, Changed Facts, Changed Needs, Changed CFS, Evidence and Recommended Conversation before the existing workflow and specialty workspaces.
- Added frontend monitoring contracts and `VITE_ENABLE_V5_MONITORING`; the Docker demo enables it while local development remains safe-off.
- Added Dashboard／Action Center／snapshot-report Vitest and axe coverage plus real 1440／1024／768／390 Compose browser acceptance with no horizontal overflow.
- Added the E12 deny-by-default Agent Tool Registry and six bounded roles for intake, goal drafting, deterministic household explanation, catalog-only scenario selection, evidence-only product research and advisor meeting preparation.
- Reused `AgentOrchestrationRun`, `AgentStepRun`, `IntakeDraft` and `KnowledgeChunk` without a new Agent database framework or migration, and isolated E12 single-step runs from the existing nine-agent history queries.
- Added fail-closed guardrails for prompt injection, highest-return product requests, purchase-amount delegation, risk-level escalation and eligibility overrides; blocked runs persist only the guardrail evidence and invoke no business tool.
- Added feature-flagged Tool Registry／run／replay APIs, Advisor Copilot RBAC and E12 acceptance tests proving no unconfirmed fact writes, invented education assumptions, catalog-external scenarios, eligibility override or Next Best Sale output.
- Added migration `0027_v5_calibration_registry` with source-versioned calibration datasets and effective-dated parameters carrying method, confidence, region, segment and limitations.
- Added `CalibrationPort.get_parameter(code, segment, region, date)`, idempotent registry materialization and fail-closed resolution that returns `needs_review` instead of guessing when a requested verified or bank-authorized parameter is absent.
- Added an auditable China purchasing-power registry containing controlled HCI／IAI rules, the verified national CPI observation and verified Hangzhou／Nanjing／Guangzhou minimum-wage CAGR observations; nominal consumption-expenditure changes are explicitly excluded as CPI proxies.
- Added separate `controlled_demo`, `empirically_calibrated` and `bank_authorized` mode disclosure across HCI, every GCI stream, IAI, the Wealth Goals UI, formal-report chapter 4／appendix F and Decision Evidence V2.
- Added feature-flagged calibration catalog／parameter APIs, safe-off development defaults, Docker Demo enablement and real `0026 → 0027 → 0026` migration coverage.

## 0.13.0 — 2026-08-05

- Added the one-click, ten-stage offline main Demo for the 35-year-old dual-income parenting household.
- Added deterministic A/B/C family comparison proving three distinct dynamic four-account configurations.
- Added durable Demo and experiment-suite ledgers, migration `0013_demo_release`, recovery-safe retries, preheating and TTL caching.
- Added seven release experiments with explicit test-only boundaries; participant comprehension and advisor-time studies remain protocols rather than fabricated bank results.
- Added the `/demo` release orchestration UI, release manifest, local warmup and black-box acceptance gates.
- Added synthetic-only SQLite backup/restore controls, release documentation, license and third-party notices.
- Added the Prompt 14 competition package: expanded README, 12-topic technical whitepaper and DOCX, timed demo script, 15-question defense library, ICBC value brief, editable 14-slide deck, final matrices and a standard-library delivery checker.
- Preserved the strict eight-chapter report, no-network Mock default and all consumer-protection guardrails.

## 0.12.0 — 2026-08-04

- Added signed sessions, RBAC/object grants, privacy controls, model-risk ledgers, eight adversarial tests and ten report release gates.

## 0.1.0 — 2026-08-04

- Established the FastAPI, React, SQLAlchemy, Alembic, testing and Docker Compose foundation.

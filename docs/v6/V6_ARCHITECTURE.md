# Fortune Copilot V6 Architecture

## 1. Architecture intent

Fortune Copilot V6 is a competition-focused refinement of V5, not a replacement platform. The decision object remains the household. The system preserves the existing canonical household model, deterministic financial engines, product ontology, monitoring, Financial Twin, advisor workflow and compliance evidence chain.

The public architecture is organized around five product engines and one cross-cutting trust layer. This is an external information architecture: it does not require the repository to be rewritten into six new services.

## 2. Decision order

```text
Household facts
  → life goals
  → family responsibilities
  → financial safety
  → eligible long-term capital (ELTC)
  → family risk budget (GRB)
  → asset allocation
  → product candidates
  → monitoring and replanning
```

No product, agent or model may bypass this order. A risk questionnaire is one input to the family risk budget, not the starting point for product sales.

## 3. Five engines

### 3.1 Family Understanding Engine

Responsibilities:

- natural-language household intake;
- draft extraction with evidence and missing fields;
- explicit confirmation before canonical Household Facts change;
- member, lifecycle, goal and need identification.

Primary existing implementation:

- bounded intake and trust services;
- client profile and household schemas;
- confirmation workflow and completeness checks.

AI may understand and explain language. It may not invent missing mortgage terms, assets, goals or other financial facts.

### 3.2 Household Capital Engine

Responsibilities:

- CHFH financial-health assessment;
- balance sheet, cash flow, liabilities and protection;
- dynamic four-purpose accounts;
- responsibility cash-flow deductions;
- ELTC calculation and capital-investment eligibility.

ELTC is computed as:

```text
deployable financial resources
− daily liquidity
− emergency reserve
− high-interest debt
− essential protection
− near-term responsibilities
− committed goal capital
− locked institutional assets
= eligible long-term capital (ELTC)
```

Only ELTC may formally enter long-term asset allocation. The four accounts are purpose accounts, not a fixed 10/20/30/40 allocation.

### 3.3 Wealth Planning Engine

Responsibilities:

- Goal + Risk + Behavior profile;
- family risk budget;
- asset allocation and scenario comparison;
- liquidity, CVaR, purchasing-power and diversification constraints.

The risk budget is bounded by Risk Capacity, Risk Willingness and Behavioral Risk. Behavioral evidence can maintain or reduce the budget; it cannot raise it. Risk Requirement may expose a goal conflict but cannot override capacity, willingness or behavior.

### 3.4 Product Intelligence Engine

Responsibilities:

- product ontology and public evidence snapshots;
- use, horizon, risk, liquidity and customer eligibility;
- ranking and concentration/conflict filters;
- explainable candidate generation.

The existing product engine remains the sole source of formal candidates. Candidate counts are produced by the deterministic funnel. “Public Verified” evidence never implies a live ICBC shelf, current sale status or transaction availability.

### 3.5 Wealth Companion Engine

Responsibilities:

- Financial Twin and household-event comparison;
- monitoring and material-change detection;
- behavior evidence and cooling periods;
- Next Best Action;
- advisor Why Now and continuous replanning.

The loop is `Before → Event → After`. Next Best Action may request information, safety actions, goal review, cooling-off, contribution changes or professional referral. It is not Next Best Product or Next Best Sale.

## 4. Trust & Compliance Layer

The cross-cutting layer constrains every engine:

- suitability and prohibited-action rules;
- versioned inputs, rules and product snapshots;
- evidence IDs and citation validity;
- replay, decision hash and audit trail;
- LLM field allowlists, schema validation and deterministic fallback;
- role-based disclosure and human review.

The compliance experience answers four questions first: Why This Advice, Suitability, Evidence and Replay. Low-level model runs, hashes and snapshot IDs remain available in expanded detail.

## 5. Authority boundaries

| Decision | Authority |
| --- | --- |
| Parse household language | bounded AI extraction |
| Confirm household fact | customer/advisor explicit confirmation |
| Calculate money, ratios and ELTC | deterministic financial engine |
| Set family risk budget | versioned GRB rules |
| Produce allocation | controlled mathematical model and constraints |
| Determine product eligibility | product ontology and suitability rules |
| Explain an existing result | bounded explanation layer |
| Release a formal plan | advisor/compliance/customer workflow |
| Execute a transaction | not provided by V6 |

## 6. Data truth labels

- **Synthetic**: generated household/persona facts used for repeatable tests and demos.
- **Public Verified**: public product or policy evidence with a source and verification date.
- **Mock**: simulated bank, product, model or integration adapter.
- **Live**: production data or connection. V6 has no Live ICBC connection and therefore displays no Live label.

## 7. Preserved V5 capabilities

V6 keeps retirement, family enterprise, cross-border exposure, trust/philanthropy, Financial Twin, monitoring, behavior, agents, RAG and advanced risk tooling. They remain available as specialist capabilities but do not displace the core competition story: household safety → ELTC → GRB → allocation → product → continuous review.

## 8. Deployment boundary

The current repository is a competition prototype using synthetic households, public product snapshots and Mock bank adapters. It performs no account opening, trading, product sale, guaranteed-return claim or live ICBC integration. Any institutional deployment requires separate data authorization, model governance, suitability mapping, legal/compliance approval, human operating procedures and staged validation.

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_database
from app.schemas.common import CapabilitiesResponse, Capability, DependencyStatus

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    settings = get_settings()
    database_status, database_detail = check_database()
    return CapabilitiesResponse(
        version=settings.app_version,
        runtime_mode=settings.app_env,
        mock_mode=settings.is_mock_mode,
        database=DependencyStatus(status=database_status, detail=database_detail),
        portals=["client", "advisor", "risk"],
        capabilities=[
            Capability(
                id="api_foundation",
                status="available",
                implementation="real",
                notes="FastAPI v1, error envelope, logging, configuration, database probe",
            ),
            Capability(
                id="llm_provider",
                status="available",
                implementation="mock",
                notes="Deterministic template provider; no key or network required",
            ),
            Capability(
                id="domain_data",
                status="available",
                implementation="real",
                notes=(
                    "45 versioned domain entities, validated CRUD, pagination, logical erasure "
                    "and privacy/evaluation ledgers"
                ),
            ),
            Capability(
                id="synthetic_households",
                status="available",
                implementation="real",
                notes="Validated A/B/C synthetic dataset; B is the main demo input set",
            ),
            Capability(
                id="financial_engine",
                status="available",
                implementation="real",
                notes=(
                    "Versioned Decimal statements, 20 auditable metrics, diagnostics, "
                    "protection gap and purchasing-power assessment"
                ),
            ),
            Capability(
                id="dynamic_account_planning",
                status="available",
                implementation="real",
                notes=(
                    "Six-stage lifecycle, goal present values, seven-step waterfall, "
                    "three denominators, five-hard-one-soft gates and counterfactual recompute"
                ),
            ),
            Capability(
                id="portfolio_suitability",
                status="available",
                implementation="real",
                notes=(
                    "Versioned Mock catalog, deterministic multi-objective grid optimizer, "
                    "three candidates, three suitability gates and bounded rebalancing"
                ),
            ),
            Capability(
                id="wealth_digital_twin",
                status="available",
                implementation="real",
                notes=(
                    "Monthly household state transitions, reproducible Monte Carlo, "
                    "19 composable stress scenarios, staged progress/cancel and audit export"
                ),
            ),
            Capability(
                id="behavioral_finance",
                status="available",
                implementation="real",
                notes=(
                    "Seven-dimension questionnaire, six recorded choice experiments, "
                    "11 evidence-backed biases, prudent risk downshift, personalized "
                    "interventions, cooling periods and synthetic/authorized A/B metrics"
                ),
            ),
            Capability(
                id="trusted_ai",
                status="available",
                implementation="real",
                notes=(
                    "Controlled offline hybrid RAG, dated citations, relational household graph, "
                    "nine-agent state machine, confirmation-only intake and deterministic "
                    "anti-hallucination validation"
                ),
            ),
            Capability(
                id="client_experience",
                status="available",
                implementation="real",
                notes=(
                    "Eleven client task workspaces, ECharts data-table contract, strict "
                    "eight-chapter preview, action calendar, privacy export, consent "
                    "withdrawal and human-review audit entry"
                ),
            ),
            Capability(
                id="advisor_compliance_workflow",
                status="available",
                implementation="real",
                notes=(
                    "Four-role RBAC, immutable eight-state plan versions, advisor queue, "
                    "compliance controls, client confirmation, complaint replay and audit export"
                ),
            ),
            Capability(
                id="formal_eight_chapter_reports",
                status="available",
                implementation="real",
                notes=(
                    "Exact eight-chapter immutable snapshots, deterministic numeric ledger, "
                    "controlled citations, persistent action lifecycle, HTML/PDF export and "
                    "auditable monthly/major-event recalculation"
                ),
            ),
            Capability(
                id="security_privacy_model_risk",
                status="available",
                implementation="real",
                notes=(
                    "Signed expiring sessions, RBAC and object grants, explicit privacy actions, "
                    "redacted model ledger, eight adversarial cases and ten release gates"
                ),
            ),
            Capability(
                id="complete_demo_release",
                status="available",
                implementation="real",
                notes=(
                    "One-click ten-stage offline story, three-family dynamic comparison, "
                    "seven test-boundary experiments, warmup, recovery and release ledger"
                ),
            ),
            Capability(
                id="bank_adapter",
                status="available",
                implementation="mock_only",
                notes=(
                    "Eight synthetic account interfaces through a project-owned Mock adapter; "
                    "credit limit is information-only and no production ICBC connection is claimed"
                ),
            ),
        ],
        guardrails=[
            "credit_limit_is_not_asset",
            "no_fixed_four_account_ratio",
            "no_principal_or_return_guarantee",
            "llm_must_not_calculate_key_numbers",
            "growth_70_percent_requires_long_term_funds_and_safety_gates",
            "minimum_wage_is_not_cpi",
            "no_default_stock_leverage_or_futures_recommendation",
            "release_requires_all_ten_quality_gates",
            "external_model_context_uses_field_allowlist",
        ],
    )

from enum import StrEnum


class LifecycleStage(StrEnum):
    EARLY_CAREER = "early_career"
    FAMILY_FORMATION = "family_formation"
    PARENTING = "parenting"
    MATURE_FAMILY = "mature_family"
    RETIREMENT_PREPARATION = "retirement_preparation"
    RETIREMENT_AND_LEGACY = "retirement_and_legacy"


class AccountBucket(StrEnum):
    DAILY_LIQUIDITY = "daily_liquidity"
    RISK_PROTECTION = "risk_protection"
    STABLE_GOALS = "stable_goals"
    LONG_TERM_GROWTH = "long_term_growth"


class AssetCategory(StrEnum):
    CASH = "cash"
    DEMAND_DEPOSIT = "demand_deposit"
    MONEY_MARKET = "money_market"
    TIME_DEPOSIT = "time_deposit"
    BANK_WEALTH_MANAGEMENT = "bank_wealth_management"
    BOND = "bond"
    BOND_FUND = "bond_fund"
    PUBLIC_FUND = "public_fund"
    EQUITY_FUND = "equity_fund"
    STOCK = "stock"
    PENSION_ACCOUNT = "pension_account"
    INSURANCE_CASH_VALUE = "insurance_cash_value"
    TRUST = "trust"
    PRIMARY_RESIDENCE = "primary_residence"
    INVESTMENT_PROPERTY = "investment_property"
    VEHICLE = "vehicle"
    OTHER = "other"


class LiabilityCategory(StrEnum):
    MORTGAGE = "mortgage"
    AUTO_LOAN = "auto_loan"
    CONSUMER_LOAN = "consumer_loan"
    CREDIT_CARD_UNPAID = "credit_card_unpaid"
    BANK_LOAN = "bank_loan"
    NON_BANK_LOAN = "non_bank_loan"
    OTHER = "other"


class GoalType(StrEnum):
    EMERGENCY_FUND = "emergency_fund"
    EDUCATION = "education"
    HOME = "home"
    RETIREMENT = "retirement"
    MEDICAL = "medical"
    TRAVEL = "travel"
    DEBT_REPAYMENT = "debt_repayment"
    FAMILY_SUPPORT = "family_support"
    WEALTH_TRANSFER = "wealth_transfer"
    OTHER = "other"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM_LOW = "medium_low"
    MEDIUM = "medium"
    MEDIUM_HIGH = "medium_high"
    HIGH = "high"


class ProductRiskLevel(StrEnum):
    R1 = "r1"
    R2 = "r2"
    R3 = "r3"
    R4 = "r4"
    R5 = "r5"


class PortfolioCandidateType(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    GROWTH = "growth"


class SuitabilityGateType(StrEnum):
    FAMILY_SAFETY = "family_safety"
    CUSTOMER = "customer"
    PRODUCT = "product"


class SuitabilityStatus(StrEnum):
    PASS = "pass"
    RESTRICT = "restrict"
    BLOCK = "block"


class SuitabilityDecision(StrEnum):
    ALLOW = "allow"
    DOWNGRADE = "downgrade"
    REJECT = "reject"
    EDUCATION_ONLY = "education_only"


class MarketScenario(StrEnum):
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"
    RISK_ON = "risk_on"


class SimulationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class BehaviorSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXITED = "exited"


class BehaviorInterventionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class ComplexityLevel(StrEnum):
    BASIC = "basic"
    STANDARD = "standard"
    COMPLEX = "complex"
    PROFESSIONAL = "professional"


class LiquidityLevel(StrEnum):
    IMMEDIATE = "immediate"
    WITHIN_7_DAYS = "within_7_days"
    WITHIN_30_DAYS = "within_30_days"
    WITHIN_1_YEAR = "within_1_year"
    ILLIQUID = "illiquid"


class RecommendationStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CUSTOMER_CONFIRMED = "customer_confirmed"
    EXECUTED = "executed"
    EXPIRED = "expired"


class PlanWorkflowState(StrEnum):
    DRAFT = "draft"
    CALCULATED = "calculated"
    SUITABILITY_CHECKED = "suitability_checked"
    ADVISOR_REVIEWED = "advisor_reviewed"
    COMPLIANCE_REVIEWED = "compliance_reviewed"
    CUSTOMER_CONFIRMED = "customer_confirmed"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class PlanWorkflowAction(StrEnum):
    CREATE = "create"
    CALCULATE = "calculate"
    SUITABILITY_CHECK = "suitability_check"
    ADVISOR_REVIEW = "advisor_review"
    REVISE_ADVICE = "revise_advice"
    EDIT_COMMUNICATION = "edit_communication"
    SUBMIT_COMPLIANCE = "submit_compliance"
    COMPLIANCE_APPROVE = "compliance_approve"
    COMPLIANCE_RETURN = "compliance_return"
    REQUIRE_HUMAN_REVIEW = "require_human_review"
    CUSTOMER_CONFIRM = "customer_confirm"
    ACTIVATE = "activate"
    SUPERSEDE = "supersede"


class AuditEventType(StrEnum):
    CONSENT_GRANTED = "consent_granted"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    DATA_CREATED = "data_created"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    DATA_ACCESSED = "data_accessed"
    CALCULATION_EXECUTED = "calculation_executed"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    REVIEW_RECORDED = "review_recorded"
    CONFIRMATION_RECORDED = "confirmation_recorded"
    MODEL_EXECUTED = "model_executed"
    RULE_APPLIED = "rule_applied"
    SUITABILITY_EVALUATED = "suitability_evaluated"
    SIMULATION_EXECUTED = "simulation_executed"
    SIMULATION_CANCELLED = "simulation_cancelled"
    BEHAVIOR_SESSION_STARTED = "behavior_session_started"
    BEHAVIOR_RESPONSE_RECORDED = "behavior_response_recorded"
    BEHAVIOR_ASSESSMENT_COMPLETED = "behavior_assessment_completed"
    BEHAVIOR_EXPERIMENT_EXITED = "behavior_experiment_exited"
    BEHAVIOR_INTERVENTION_UPDATED = "behavior_intervention_updated"
    KNOWLEDGE_RETRIEVED = "knowledge_retrieved"
    INTAKE_DRAFT_CREATED = "intake_draft_created"
    INTAKE_DRAFT_CONFIRMED = "intake_draft_confirmed"
    ORCHESTRATION_STARTED = "orchestration_started"
    AGENT_STEP_COMPLETED = "agent_step_completed"
    AGENT_STEP_DEGRADED = "agent_step_degraded"
    ORCHESTRATION_COMPLETED = "orchestration_completed"
    HALLUCINATION_BLOCKED = "hallucination_blocked"
    PLAN_WORKFLOW_VERSIONED = "plan_workflow_versioned"
    COMPLIANCE_DECISION_RECORDED = "compliance_decision_recorded"
    COMPLAINT_REPLAYED = "complaint_replayed"
    AUDIT_PACKAGE_EXPORTED = "audit_package_exported"
    MOCK_BANK_DATA_ACCESSED = "mock_bank_data_accessed"
    REPORT_GENERATED = "report_generated"
    REPORT_RECALCULATED = "report_recalculated"
    REPORT_ACTION_UPDATED = "report_action_updated"
    REPORT_EXPORT_SUCCEEDED = "report_export_succeeded"
    REPORT_EXPORT_FAILED = "report_export_failed"
    PRIVACY_DATA_EXPORTED = "privacy_data_exported"
    PRIVACY_DATA_ERASED = "privacy_data_erased"
    FILE_INSPECTION_RECORDED = "file_inspection_recorded"
    QUALITY_GATE_EVALUATED = "quality_gate_evaluated"
    REPORT_PUBLISHED = "report_published"
    ADVERSARIAL_EVALUATION_COMPLETED = "adversarial_evaluation_completed"
    DEMO_RUN_STARTED = "demo_run_started"
    DEMO_STAGE_COMPLETED = "demo_stage_completed"
    DEMO_RUN_COMPLETED = "demo_run_completed"
    DEMO_RUN_FAILED = "demo_run_failed"
    DEMO_DATA_RESET = "demo_data_reset"
    DEMO_PREHEATED = "demo_preheated"
    EXPERIMENT_SUITE_COMPLETED = "experiment_suite_completed"


class IntakeDraftStatus(StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    PARTIALLY_CONFIRMED = "partially_confirmed"
    CONFIRMED = "confirmed"


class OrchestrationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class AgentStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class CashFlowFrequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    ONE_TIME = "one_time"
    IRREGULAR = "irregular"


class IncomeType(StrEnum):
    EMPLOYMENT = "employment"
    BUSINESS = "business"
    PENSION = "pension"
    RENTAL = "rental"
    INVESTMENT = "investment"
    TRANSFER = "transfer"
    OTHER = "other"


class ExpenseNecessity(StrEnum):
    ESSENTIAL = "essential"
    FLEXIBLE = "flexible"


class ExpenseCategory(StrEnum):
    BASIC_LIVING = "basic_living"
    DISCRETIONARY = "discretionary"
    PARENT_SUPPORT = "parent_support"
    CHILD_EDUCATION = "child_education"
    MEDICAL = "medical"
    INSURANCE_PREMIUM = "insurance_premium"
    DEBT_SERVICE = "debt_service"
    TAX = "tax"
    OTHER = "other"


class RateType(StrEnum):
    FIXED = "fixed"
    FLOATING = "floating"


class InsuranceType(StrEnum):
    TERM_LIFE = "term_life"
    WHOLE_LIFE = "whole_life"
    MEDICAL = "medical"
    CRITICAL_ILLNESS = "critical_illness"
    ACCIDENT = "accident"
    ANNUITY = "annuity"
    PROPERTY = "property"
    OTHER = "other"


class PropertyUse(StrEnum):
    NOT_PROPERTY = "not_property"
    PRIMARY_RESIDENCE = "primary_residence"
    INVESTMENT_PROPERTY = "investment_property"


class GoalRigidity(StrEnum):
    FLEXIBLE = "flexible"
    IMPORTANT = "important"
    RIGID = "rigid"


class EmploymentStability(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

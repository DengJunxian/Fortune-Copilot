from enum import StrEnum


class LifecycleStage(StrEnum):
    EARLY_CAREER = "early_career"
    FAMILY_FORMATION = "family_formation"
    PARENTING = "parenting"
    MATURE_FAMILY = "mature_family"
    RETIREMENT_PREPARATION = "retirement_preparation"
    RETIREMENT_AND_LEGACY = "retirement_and_legacy"


class CalibrationMode(StrEnum):
    CONTROLLED_DEMO = "controlled_demo"
    EMPIRICALLY_CALIBRATED = "empirically_calibrated"
    BANK_AUTHORIZED = "bank_authorized"


class AccountBucket(StrEnum):
    DAILY_LIQUIDITY = "daily_liquidity"
    RISK_PROTECTION = "risk_protection"
    STABLE_GOALS = "stable_goals"
    LONG_TERM_GROWTH = "long_term_growth"


class AssetPurposeDimension(StrEnum):
    DAILY = "daily"
    PROTECTION = "protection"
    STABLE = "stable"
    GROWTH = "growth"


class AccountWrapper(StrEnum):
    ORDINARY = "ordinary"
    DEMAND_ACCOUNT = "demand_account"
    PERSONAL_PENSION = "personal_pension"
    SOCIAL_SECURITY = "social_security"
    ENTERPRISE_ANNUITY = "enterprise_annuity"
    OCCUPATIONAL_ANNUITY = "occupational_annuity"
    PROVIDENT_FUND = "provident_fund"
    INSURANCE = "insurance"
    OTHER = "other"


class FinancialEntityType(StrEnum):
    HOUSEHOLD = "household"
    PERSON = "person"
    ENTERPRISE = "enterprise"
    TRUST = "trust"
    OTHER = "other"


class OwnershipType(StrEnum):
    HOUSEHOLD_MEMBER = "household_member"
    DIRECT = "direct"
    JOINT = "joint"
    BENEFICIAL = "beneficial"
    CONTROL = "control"
    OTHER = "other"


class WealthTier(StrEnum):
    FOUNDATIONAL = "foundational"
    EMERGING_AFFLUENT = "emerging_affluent"
    AFFLUENT = "affluent"
    HIGH_NET_WORTH = "high_net_worth"


class ServiceComplexity(StrEnum):
    STANDARD = "standard"
    ENHANCED = "enhanced"
    COMPLEX = "complex"
    SPECIALIST = "specialist"


class ComplexityBand(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PensionStage(StrEnum):
    NOT_STARTED = "not_started"
    ACCUMULATION = "accumulation"
    TRANSITION = "transition"
    RETIREMENT = "retirement"


class ClientProfileStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    NEEDS_REVIEW = "needs_review"


class ProfileTagSeverity(StrEnum):
    INFO = "info"
    WATCH = "watch"
    HIGH = "high"


class WealthNeedType(StrEnum):
    LIQUIDITY = "liquidity"
    EMERGENCY = "emergency"
    DEBT_REPAYMENT = "debt_repayment"
    MEDICAL_PROTECTION = "medical_protection"
    DEATH_PROTECTION = "death_protection"
    EDUCATION = "education"
    HOUSING = "housing"
    RETIREMENT = "retirement"
    LONG_TERM_GROWTH = "long_term_growth"
    ENTERPRISE_CONCENTRATION = "enterprise_concentration"
    CURRENCY_MATCHING = "currency_matching"
    SUCCESSION = "succession"
    TRUST = "trust"
    PHILANTHROPY = "philanthropy"


class WealthNeedStatus(StrEnum):
    IDENTIFIED = "identified"
    PARTIALLY_PREPARED = "partially_prepared"
    PREPARED = "prepared"
    NEEDS_REVIEW = "needs_review"


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


class LiabilityStreamType(StrEnum):
    EDUCATION = "education"
    HOUSING = "housing"
    RETIREMENT = "retirement"
    MEDICAL = "medical"
    FAMILY_SUPPORT = "family_support"
    DEBT_SERVICE = "debt_service"
    PROTECTION = "protection"
    LIVING = "living"
    SUCCESSION = "succession"
    PHILANTHROPY = "philanthropy"
    OTHER = "other"


class HouseholdSnapshotStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class FinancialEventDomain(StrEnum):
    LIFE = "life"
    ENTERPRISE = "enterprise"


class FinancialEventStatus(StrEnum):
    CONFIRMED = "confirmed"
    APPLIED = "applied"
    PROCESSED = "processed"
    FAILED = "failed"


class LifeEventType(StrEnum):
    SALARY_CHANGE = "salary_change"


class EnterpriseStage(StrEnum):
    STARTUP = "startup"
    GROWTH = "growth"
    MATURE = "mature"
    PRE_IPO = "pre_ipo"
    PUBLIC = "public"
    EXITING = "exiting"


class EnterpriseListedStatus(StrEnum):
    UNLISTED = "unlisted"
    LISTED = "listed"
    DELISTED = "delisted"


class EnterpriseType(StrEnum):
    OPERATING_COMPANY = "operating_company"
    HOLDING_COMPANY = "holding_company"
    PARTNERSHIP = "partnership"
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    FAMILY_BUSINESS = "family_business"
    OTHER = "other"


class EnterpriseInstrumentType(StrEnum):
    COMMON_EQUITY = "common_equity"
    PREFERRED_EQUITY = "preferred_equity"
    PARTNERSHIP_INTEREST = "partnership_interest"
    RESTRICTED_STOCK = "restricted_stock"
    STOCK_OPTION = "stock_option"
    OTHER = "other"


class EnterpriseValuationMethod(StrEnum):
    TRANSACTION = "transaction"
    MARKET_MULTIPLE = "market_multiple"
    DISCOUNTED_CASH_FLOW = "discounted_cash_flow"
    NET_ASSET = "net_asset"
    USER_ESTIMATE = "user_estimate"
    OTHER = "other"


class EvidenceConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EnterpriseCashflowType(StrEnum):
    SALARY = "salary"
    DIVIDEND = "dividend"
    BUSINESS_DISTRIBUTION = "business_distribution"
    MANAGEMENT_FEE = "management_fee"
    OTHER = "other"


class EnterpriseCashflowStability(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EnterpriseGuaranteeType(StrEnum):
    PERSONAL = "personal"
    JOINT_AND_SEVERAL = "joint_and_several"
    PROPERTY = "property"
    CROSS_GUARANTEE = "cross_guarantee"
    OTHER = "other"


class EnterpriseEventType(StrEnum):
    FUNDING = "funding"
    IPO = "ipo"
    LOCKUP_EXPIRY = "lockup_expiry"
    EQUITY_SALE = "equity_sale"
    DIVIDEND_CHANGE = "dividend_change"
    VALUATION_CHANGE = "valuation_change"
    GUARANTEE_CHANGE = "guarantee_change"
    CASHFLOW_DETERIORATION = "cashflow_deterioration"


class EnterpriseEventStatus(StrEnum):
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CFSSolutionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    NEEDS_REVIEW = "needs_review"


class CFSComponentType(StrEnum):
    LIQUIDITY = "liquidity"
    DEBT = "debt"
    PROTECTION = "protection"
    HOUSING = "housing"
    EDUCATION = "education"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    ENTERPRISE_RISK = "enterprise_risk"
    CROSS_BORDER = "cross_border"
    SUCCESSION = "succession"
    TRUST = "trust"
    PHILANTHROPY = "philanthropy"
    PROFESSIONAL_SERVICE = "professional_service"
    NO_ACTION = "no_action"


class CFSComponentStatus(StrEnum):
    RECOMMENDED = "recommended"
    NO_ACTION_REQUIRED = "no_action_required"
    PROFESSIONAL_REVIEW_REQUIRED = "professional_review_required"
    COMPLETED = "completed"


class CFSTimeHorizon(StrEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    ONGOING = "ongoing"


class ProfessionalSpecialistType(StrEnum):
    PRIVATE_BANKER = "private_banker"
    INVESTMENT_ADVISOR = "investment_advisor"
    PENSION_SPECIALIST = "pension_specialist"
    INSURANCE_SPECIALIST = "insurance_specialist"
    CROSS_BORDER_SPECIALIST = "cross_border_specialist"
    TRUST_SPECIALIST = "trust_specialist"
    LEGAL_TAX_PROFESSIONAL = "legal_tax_professional"
    PHILANTHROPY_SPECIALIST = "philanthropy_specialist"


class ProfessionalReferralUrgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProfessionalReferralStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InstitutionalEntitlementType(StrEnum):
    SOCIAL_SECURITY = "social_security"
    ENTERPRISE_PENSION = "enterprise_pension"
    OCCUPATIONAL_PENSION = "occupational_pension"
    PERSONAL_PENSION = "personal_pension"
    ANNUITY = "annuity"
    RENTAL = "rental"
    FINANCIAL_WITHDRAWAL = "financial_withdrawal"


class CurrencyExposureType(StrEnum):
    ASSET_CURRENCY = "asset_currency"
    INCOME_CURRENCY = "income_currency"
    LIABILITY_CURRENCY = "liability_currency"
    EDUCATION_LIABILITY = "education_liability"
    ENTERPRISE_REVENUE = "enterprise_revenue"
    FUTURE_OBLIGATION = "future_obligation"


class CurrencyExposureDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class CurrencyExposureHorizon(StrEnum):
    CURRENT = "current"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class SpecializedComplexity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrustSuccessionNeedType(StrEnum):
    MINOR_BENEFICIARY = "minor_beneficiary"
    SPECIAL_CARE = "special_care"
    MULTI_GENERATION = "multi_generation"
    ENTERPRISE_SUCCESSION = "enterprise_succession"
    OWNERSHIP_COMPLEXITY = "ownership_complexity"
    INSURANCE_TRUST_COORDINATION = "insurance_trust_coordination"


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


class ProductFamily(StrEnum):
    DEPOSIT = "deposit"
    BANK_WEALTH_MANAGEMENT = "bank_wealth_management"
    MONEY_MARKET_FUND = "money_market_fund"
    BOND_FUND = "bond_fund"
    EQUITY_INDEX_FUND = "equity_index_fund"
    BOND_TREASURY = "bond_treasury"
    GOLD = "gold"
    INSURANCE = "insurance"
    PERSONAL_PENSION_PRODUCT = "personal_pension_product"
    TRUST_WEALTH_TRANSFER_TOOL = "trust_wealth_transfer_tool"
    CASH_MANAGEMENT = "cash_management"


class ProductEligibilityDecision(StrEnum):
    ELIGIBLE = "eligible"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"
    EDUCATION_ONLY = "education_only"
    PROFESSIONAL_REVIEW = "professional_review"


class PortfolioCandidateType(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    GROWTH = "growth"


class SuitabilityGateType(StrEnum):
    FAMILY_SAFETY = "family_safety"
    CUSTOMER = "customer"
    PRODUCT = "product"
    CHANNEL = "channel"
    TRANSACTION_TIME = "transaction_time"


class SuitabilityStatus(StrEnum):
    PASS = "pass"
    RESTRICT = "restrict"
    BLOCK = "block"


class SuitabilityDecision(StrEnum):
    ALLOW = "allow"
    DOWNGRADE = "downgrade"
    REJECT = "reject"
    EDUCATION_ONLY = "education_only"
    ESCALATE = "escalate"


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


class MonitoringPolicyType(StrEnum):
    GOAL_FUNDING_DRIFT = "goal_funding_drift"
    ELTC_CHANGE = "eltc_change"
    RISK_BUDGET_BREACH = "risk_budget_breach"
    ASSET_CONCENTRATION = "asset_concentration"
    ENTERPRISE_DEPENDENCY = "enterprise_dependency"
    CURRENCY_MISMATCH = "currency_mismatch"
    PRODUCT_MATURITY = "product_maturity"
    SNAPSHOT_STALENESS = "snapshot_staleness"
    RETIREMENT_GAP = "retirement_gap"
    LIFE_EVENT = "life_event"
    BEHAVIOR_DRIFT = "behavior_drift"


class MonitoringComparator(StrEnum):
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    EQUAL = "eq"
    ABSOLUTE_CHANGE_AT_LEAST = "absolute_change_gte"
    EVENT_OCCURRED = "event_occurred"


class MonitoringCadence(StrEnum):
    REALTIME = "realtime"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    EVENT_DRIVEN = "event_driven"


class MonitoringSeverity(StrEnum):
    INFO = "info"
    WATCH = "watch"
    HIGH = "high"
    CRITICAL = "critical"


class MonitoringAlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AdvisorTriggerStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class BehaviorObservationType(StrEnum):
    PERFORMANCE_CHASING = "performance_chasing"
    PANIC_REDEMPTION = "panic_redemption"
    FREQUENT_OVERRIDES = "frequent_overrides"
    GOAL_CHANGES = "goal_changes"
    EARLY_WITHDRAWAL = "early_withdrawal"
    HIGH_FREQUENCY_ATTENTION = "high_frequency_attention"
    IGNORED_PROTECTION = "ignored_protection"


class RiskLimitEffect(StrEnum):
    MAINTAIN = "maintain"
    REDUCE = "reduce"


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

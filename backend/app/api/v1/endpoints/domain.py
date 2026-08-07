from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor, require_sensitive_confirmation
from app.core.database import get_session
from app.core.errors import AppError
from app.models.assessment import RiskAssessment
from app.models.common import RecordMixin
from app.models.family import ConsentRecord, Household, HouseholdMember
from app.models.finance import (
    Asset,
    ExpenseItem,
    FinancialGoal,
    IncomeSource,
    InsurancePolicy,
    Liability,
)
from app.schemas.assessment import (
    RiskAssessmentCreate,
    RiskAssessmentOut,
    RiskAssessmentUpdate,
)
from app.schemas.family import (
    ConsentRecordCreate,
    ConsentRecordOut,
    ConsentRecordUpdate,
    HouseholdCreate,
    HouseholdMemberCreate,
    HouseholdMemberOut,
    HouseholdMemberUpdate,
    HouseholdOut,
    HouseholdUpdate,
)
from app.schemas.finance import (
    AssetCreate,
    AssetOut,
    AssetUpdate,
    ExpenseItemCreate,
    ExpenseItemOut,
    ExpenseItemUpdate,
    FinancialGoalCreate,
    FinancialGoalOut,
    FinancialGoalUpdate,
    IncomeSourceCreate,
    IncomeSourceOut,
    IncomeSourceUpdate,
    InsurancePolicyCreate,
    InsurancePolicyOut,
    InsurancePolicyUpdate,
    LiabilityCreate,
    LiabilityOut,
    LiabilityUpdate,
)
from app.schemas.records import PageResponse, Pagination
from app.services.crud import (
    create_record,
    ensure_household,
    ensure_household_reference,
    get_active,
    list_active,
    soft_delete_record,
    update_record,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["household-data"])


def _validate_merged_update(
    record: RecordMixin,
    payload: BaseModel,
    create_schema: type[BaseModel],
) -> None:
    """Validate the complete post-patch record, including cross-field rules."""
    values = {
        field_name: getattr(record, field_name)
        for field_name in create_schema.model_fields
        if hasattr(record, field_name)
    }
    values.update(
        payload.model_dump(mode="python", exclude_unset=True, exclude={"expected_version"})
    )
    try:
        create_schema.model_validate(values)
    except ValidationError as exc:
        safe_fields = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "更新后数据无效")),
                "type": str(error.get("type", "validation_error")),
            }
            for error in exc.errors()
        ]
        raise AppError(
            "validation_error",
            "更新后数据校验失败",
            status_code=422,
            details={"fields": safe_fields},
        ) from exc


@router.post("/households", response_model=HouseholdOut, status_code=status.HTTP_201_CREATED)
def create_household(
    payload: HouseholdCreate,
    session: SessionDependency,
    actor: ActorDependency,
) -> Household:
    return create_record(session, Household, payload, actor)


@router.get("/households", response_model=PageResponse[HouseholdOut])
def list_households(
    session: SessionDependency,
    actor: ActorDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageResponse[HouseholdOut]:
    items, total, pages = list_active(
        session,
        Household,
        page=page,
        page_size=page_size,
        allowed_household_ids=None
        if actor.role == "admin" or "*" in actor.household_ids
        else actor.household_ids,
    )
    return PageResponse[HouseholdOut](
        items=[HouseholdOut.model_validate(item) for item in items],
        pagination=Pagination(page=page, page_size=page_size, total=total, pages=pages),
    )


@router.get("/households/{household_id}", response_model=HouseholdOut)
def get_household(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> Household:
    return ensure_household(session, household_id)


@router.patch("/households/{household_id}", response_model=HouseholdOut)
def update_household(
    household_id: str,
    payload: HouseholdUpdate,
    session: SessionDependency,
    actor: ActorDependency,
) -> Household:
    record = ensure_household(session, household_id)
    _validate_merged_update(record, payload, HouseholdCreate)
    return update_record(session, record, payload, actor)


@router.delete("/households/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(
    request_context: Request,
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    require_sensitive_confirmation(request_context, "legacy_soft_delete_household")
    record = ensure_household(session, household_id)
    soft_delete_record(session, record, actor, expected_version=expected_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@dataclass(frozen=True)
class ResourceSpec:
    slug: str
    singular: str
    model: type[RecordMixin]
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    output_schema: type[BaseModel]
    reference_fields: tuple[tuple[str, type[RecordMixin]], ...] = ()


RESOURCE_SPECS = (
    ResourceSpec(
        "members",
        "member",
        HouseholdMember,
        HouseholdMemberCreate,
        HouseholdMemberUpdate,
        HouseholdMemberOut,
    ),
    ResourceSpec(
        "assets",
        "asset",
        Asset,
        AssetCreate,
        AssetUpdate,
        AssetOut,
        (("owner_member_id", HouseholdMember),),
    ),
    ResourceSpec(
        "liabilities",
        "liability",
        Liability,
        LiabilityCreate,
        LiabilityUpdate,
        LiabilityOut,
        (("borrower_member_id", HouseholdMember), ("linked_asset_id", Asset)),
    ),
    ResourceSpec(
        "incomes",
        "income",
        IncomeSource,
        IncomeSourceCreate,
        IncomeSourceUpdate,
        IncomeSourceOut,
        (("member_id", HouseholdMember),),
    ),
    ResourceSpec(
        "expenses",
        "expense",
        ExpenseItem,
        ExpenseItemCreate,
        ExpenseItemUpdate,
        ExpenseItemOut,
        (("member_id", HouseholdMember),),
    ),
    ResourceSpec(
        "insurance-policies",
        "insurance_policy",
        InsurancePolicy,
        InsurancePolicyCreate,
        InsurancePolicyUpdate,
        InsurancePolicyOut,
        (("insured_member_id", HouseholdMember),),
    ),
    ResourceSpec(
        "goals",
        "goal",
        FinancialGoal,
        FinancialGoalCreate,
        FinancialGoalUpdate,
        FinancialGoalOut,
    ),
    ResourceSpec(
        "risk-assessments",
        "risk_assessment",
        RiskAssessment,
        RiskAssessmentCreate,
        RiskAssessmentUpdate,
        RiskAssessmentOut,
    ),
    ResourceSpec(
        "consents",
        "consent",
        ConsentRecord,
        ConsentRecordCreate,
        ConsentRecordUpdate,
        ConsentRecordOut,
        (("member_id", HouseholdMember),),
    ),
)


def _validate_references(
    session: Session,
    spec: ResourceSpec,
    payload: BaseModel,
    household_id: str,
) -> None:
    values = payload.model_dump(mode="python", exclude_unset=True)
    for field_name, model in spec.reference_fields:
        if field_name in values:
            ensure_household_reference(session, model, values[field_name], household_id)


def _build_resource_router(spec: ResourceSpec) -> APIRouter:
    resource_router = APIRouter(prefix=f"/households/{{household_id}}/{spec.slug}")

    def create_endpoint(
        household_id: str,
        payload: BaseModel,
        session: SessionDependency,
        actor: ActorDependency,
    ) -> RecordMixin:
        ensure_household(session, household_id)
        _validate_references(session, spec, payload, household_id)
        return create_record(session, spec.model, payload, actor, household_id=household_id)

    create_endpoint.__name__ = f"create_{spec.singular}"
    create_endpoint.__annotations__["payload"] = spec.create_schema
    resource_router.add_api_route(
        "",
        create_endpoint,
        methods=["POST"],
        response_model=spec.output_schema,
        status_code=status.HTTP_201_CREATED,
    )

    def list_endpoint(
        household_id: str,
        session: SessionDependency,
        _actor: ActorDependency,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> dict[str, object]:
        ensure_household(session, household_id)
        items, total, pages = list_active(
            session,
            spec.model,
            household_id=household_id,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [spec.output_schema.model_validate(item) for item in items],
            "pagination": Pagination(
                page=page,
                page_size=page_size,
                total=total,
                pages=pages,
            ),
        }

    list_endpoint.__name__ = f"list_{spec.slug.replace('-', '_')}"
    resource_router.add_api_route(
        "",
        list_endpoint,
        methods=["GET"],
        response_model=PageResponse[spec.output_schema],  # type: ignore[name-defined]
    )

    def get_endpoint(
        household_id: str,
        record_id: str,
        session: SessionDependency,
        _actor: ActorDependency,
    ) -> RecordMixin:
        ensure_household(session, household_id)
        return get_active(session, spec.model, record_id, household_id=household_id)

    get_endpoint.__name__ = f"get_{spec.singular}"
    resource_router.add_api_route(
        "/{record_id}",
        get_endpoint,
        methods=["GET"],
        response_model=spec.output_schema,
    )

    def update_endpoint(
        household_id: str,
        record_id: str,
        payload: BaseModel,
        session: SessionDependency,
        actor: ActorDependency,
    ) -> RecordMixin:
        ensure_household(session, household_id)
        _validate_references(session, spec, payload, household_id)
        record = get_active(session, spec.model, record_id, household_id=household_id)
        _validate_merged_update(record, payload, spec.create_schema)
        return update_record(session, record, payload, actor)

    update_endpoint.__name__ = f"update_{spec.singular}"
    update_endpoint.__annotations__["payload"] = spec.update_schema
    resource_router.add_api_route(
        "/{record_id}",
        update_endpoint,
        methods=["PATCH"],
        response_model=spec.output_schema,
    )

    def delete_endpoint(
        household_id: str,
        record_id: str,
        session: SessionDependency,
        actor: ActorDependency,
        expected_version: Annotated[int, Query(ge=1)],
    ) -> Response:
        ensure_household(session, household_id)
        record = get_active(session, spec.model, record_id, household_id=household_id)
        soft_delete_record(session, record, actor, expected_version=expected_version)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    delete_endpoint.__name__ = f"delete_{spec.singular}"
    resource_router.add_api_route(
        "/{record_id}",
        delete_endpoint,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
    )
    return resource_router


for resource_spec in RESOURCE_SPECS:
    router.include_router(_build_resource_router(resource_spec))

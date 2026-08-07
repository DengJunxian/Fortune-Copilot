from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, ActorRole, require_actor, require_roles
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.schemas.formal_report import (
    FormalReportDocument,
    ReportActionList,
    ReportActionUpdateRequest,
    ReportActionUpdateResponse,
    ReportGenerationChain,
    ReportGenerationRequest,
    ReportRecalculationRequest,
)
from app.services.reporting.render import render_formal_html, render_formal_pdf
from app.services.reporting.service import (
    generate_formal_report,
    get_current_formal_report,
    get_formal_report,
    get_report_record,
    list_report_actions,
    recalculate_formal_report,
    record_export_event,
    report_generation_chain,
    require_formal_report_visibility,
    update_report_action,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["formal-eight-chapter-reports"])
READ_ROLES: tuple[ActorRole, ...] = ("client", "advisor", "compliance", "admin")
WRITE_ROLES: tuple[ActorRole, ...] = ("client", "advisor", "admin")


@router.get(
    "/households/{household_id}/reports/current",
    response_model=FormalReportDocument | None,
)
def read_current_report(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> FormalReportDocument | None:
    require_roles(actor, READ_ROLES)
    document = get_current_formal_report(session, household_id)
    return require_formal_report_visibility(document, actor) if document is not None else None


@router.post(
    "/households/{household_id}/reports",
    response_model=FormalReportDocument,
    status_code=status.HTTP_201_CREATED,
)
def create_formal_report(
    household_id: str,
    request: ReportGenerationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> FormalReportDocument:
    require_roles(actor, WRITE_ROLES)
    return generate_formal_report(session, household_id, request, actor, get_settings())


@router.post(
    "/households/{household_id}/reports/recalculate",
    response_model=FormalReportDocument,
)
def recalculate_report(
    household_id: str,
    request: ReportRecalculationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> FormalReportDocument:
    require_roles(actor, WRITE_ROLES)
    return recalculate_formal_report(session, household_id, request, actor, get_settings())


@router.get(
    "/households/{household_id}/reports/generation-chain",
    response_model=ReportGenerationChain,
)
def read_generation_chain(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> ReportGenerationChain:
    require_roles(actor, ("advisor", "compliance", "admin"))
    return report_generation_chain(session, household_id)


@router.get(
    "/households/{household_id}/report-actions",
    response_model=ReportActionList,
)
def read_report_actions(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> ReportActionList:
    require_roles(actor, READ_ROLES)
    document = get_current_formal_report(session, household_id)
    if document is not None:
        require_formal_report_visibility(document, actor)
    return list_report_actions(session, household_id)


@router.post(
    "/households/{household_id}/report-actions/{action_code}",
    response_model=ReportActionUpdateResponse,
)
def change_report_action(
    household_id: str,
    action_code: str,
    request: ReportActionUpdateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ReportActionUpdateResponse:
    require_roles(actor, WRITE_ROLES)
    document = get_current_formal_report(session, household_id)
    if document is not None:
        require_formal_report_visibility(document, actor)
    return update_report_action(
        session,
        household_id,
        action_code,
        request,
        actor,
        get_settings(),
    )


@router.get("/reports/{report_id}", response_model=FormalReportDocument)
def read_report(
    report_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> FormalReportDocument:
    require_roles(actor, READ_ROLES)
    return require_formal_report_visibility(get_formal_report(session, report_id), actor)


def _export(
    report_id: str,
    export_format: str,
    session: Session,
    actor: ActorContext,
) -> Response:
    require_roles(actor, READ_ROLES)
    record = get_report_record(session, report_id)
    document = require_formal_report_visibility(get_formal_report(session, report_id), actor)
    try:
        if export_format == "html":
            payload, diagnostics = render_formal_html(document)
            media_type = "text/html; charset=utf-8"
        else:
            payload, diagnostics = render_formal_pdf(document)
            media_type = "application/pdf"
    except Exception as exc:
        session.rollback()
        event_id = record_export_event(
            session,
            record,
            actor,
            export_format=export_format,
            succeeded=False,
            diagnostics={
                "stage": "render",
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
                "report_version": record.report_version,
            },
        )
        raise AppError(
            "report_export_failed",
            "正式规划书导出失败；诊断事件已记录",
            status_code=500,
            details={"diagnostic_event_id": event_id, "format": export_format},
        ) from exc
    event_id = record_export_event(
        session,
        record,
        actor,
        export_format=export_format,
        succeeded=True,
        diagnostics=diagnostics,
    )
    filename = (
        f"wealthtwin-{document.household_code.lower()}-report-r{document.sequence}.{export_format}"
    )
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Version": document.versions.report_version,
            "X-Report-Hash": document.report_hash,
            "X-Export-Audit-ID": event_id,
        },
    )


@router.get("/reports/{report_id}/html")
def export_report_html(
    report_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> Response:
    return _export(report_id, "html", session, actor)


@router.get("/reports/{report_id}/pdf")
def export_report_pdf(
    report_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> Response:
    return _export(report_id, "pdf", session, actor)

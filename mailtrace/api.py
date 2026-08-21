from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from mailtrace.config import Settings, get_settings
from mailtrace.db import get_db
from mailtrace.dns_lookup import lookup_dns
from mailtrace.models import AnalystNote, AppSetting, Case, Evidence
from mailtrace.parser import ParseLimitError, safe_filename
from mailtrace.reports import (
    bundle_report,
    csv_report,
    html_report,
    json_report,
    pdf_report,
    text_report,
)
from mailtrace.schemas import (
    AnalysisSettings,
    CaseCreate,
    CaseDetail,
    CaseSummary,
    CaseUpdate,
    ConclusionUpdate,
    DNSRequest,
    EvidenceResponse,
    NoteCreate,
    NoteResponse,
    PasteEvidence,
)
from mailtrace.service import (
    add_audit,
    delete_case_files,
    delete_original,
    ingest_evidence,
    prune_expired_analyses,
)

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _case_query() -> Any:
    return select(Case).options(
        selectinload(Case.evidence),
        selectinload(Case.notes),
        selectinload(Case.audit_entries),
    )


def get_case_or_404(db: Session, case_id: str) -> Case:
    case = db.scalar(_case_query().where(Case.id == case_id))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return cast(Case, case)


def get_evidence_or_404(db: Session, case_id: str, evidence_id: str) -> tuple[Case, Evidence]:
    case = get_case_or_404(db, case_id)
    evidence = next((item for item in case.evidence if item.id == evidence_id), None)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found in this case")
    return case, evidence


def _summary(case: Case) -> CaseSummary:
    return CaseSummary(
        id=case.id,
        title=case.title,
        description=case.description,
        status=case.status,
        conclusion=case.conclusion,
        created_at=case.created_at,
        updated_at=case.updated_at,
        evidence_count=len(case.evidence),
    )


def _detail(case: Case) -> CaseDetail:
    return CaseDetail(
        **_summary(case).model_dump(),
        evidence=[EvidenceResponse.model_validate(item) for item in case.evidence],
        notes=[NoteResponse.model_validate(item) for item in case.notes],
        audit_entries=list(case.audit_entries),
    )


@router.get("/health")
def health(db: Db) -> dict[str, str]:
    db.execute(select(func.count(Case.id))).scalar_one()
    return {"status": "ok", "service": "mailtrace"}


@router.get("/settings")
def settings_info(settings: AppSettings, db: Db) -> dict[str, Any]:
    saved = db.get(AppSetting, "preferences")
    preferences = (
        saved.value if saved else {"retention_days": None, "dns_enrichment_enabled": False}
    )
    return {
        "local_first": True,
        "dns_enabled_by_default": False,
        "limits": {
            "max_upload_bytes": settings.max_upload_bytes,
            "max_headers": settings.max_headers,
            "max_header_line_bytes": settings.max_header_line_bytes,
            "max_mime_depth": settings.max_mime_depth,
            "max_mime_parts": settings.max_mime_parts,
            "max_attachments": settings.max_attachments,
        },
        "preferences": preferences,
        "safety": {
            "attachments_executed": False,
            "active_html_rendered": False,
            "external_resources_loaded": False,
            "links_automatically_opened": False,
            "evidence_submitted_externally": False,
        },
    }


@router.put("/settings")
def update_settings(payload: AnalysisSettings, db: Db, settings: AppSettings) -> dict[str, Any]:
    item = db.get(AppSetting, "preferences")
    value = payload.model_dump()
    if item:
        item.value = value
    else:
        db.add(AppSetting(key="preferences", value=value))
    db.commit()
    prune_expired_analyses(db, settings, payload.retention_days)
    return value


def _analysis_dict(evidence: Evidence, case: Case) -> dict[str, Any]:
    parsed = evidence.parsed_message
    return {
        "id": evidence.id,
        "case_id": evidence.case_id,
        "status": evidence.analysis_status,
        "stage": evidence.analysis_stage,
        "created_at": evidence.uploaded_at,
        "title": case.title,
        "filename": evidence.original_filename,
        "sha256": evidence.sha256,
        "file_size": evidence.file_size,
        "input_type": evidence.input_type,
        "summary": {
            "subject": parsed.get("subject"),
            "date": parsed.get("date"),
            "from": parsed.get("from", []),
            "assessment": evidence.assessment,
            "authentication": evidence.authentication,
            "hop_count": len(evidence.hops),
            "attachment_count": len(evidence.attachments),
            "observation_count": len(evidence.observations),
        },
        "parsed_message": parsed,
        "authentication": evidence.authentication,
        "hops": evidence.hops,
        "observations": evidence.observations,
        "attachments": evidence.attachments,
        "mime_structure": evidence.mime_structure,
        "urls": evidence.urls,
        "limitations": evidence.limitations,
        "warnings": evidence.parse_warnings,
        "timings": evidence.timings,
        "raw_available": bool(evidence.stored_filename),
        "exports": ["pdf", "json", "csv", "txt", "html", "bundle"],
    }


@router.get("/analyses")
def list_analyses(db: Db, settings: AppSettings) -> list[dict[str, Any]]:
    saved = db.get(AppSetting, "preferences")
    retention_days = saved.value.get("retention_days") if saved else None
    prune_expired_analyses(db, settings, retention_days)
    rows = db.execute(
        select(Evidence, Case)
        .join(Case, Case.id == Evidence.case_id)
        .order_by(Evidence.uploaded_at.desc())
    ).all()
    return [_analysis_dict(evidence, case) for evidence, case in rows]


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, db: Db) -> dict[str, Any]:
    row = db.execute(
        select(Evidence, Case)
        .join(Case, Case.id == Evidence.case_id)
        .where(Evidence.id == analysis_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _analysis_dict(*row)


@router.get("/analyses/{analysis_id}/state")
def get_analysis_state(analysis_id: str, db: Db) -> dict[str, Any]:
    item = db.get(Evidence, analysis_id)
    if not item:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "id": item.id,
        "status": item.analysis_status,
        "stage": item.analysis_stage,
        "polling_url": f"/api/analyses/{item.id}/state",
    }


def _create_analysis(
    db: Session,
    settings: Settings,
    data: bytes,
    filename: str,
    input_type: str,
    retain_original: bool,
) -> Evidence:
    case = Case(title=safe_filename(filename, "MailTrace analysis"), description="")
    db.add(case)
    db.flush()
    try:
        evidence = ingest_evidence(db, case, data, filename, input_type, retain_original, settings)
    except Exception:
        db.rollback()
        raise
    subject = evidence.parsed_message.get("subject")
    if subject:
        case.title = str(subject)[:200]
        db.commit()
    return evidence


@router.post("/analyses/headers", status_code=202)
def create_header_analysis(payload: PasteEvidence, db: Db, settings: AppSettings) -> dict[str, Any]:
    try:
        item = _create_analysis(
            db,
            settings,
            payload.raw_headers.encode("utf-8"),
            payload.filename,
            "headers",
            payload.retain_original,
        )
    except ParseLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": item.id,
        "status": item.analysis_status,
        "stage": item.analysis_stage,
        "polling_url": f"/api/analyses/{item.id}/state",
    }


@router.post("/analyses/upload", status_code=202)
async def create_upload_analysis(
    db: Db,
    settings: AppSettings,
    file: Annotated[UploadFile, File(description="An RFC 5322 .eml file")],
    retain_original: Annotated[bool, Form()] = True,
) -> dict[str, Any]:
    filename = file.filename or "uploaded-email.eml"
    if Path(filename.replace("\\", "/")).suffix.lower() != ".eml":
        raise HTTPException(status_code=415, detail="Only .eml files are accepted")
    data = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    try:
        item = _create_analysis(db, settings, data, filename, "eml", retain_original)
    except ParseLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": item.id,
        "status": item.analysis_status,
        "stage": item.analysis_stage,
        "polling_url": f"/api/analyses/{item.id}/state",
    }


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, db: Db, settings: AppSettings) -> Response:
    item = db.get(Evidence, analysis_id)
    if not item:
        raise HTTPException(status_code=404, detail="Analysis not found")
    case = item.case
    delete_case_files(case, settings)
    db.delete(case)
    db.commit()
    return Response(status_code=204)


@router.get("/analyses/{analysis_id}/raw")
def analysis_raw(analysis_id: str, db: Db, settings: AppSettings) -> Response:
    item = db.get(Evidence, analysis_id)
    if not item:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return raw_evidence(item.case_id, item.id, db, settings)


@router.get("/methodology")
def methodology() -> dict[str, Any]:
    return {
        "name": "Evidence-led email forensic triage",
        "authentication_boundary": "Reported results are parsed from message evidence and are not independent cryptographic verification.",
        "assessment_labels": [
            "No clear concern found",
            "Some evidence needs review",
            "Concerning evidence found",
            "Insufficient evidence",
            "Parsing incomplete",
        ],
        "network_default": "disabled",
    }


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    db: Db,
    search: str = Query(default="", max_length=200),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[CaseSummary]:
    statement = _case_query().order_by(Case.updated_at.desc())
    if search:
        escaped = search.replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Case.title.ilike(f"%{escaped}%", escape="\\"))
    if status_filter:
        statement = statement.where(Case.status == status_filter)
    return [_summary(case) for case in db.scalars(statement).unique().all()]


@router.post("/cases", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Db) -> CaseDetail:
    case = Case(title=payload.title.strip(), description=payload.description.strip())
    db.add(case)
    db.flush()
    add_audit(db, case, "case_created", metadata={"title": case.title})
    db.commit()
    return _detail(get_case_or_404(db, case.id))


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, db: Db) -> CaseDetail:
    return _detail(get_case_or_404(db, case_id))


@router.patch("/cases/{case_id}", response_model=CaseDetail)
def update_case(case_id: str, payload: CaseUpdate, db: Db) -> CaseDetail:
    case = get_case_or_404(db, case_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(case, key, value.strip() if isinstance(value, str) else value)
    add_audit(db, case, "case_updated", metadata={"fields": sorted(changes)})
    db.commit()
    return _detail(get_case_or_404(db, case_id))


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: str, db: Db, settings: AppSettings) -> Response:
    case = get_case_or_404(db, case_id)
    delete_case_files(case, settings)
    db.delete(case)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/cases/{case_id}/evidence/paste",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def paste_evidence(case_id: str, payload: PasteEvidence, db: Db, settings: AppSettings) -> Evidence:
    case = get_case_or_404(db, case_id)
    data = payload.raw_headers.encode("utf-8")
    try:
        return ingest_evidence(
            db, case, data, payload.filename, "headers", payload.retain_original, settings
        )
    except ParseLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/cases/{case_id}/evidence/upload",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    case_id: str,
    db: Db,
    settings: AppSettings,
    file: Annotated[UploadFile, File(description="An .eml or raw-header .txt file")],
    retain_original: Annotated[bool, Form()] = True,
) -> Evidence:
    case = get_case_or_404(db, case_id)
    original_name = file.filename or "uploaded-evidence"
    extension = Path(original_name.replace("\\", "/")).suffix.lower()
    if extension not in {".eml", ".txt"}:
        raise HTTPException(
            status_code=415, detail="Only .eml and .txt evidence files are accepted"
        )
    data = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    input_type = "eml" if extension == ".eml" else "headers"
    try:
        return ingest_evidence(db, case, data, original_name, input_type, retain_original, settings)
    except ParseLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/cases/{case_id}/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(case_id: str, evidence_id: str, db: Db) -> Evidence:
    return get_evidence_or_404(db, case_id, evidence_id)[1]


@router.get("/cases/{case_id}/evidence/{evidence_id}/raw")
def raw_evidence(case_id: str, evidence_id: str, db: Db, settings: AppSettings) -> Response:
    _, evidence = get_evidence_or_404(db, case_id, evidence_id)
    if not evidence.stored_filename:
        raise HTTPException(
            status_code=410, detail="The original evidence was not retained or has been deleted"
        )
    path = (settings.evidence_dir / evidence.stored_filename).resolve()
    if path.parent != settings.evidence_dir.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Stored evidence file is unavailable")
    return Response(
        path.read_bytes(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename(evidence.original_filename)}.txt"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/cases/{case_id}/evidence/{evidence_id}/original", status_code=204)
def remove_original(case_id: str, evidence_id: str, db: Db, settings: AppSettings) -> Response:
    case, evidence = get_evidence_or_404(db, case_id, evidence_id)
    delete_original(db, case, evidence, settings)
    return Response(status_code=204)


@router.post("/cases/{case_id}/notes", response_model=NoteResponse, status_code=201)
def add_note(case_id: str, payload: NoteCreate, db: Db) -> AnalystNote:
    case = get_case_or_404(db, case_id)
    note = AnalystNote(
        case_id=case.id, note=payload.note.strip(), author_label=payload.author_label.strip()
    )
    db.add(note)
    add_audit(db, case, "analyst_note_added", metadata={"author_label": note.author_label})
    db.commit()
    db.refresh(note)
    return note


@router.delete("/cases/{case_id}/notes/{note_id}", status_code=204)
def remove_note(case_id: str, note_id: str, db: Db) -> Response:
    case = get_case_or_404(db, case_id)
    note = next((item for item in case.notes if item.id == note_id), None)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    add_audit(db, case, "analyst_note_deleted")
    db.commit()
    return Response(status_code=204)


@router.put("/cases/{case_id}/conclusion", response_model=CaseDetail)
def set_conclusion(case_id: str, payload: ConclusionUpdate, db: Db) -> CaseDetail:
    case = get_case_or_404(db, case_id)
    case.conclusion = payload.conclusion
    add_audit(db, case, "analyst_conclusion_changed", metadata={"conclusion": payload.conclusion})
    db.commit()
    return _detail(get_case_or_404(db, case_id))


@router.post("/dns/lookup")
def dns_check(payload: DNSRequest, db: Db, settings: AppSettings) -> dict[str, Any]:
    saved = db.get(AppSetting, "preferences")
    if not saved or not saved.value.get("dns_enrichment_enabled", False):
        raise HTTPException(status_code=403, detail="Optional DNS enrichment is disabled")
    try:
        return lookup_dns(db, payload.domain, payload.selector, settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


ReportFormat = Literal["html", "pdf", "json", "csv", "txt", "bundle"]


@router.get("/cases/{case_id}/reports/{report_format}")
def report(case_id: str, report_format: ReportFormat, db: Db, settings: AppSettings) -> Response:
    case = get_case_or_404(db, case_id)
    base = safe_filename(case.title, "mailtrace-case")
    if report_format == "html":
        content, media_type, extension = html_report(case), "text/html; charset=utf-8", "html"
    elif report_format == "pdf":
        content, media_type, extension = pdf_report(case), "application/pdf", "pdf"
    elif report_format == "json":
        content, media_type, extension = json_report(case), "application/json", "json"
    elif report_format == "csv":
        content, media_type, extension = csv_report(case), "text/csv; charset=utf-8", "csv"
    elif report_format == "txt":
        content, media_type, extension = text_report(case), "text/plain; charset=utf-8", "txt"
    else:
        originals: dict[str, bytes] = {}
        for evidence in case.evidence:
            if not evidence.stored_filename:
                continue
            path = (settings.evidence_dir / evidence.stored_filename).resolve()
            if path.parent == settings.evidence_dir.resolve() and path.is_file():
                originals[evidence.id] = path.read_bytes()
        content, media_type, extension = bundle_report(case, originals), "application/zip", "zip"
    add_audit(db, case, "report_generated", metadata={"format": report_format})
    db.commit()
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{base}.{extension}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox"
            if report_format == "html"
            else "default-src 'none'",
        },
    )


@router.get("/analyses/{analysis_id}/exports/{report_format}")
def analysis_report(
    analysis_id: str,
    report_format: ReportFormat,
    db: Db,
    settings: AppSettings,
) -> Response:
    item = db.get(Evidence, analysis_id)
    if not item:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return report(item.case_id, report_format, db, settings)


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


@router.get("/demos")
def list_demos() -> list[dict[str, str]]:
    catalog = json.loads((FIXTURE_ROOT / "catalog.json").read_text(encoding="utf-8"))
    return [
        {key: str(value) for key, value in item.items() if key != "expected_rules"}
        for item in catalog
    ]


@router.post("/demos/{slug}/load", response_model=CaseDetail, status_code=201)
def load_demo(slug: str, db: Db, settings: AppSettings) -> CaseDetail:
    catalog = json.loads((FIXTURE_ROOT / "catalog.json").read_text(encoding="utf-8"))
    demo = next((item for item in catalog if item["slug"] == slug), None)
    if not demo:
        raise HTTPException(status_code=404, detail="Demonstration case not found")
    fixture = (FIXTURE_ROOT / f"{slug}.eml").resolve()
    if fixture.parent != FIXTURE_ROOT.resolve() or not fixture.is_file():
        raise HTTPException(status_code=500, detail="Demonstration fixture is missing")
    case = Case(title=demo["title"], description=demo["description"])
    db.add(case)
    db.flush()
    add_audit(db, case, "case_created_from_demo", metadata={"fixture": slug})
    db.commit()
    case = get_case_or_404(db, case.id)
    ingest_evidence(db, case, fixture.read_bytes(), fixture.name, "eml", True, settings)
    return _detail(get_case_or_404(db, case.id))

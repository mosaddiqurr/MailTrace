from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from mailtrace.config import Settings
from mailtrace.models import AuditEntry, Case, Evidence
from mailtrace.parser import parse_evidence, safe_filename


def add_audit(
    db: Session,
    case: Case,
    action: str,
    evidence_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEntry(
            case_id=case.id,
            action=action,
            evidence_id=evidence_id,
            metadata_json=metadata or {},
        )
    )


def ingest_evidence(
    db: Session,
    case: Case,
    data: bytes,
    original_filename: str,
    input_type: str,
    retain_original: bool,
    settings: Settings,
) -> Evidence:
    result = parse_evidence(data, input_type, settings)
    digest = hashlib.sha256(data).hexdigest()
    evidence_id = str(uuid4())
    stored_filename: str | None = None
    stored_path: Path | None = None
    if retain_original:
        suffix = ".eml" if input_type == "eml" else ".txt"
        stored_filename = f"{evidence_id}{suffix}"
        stored_path = settings.evidence_dir / stored_filename
        with stored_path.open("xb") as output:
            output.write(data)

    evidence = Evidence(
        id=evidence_id,
        case_id=case.id,
        original_filename=safe_filename(original_filename, f"evidence-{evidence_id}"),
        stored_filename=stored_filename,
        sha256=digest,
        file_size=len(data),
        input_type=input_type,
        parser_version=result["parser_version"],
        parse_status="complete",
        parse_warnings=result["warnings"],
        parsed_message=result["parsed_message"],
        authentication=result["authentication"],
        hops=result["hops"],
        entities=result["entities"],
        observations=result["observations"],
        attachments=result["attachments"],
        mime_structure=result["mime_structure"],
        urls=result["urls"],
        assessment=result["assessment"],
        limitations=result["limitations"],
        timings=result["timings"],
        analysis_status="complete",
        analysis_stage="building_report",
    )
    db.add(evidence)
    add_audit(
        db,
        case,
        "evidence_ingested",
        evidence_id,
        {
            "sha256": digest,
            "size": len(data),
            "input_type": input_type,
            "original_retained": retain_original,
        },
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        if stored_path and stored_path.exists():
            stored_path.unlink()
        raise
    db.refresh(evidence)
    return evidence


def delete_original(db: Session, case: Case, evidence: Evidence, settings: Settings) -> None:
    if evidence.stored_filename:
        path = settings.evidence_dir / evidence.stored_filename
        resolved = path.resolve()
        if resolved.parent != settings.evidence_dir.resolve():
            raise ValueError("Stored evidence path escaped the evidence directory")
        if resolved.exists():
            resolved.unlink()
        evidence.stored_filename = None
    add_audit(
        db,
        case,
        "original_evidence_deleted",
        evidence.id,
        {"sha256_preserved": evidence.sha256},
    )
    db.commit()


def delete_case_files(case: Case, settings: Settings) -> None:
    evidence_root = settings.evidence_dir.resolve()
    for item in case.evidence:
        if not item.stored_filename:
            continue
        path = (settings.evidence_dir / item.stored_filename).resolve()
        if path.parent == evidence_root and path.exists():
            path.unlink()


def prune_expired_analyses(db: Session, settings: Settings, retention_days: int | None) -> int:
    if retention_days is None:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    expired = list(db.scalars(select(Evidence).where(Evidence.uploaded_at < cutoff)).all())
    removed = 0
    for item in expired:
        case = item.case
        if item.stored_filename:
            path = (settings.evidence_dir / item.stored_filename).resolve()
            if path.parent == settings.evidence_dir.resolve() and path.exists():
                path.unlink()
        if len(case.evidence) == 1:
            db.delete(case)
        else:
            db.delete(item)
        removed += 1
    if removed:
        db.commit()
    return removed

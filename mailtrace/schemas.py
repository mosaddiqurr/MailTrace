from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Conclusion = Literal["unreviewed", "likely_legitimate", "suspicious", "inconclusive"]


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: Literal["open", "closed", "archived"] | None = None


class ConclusionUpdate(BaseModel):
    conclusion: Conclusion


class NoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=20_000)
    author_label: str = Field(default="Local analyst", min_length=1, max_length=100)


class PasteEvidence(BaseModel):
    raw_headers: str = Field(min_length=1)
    filename: str = Field(default="pasted-headers.txt", max_length=255)
    retain_original: bool = True


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: str
    conclusion: str
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    note: str
    author_label: str
    created_at: datetime


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: str | None
    action: str
    metadata_json: dict[str, Any]
    created_at: datetime


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    original_filename: str
    stored_filename: str | None
    sha256: str
    file_size: int
    input_type: str
    uploaded_at: datetime
    parser_version: str
    parse_status: str
    parse_warnings: list[dict[str, Any]]
    parsed_message: dict[str, Any]
    authentication: dict[str, Any]
    hops: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    mime_structure: dict[str, Any] = Field(default_factory=dict)
    urls: list[dict[str, Any]] = Field(default_factory=list)
    assessment: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    timings: dict[str, Any] = Field(default_factory=dict)
    analysis_status: str = "complete"
    analysis_stage: str = "building_report"
    error_code: str | None = None
    error_message: str | None = None


class CaseDetail(CaseSummary):
    evidence: list[EvidenceResponse]
    notes: list[NoteResponse]
    audit_entries: list[AuditResponse]


class DNSRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=253)
    selector: str | None = Field(default=None, max_length=63)


class AnalysisState(BaseModel):
    id: str
    status: Literal["queued", "processing", "complete", "partial", "failed"]
    stage: str
    polling_url: str


class AnalysisSettings(BaseModel):
    retention_days: Literal[7, 30, 90] | None = None
    dns_enrichment_enabled: bool = False

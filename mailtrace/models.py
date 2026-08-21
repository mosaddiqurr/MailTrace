from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mailtrace.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open")
    conclusion: Mapped[str] = mapped_column(String(32), default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Evidence.uploaded_at"
    )
    notes: Mapped[list[AnalystNote]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="AnalystNote.created_at"
    )
    audit_entries: Mapped[list[AuditEntry]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="AuditEntry.created_at"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer)
    input_type: Mapped[str] = mapped_column(String(20))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    parser_version: Mapped[str] = mapped_column(String(32))
    parse_status: Mapped[str] = mapped_column(String(20), default="complete")
    parse_warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    parsed_message: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    authentication: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hops: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    entities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    observations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    mime_structure: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    urls: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    timings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    analysis_status: Mapped[str] = mapped_column(String(20), default="complete")
    analysis_stage: Mapped[str] = mapped_column(String(40), default="building_report")
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)

    case: Mapped[Case] = relationship(back_populates="evidence")


class AnalystNote(Base):
    __tablename__ = "analyst_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    note: Mapped[str] = mapped_column(Text)
    author_label: Mapped[str] = mapped_column(String(100), default="Local analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="notes")


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="audit_entries")


class DNSCache(Base):
    __tablename__ = "dns_cache"

    key: Mapped[str] = mapped_column(String(500), primary_key=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

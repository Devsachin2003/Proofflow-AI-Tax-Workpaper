"""Baseline tables. Packet rows are written only by the importer and never modified by API handlers.

The one additive exception: evidence attached by users is stored as `document` rows with origin='workpaper'
(ids W-0001...), so attached files, messages and notes are traced exactly like packet documents.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PacketImport(Base):
    __tablename__ = "packet_import"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    client_id: Mapped[str] = mapped_column(String(32))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    counts: Mapped[dict] = mapped_column(JSONB)
    raw: Mapped[dict] = mapped_column(JSONB)


class ReferenceData(Base):
    __tablename__ = "reference_data"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict | list] = mapped_column(JSONB)


class Person(Base):
    __tablename__ = "person"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    role: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    ssn: Mapped[str | None] = mapped_column(String(16))
    ip_pin: Mapped[str | None] = mapped_column(String(16))
    dob: Mapped[date | None] = mapped_column(Date)
    occupation: Mapped[str | None] = mapped_column(String(128))
    relationship: Mapped[str | None] = mapped_column(String(64))
    months_lived_with_you: Mapped[int | None] = mapped_column(Integer)
    full_time_student: Mapped[bool | None] = mapped_column(Boolean)
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB)


class Document(Base):
    __tablename__ = "document"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    issuer: Mapped[str | None] = mapped_column(String(255))
    belongs_to: Mapped[str] = mapped_column(String(32))
    tax_year: Mapped[int | None] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uploaded_by: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str | None] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer)
    marked_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_status: Mapped[str] = mapped_column(String(32))
    extraction_values: Mapped[int] = mapped_column(Integer, default=0)
    extraction_reason: Mapped[str | None] = mapped_column(Text)
    # packet = imported baseline; workpaper = evidence attached by a user (file, message, note)
    origin: Mapped[str] = mapped_column(String(16), default="packet")
    evidence_kind: Mapped[str | None] = mapped_column(String(16))
    attached_by: Mapped[str | None] = mapped_column(String(16))
    attached_to: Mapped[str | None] = mapped_column(String(128))


class DocumentPage(Base):
    __tablename__ = "document_page"
    document_id: Mapped[str] = mapped_column(ForeignKey("document.id"), primary_key=True)
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    printed_content: Mapped[str] = mapped_column(Text)


class ExtractedValue(Base):
    __tablename__ = "extracted_value"
    __table_args__ = (
        ForeignKeyConstraint(["document_id", "page"], ["document_page.document_id", "document_page.page"]),
        Index("ix_ev_doc_page", "document_id", "page"),
    )
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(16))
    page: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(Text)
    value: Mapped[object] = mapped_column(JSONB)
    value_num: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    value_type: Mapped[str] = mapped_column(String(32))
    text_as_read: Mapped[str] = mapped_column(Text, default="")
    x0: Mapped[float] = mapped_column(Float)
    y0: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)


class ReturnVersion(Base):
    __tablename__ = "return_version"
    version: Mapped[str] = mapped_column(String(8), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(Text)
    summary: Mapped[dict] = mapped_column(JSONB)
    tax_effect_rates: Mapped[dict] = mapped_column(JSONB)
    carryovers_out: Mapped[dict] = mapped_column(JSONB)
    documents_used: Mapped[list[str]] = mapped_column(ARRAY(String))
    documents_superseded: Mapped[list[str]] = mapped_column(ARRAY(String))


class ReturnLine(Base):
    __tablename__ = "return_line"
    __table_args__ = (
        UniqueConstraint("version", "key", name="uq_line_version_key"),
        Index("ix_line_version_form", "version", "form"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(ForeignKey("return_version.version"))
    key: Mapped[str] = mapped_column(String(64))
    ordinal: Mapped[int] = mapped_column(Integer)
    jurisdiction: Mapped[str] = mapped_column(String(16))
    form: Mapped[str] = mapped_column(String(32))
    line: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(Text)
    value: Mapped[object] = mapped_column(JSONB)
    value_num: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    rule: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)


class LineInput(Base):
    __tablename__ = "line_input"
    __table_args__ = (Index("ix_line_input_reverse", "version", "input_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("return_line.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(8))
    line_key: Mapped[str] = mapped_column(String(64))
    input_key: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)


class SourceRef(Base):
    """Provenance edge: an owner (line, asset, diagnostic, timeline event, prior-year line) cites a reference."""

    __tablename__ = "source_ref"
    __table_args__ = (
        Index("ix_source_owner", "owner_type", "version", "owner_key"),
        Index("ix_source_target", "target_type", "target_id"),
        Index("ix_source_document", "document_id", "version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(16))
    owner_key: Mapped[str] = mapped_column(String(128))
    version: Mapped[str | None] = mapped_column(String(8))
    position: Mapped[int] = mapped_column(Integer)
    raw_ref: Mapped[str] = mapped_column(Text)
    ref_type: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[str | None] = mapped_column(String(16))
    page: Mapped[int | None] = mapped_column(Integer)
    resolved: Mapped[bool] = mapped_column(Boolean)
    resolution_note: Mapped[str | None] = mapped_column(Text)


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = (UniqueConstraint("version", "asset_id", name="uq_asset_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(8))  # v1..v3 or "prior"
    asset_id: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    activity: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB)


class Diagnostic(Base):
    __tablename__ = "diagnostic"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(ForeignKey("return_version.version"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    refs: Mapped[list[str]] = mapped_column(ARRAY(String))


class VersionChange(Base):
    __tablename__ = "version_change"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(ForeignKey("return_version.version"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(64))
    change: Mapped[str] = mapped_column(String(16))
    old: Mapped[object | None] = mapped_column(JSONB)
    new: Mapped[object | None] = mapped_column(JSONB)


class ClientItem(Base):
    __tablename__ = "client_item"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # questionnaire | message | call_note
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    author: Mapped[str | None] = mapped_column(String(128))
    recipient: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB)


class TimelineEvent(Base):
    __tablename__ = "timeline_event"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str | None] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text)
    refs: Mapped[list[str]] = mapped_column(ARRAY(String))


class Notice(Base):
    __tablename__ = "notice"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agency: Mapped[str] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(Text)
    tax_year: Mapped[int] = mapped_column(Integer)
    dated: Mapped[date] = mapped_column(Date)
    response_due: Mapped[date | None] = mapped_column(Date)
    document_id: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB)


class EfileSubmission(Base):
    __tablename__ = "efile_submission"
    submission_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    jurisdiction: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    errors: Mapped[list] = mapped_column(JSONB)


class WhatIfScenario(Base):
    __tablename__ = "what_if_scenario"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    base_version: Mapped[str] = mapped_column(String(8))
    choices: Mapped[dict] = mapped_column(JSONB)
    federal: Mapped[dict] = mapped_column(JSONB)
    california: Mapped[dict] = mapped_column(JSONB)
    changed_lines: Mapped[list] = mapped_column(JSONB)


class AppUser(Base):
    __tablename__ = "app_user"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16))  # staff | client
    credential: Mapped[str | None] = mapped_column(String(32))
    sensitive_clearance: Mapped[bool] = mapped_column(Boolean, default=False)
    active_from: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    ptin: Mapped[str | None] = mapped_column(String(16))
    person_id: Mapped[str | None] = mapped_column(String(32))

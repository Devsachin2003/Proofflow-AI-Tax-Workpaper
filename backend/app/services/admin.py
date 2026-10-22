"""Administrative maintenance of the workpaper layer. The imported baseline is never touched."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Adjustment,
    AiResponse,
    Assignment,
    Comment,
    Document,
    DocumentPage,
    FilingRecord,
    Finding,
    FirmSetting,
    Notification,
    PacketImport,
    ReplayState,
    ReviewNote,
    Signoff,
    TimeEntry,
    UserSeen,
    Verification,
    WorkpaperArea,
    WorkpaperRevision,
)
from app.services import audit
from app.services.importer import seed_workpaper

# Child tables first so foreign keys are satisfied.
WORKPAPER_TABLES = [
    Notification, UserSeen, AiResponse, TimeEntry, Signoff, Assignment, Comment, ReviewNote, Adjustment,
    Verification, Finding, WorkpaperRevision, FilingRecord, WorkpaperArea, FirmSetting, ReplayState,
]


def reset_workpaper(db: Session, actor_id: str | None = None, validate: bool = True) -> dict:
    """Delete all human work and re-seed configuration.

    The audit trail and sensitive-access log are append-only and survive a reset; the reset itself is audited.
    """
    pkt = db.scalar(select(PacketImport))
    if pkt is None:
        raise RuntimeError("No packet has been imported")
    removed: dict[str, int] = {}
    wp_docs = db.scalars(select(Document.id).where(Document.origin == "workpaper")).all()
    if wp_docs:
        db.execute(delete(DocumentPage).where(DocumentPage.document_id.in_(wp_docs)))
        db.execute(delete(Document).where(Document.id.in_(wp_docs)))
    removed["workpaper_documents"] = len(wp_docs)
    for model in WORKPAPER_TABLES:
        removed[model.__tablename__] = db.execute(delete(model)).rowcount or 0
    db.flush()
    seed_workpaper(db, pkt.raw)
    audit.record(db, actor=actor_id or "system", action="workpaper.reset", entity_type="workpaper",
                 entity_id="WP", summary="Workpaper reset to the imported baseline", after={"removed": removed})
    db.commit()
    result: dict = {"status": "reset", "removed": removed}
    if validate:
        from app.services.findings import run_validation

        result["validation"] = run_validation(db, actor_id=actor_id)
    return result

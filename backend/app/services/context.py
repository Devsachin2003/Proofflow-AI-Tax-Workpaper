"""Process-wide cache of the immutable packet index (keyed by the imported packet's sha256)."""

from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Document, DocumentPage, PacketImport, ReplayState
from app.services.packet_index import PacketIndex
from app.services.resolver import Resolver

_lock = Lock()
_cache: dict[str, PacketIndex] = {}


def get_index(db: Session) -> PacketIndex:
    sha = db.scalar(select(PacketImport.sha256))
    if not sha:
        raise AppError("No packet has been imported. Run `python -m app.cli import-packet`.", code="no_packet")
    with _lock:
        if sha not in _cache:
            raw = db.scalar(select(PacketImport.raw).where(PacketImport.sha256 == sha))
            _cache.clear()
            _cache[sha] = PacketIndex(raw)
        return _cache[sha]


def workpaper_documents(db: Session) -> dict[str, dict]:
    rows = db.scalars(select(Document).where(Document.origin == "workpaper")).all()
    return {d.id: {"id": d.id, "title": d.title, "page_count": d.page_count} for d in rows}


def get_resolver(db: Session) -> Resolver:
    return Resolver(get_index(db), workpaper_documents(db))


def replay_now(db: Session):
    state = db.get(ReplayState, 1)
    return state.now if state else None


def workpaper_page(db: Session, doc_id: str, page: int) -> str | None:
    p = db.get(DocumentPage, (doc_id, page))
    return p.printed_content if p else None

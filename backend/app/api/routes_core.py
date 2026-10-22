from fastapi import APIRouter, Depends
from sqlalchemy import select, text

from app.api.deps import CurrentUser, Session, get_current_user, get_db
from app.core.config import get_settings
from app.core.permissions import PERMISSIONS, matrix
from app.models import AppUser, PacketImport, ReplayState
from app.services.importer import baseline_counts
from app.services.revisions import active_base_version

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    imported = db.scalar(select(PacketImport.sha256)) is not None
    return {"status": "ok", "database": "ok", "packet_imported": imported}


@router.get("/api/meta")
def meta(db: Session = Depends(get_db)):
    imp = db.scalar(select(PacketImport))
    state = db.get(ReplayState, 1)
    return {
        "app": "ProofFlow AI",
        "packet": {"sha256": imp.sha256, "file_name": imp.file_name, "client_id": imp.client_id,
                   "imported_at": imp.imported_at, "name": imp.raw["packet"]["name"]} if imp else None,
        "counts": baseline_counts(db),
        "active_version": active_base_version(db) if imp else None,
        "replay_now": state.now if state else None,
        "llm_enabled": get_settings().llm_enabled,
        "demo_identity": True,
    }


@router.get("/api/users")
def users(db: Session = Depends(get_db)):
    rows = db.scalars(select(AppUser).order_by(AppUser.kind.desc(), AppUser.id)).all()
    return [
        {"id": u.id, "name": u.name, "role": u.role, "kind": u.kind, "credential": u.credential,
         "sensitive_clearance": u.sensitive_clearance, "active_from": u.active_from, "note": u.note}
        for u in rows
    ]


@router.get("/api/me")
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    state = db.get(ReplayState, 1)
    active = not (user.active_from and state and user.active_from > state.now.date())
    return {
        "id": user.id, "name": user.name, "role": user.role, "kind": user.kind,
        "sensitive_clearance": user.sensitive_clearance, "active_from": user.active_from,
        "active_on_replay_date": active,
        "permissions": sorted(a for a, roles in PERMISSIONS.items() if user.role in roles),
    }


@router.get("/api/permissions")
def permissions():
    return matrix()

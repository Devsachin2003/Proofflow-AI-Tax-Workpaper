from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, Notification, ReplayState


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def snapshot(obj, fields: list[str]) -> dict:
    return {f: _jsonable(getattr(obj, f)) for f in fields}


def record(
    db: Session,
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> AuditEvent:
    state = db.get(ReplayState, 1)
    ev = AuditEvent(
        actor_id=getattr(actor, "id", None),
        actor_role=getattr(actor, "role", None),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        summary=summary,
        before=_jsonable(before) if before else None,
        after=_jsonable(after) if after else None,
        reason=reason,
        simulated_at=state.now if state else None,
    )
    db.add(ev)
    db.flush()
    return ev


def notify(db: Session, user_ids: list[str | None], kind: str, title: str, body: str | None = None,
           link: str | None = None, exclude: str | None = None) -> None:
    for uid in {u for u in user_ids if u and u != exclude}:
        db.add(Notification(user_id=uid, kind=kind, title=title, body=body, link=link))

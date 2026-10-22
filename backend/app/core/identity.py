"""Demo identity.

The demo selects a seeded firm or client user with the `X-Demo-User` header. This is a clearly labelled
simulation for evaluators to experience role permissions; it is not authentication. In production this
dependency would be replaced by an identity provider (OIDC) mapping tokens to the same user records.
"""

from dataclasses import dataclass
from datetime import date

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden
from app.db.session import get_db
from app.models import AppUser


@dataclass(frozen=True)
class CurrentUser:
    id: str
    name: str
    role: str
    kind: str
    sensitive_clearance: bool
    active_from: date | None
    person_id: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.kind == "staff"


def get_current_user(
    x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
    db: Session = Depends(get_db),
) -> CurrentUser:
    settings = get_settings()
    if not settings.demo_identity_enabled:
        raise Forbidden("Demo identity is disabled and no identity provider is configured.")
    user_id = x_demo_user or settings.default_demo_user
    u = db.get(AppUser, user_id)
    if u is None:
        raise Forbidden(f"Unknown demo user '{user_id}'.", code="unknown_user")
    return CurrentUser(u.id, u.name, u.role, u.kind, u.sensitive_clearance, u.active_from, u.person_id)

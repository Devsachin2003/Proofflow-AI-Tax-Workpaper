"""Server-side permission matrix. Every mutating service call checks `require(user, action)`."""

from app.core.errors import Forbidden

STAFF_ROLES = {"preparer", "reviewer", "partner", "firm_administrator", "quality_reviewer"}
PREPARING_ROLES = {"preparer", "reviewer", "partner"}
REVIEWING_ROLES = {"reviewer", "partner"}

PERMISSIONS: dict[str, set[str]] = {
    "workpaper.view": STAFF_ROLES,
    "client.view": STAFF_ROLES | {"client"},
    "evidence.attach": PREPARING_ROLES | {"client"},
    "verification.create": PREPARING_ROLES,
    "finding.update": PREPARING_ROLES,
    "finding.false_positive": REVIEWING_ROLES,
    "finding.run_validation": PREPARING_ROLES | {"firm_administrator"},
    "adjustment.propose": PREPARING_ROLES,
    "adjustment.decide": REVIEWING_ROLES,
    "note.create": REVIEWING_ROLES | {"quality_reviewer"},
    "note.judgment": PREPARING_ROLES,
    "note.respond": PREPARING_ROLES,
    "note.clear": REVIEWING_ROLES | {"quality_reviewer"},
    "comment.create": STAFF_ROLES | {"client"},
    "client_question.create": PREPARING_ROLES,
    "assignment.manage": REVIEWING_ROLES | {"firm_administrator"},
    "area.update": PREPARING_ROLES,
    "signoff.preparer": {"preparer", "reviewer", "partner"},
    "signoff.reviewer": REVIEWING_ROLES,
    "signoff.partner": {"partner"},
    "signoff.client": {"client"},
    "filing.submit": {"partner", "reviewer"},
    "filing.amend": {"partner", "reviewer"},
    "revision.create": PREPARING_ROLES,
    "replay.control": STAFF_ROLES,
    "firm.settings.edit": {"firm_administrator"},
    "firm.access_logs.view": {"firm_administrator", "partner", "quality_reviewer"},
    "time.record": STAFF_ROLES,
    "admin.reset": {"firm_administrator"},
    "assistant.ask": STAFF_ROLES,
}


def can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, set())


def require(user, action: str) -> None:
    if not can(user.role, action):
        raise Forbidden(
            f"Role '{user.role}' is not permitted to perform '{action}'.",
            details={"action": action, "role": user.role},
            code="permission_denied",
        )


def matrix() -> dict[str, list[str]]:
    return {action: sorted(roles) for action, roles in PERMISSIONS.items()}

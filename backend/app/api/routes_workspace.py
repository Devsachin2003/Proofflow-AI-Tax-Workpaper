from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, Session, get_current_user, get_db, staff_user
from app.services import findings, overview
from app.services.revisions import list_revisions

router = APIRouter(prefix="/api")


@router.get("/overview")
def get_overview(db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return overview.overview(db)


@router.get("/household")
def get_household(db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return overview.household(db)


@router.get("/timeline")
def get_timeline(include_future: bool = False, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(staff_user)):
    return overview.timeline(db, include_future)


@router.get("/areas")
def get_areas(db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return overview.areas(db)


@router.get("/scenarios")
def get_scenarios(db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return overview.scenarios(db)


@router.get("/diagnostics")
def get_diagnostics(version: str | None = None, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(staff_user)):
    return overview.diagnostics(db, version)


@router.get("/findings")
def get_findings(status: str | None = Query(default=None), db: Session = Depends(get_db),
                 user: CurrentUser = Depends(staff_user)):
    return findings.list_findings(db, status)


@router.post("/validation/run")
def run_validation(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    from app.core.permissions import require

    require(user, "finding.run_validation")
    return findings.run_validation(db, actor_id=user.id)


@router.get("/findings/{finding_id}")
def get_finding(finding_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return findings.get_finding(db, finding_id)


class FindingDecision(BaseModel):
    status: str = Field(pattern="^(open|in_review|resolved|false_positive|accepted)$")
    note: str | None = Field(default=None, max_length=4000)
    expected_version: int | None = None


@router.patch("/findings/{finding_id}")
def decide_finding(finding_id: str, body: FindingDecision, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(get_current_user)):
    return findings.decide_finding(db, user, finding_id, body.status, body.note, body.expected_version)


@router.get("/revisions")
def get_revisions(db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return list_revisions(db)

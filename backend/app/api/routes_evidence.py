from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, Session, get_current_user, get_db, staff_user
from app.core.masking import mask_deep
from app.services import evidence, lineage
from app.services.context import get_resolver
from app.services.revisions import active_base_version

router = APIRouter(prefix="/api")


@router.get("/documents")
def list_documents(
    version: str | None = None, q: str | None = None, document_type: str | None = None,
    belongs_to: str | None = None, usage: str | None = None, extraction: str | None = None,
    corrected: bool | None = None, with_findings: bool | None = None, review: str | None = None,
    include_future: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user),
):
    return evidence.list_documents(db, version or active_base_version(db), q, document_type, belongs_to, usage,
                                   extraction, corrected, with_findings, review, include_future)


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, version: str | None = None, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(staff_user)):
    return evidence.document_detail(db, doc_id, version or active_base_version(db))


@router.get("/extracted-values/{ev_id}")
def get_value(ev_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return evidence.value_detail(db, ev_id)


class EvidenceIn(BaseModel):
    kind: str = Field(pattern="^(file|message|note)$")
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    file_name: str | None = Field(default=None, max_length=200)
    attached_to: str | None = Field(default=None, max_length=128)


@router.post("/evidence", status_code=201)
def attach(body: EvidenceIn, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return evidence.attach_evidence(db, user, kind=body.kind, title=body.title, content=body.content,
                                    file_name=body.file_name, attached_to=body.attached_to)


@router.get("/resolve")
def resolve(ref: str = Query(min_length=1, max_length=200), version: str | None = None,
            db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    res = get_resolver(db).resolve(ref, version or active_base_version(db))
    out = mask_deep(res.as_dict())
    if res.ref_type == "extracted_value" and res.resolved:
        out["detail"] = evidence.value_detail(db, ref)
    return out


@router.get("/versions")
def versions(db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return lineage.versions(db)


@router.get("/lines")
def list_lines(version: str | None = None, q: str | None = None, form: str | None = None,
               jurisdiction: str | None = None, include_lots: bool = False, area: str | None = None,
               limit: int = Query(200, le=1000), offset: int = 0, db: Session = Depends(get_db),
               user: CurrentUser = Depends(staff_user)):
    return lineage.list_lines(db, version or active_base_version(db), q, form, jurisdiction, include_lots, area,
                              limit, offset)


@router.get("/lines/{key}")
def line_detail(key: str, version: str | None = None, db: Session = Depends(get_db),
                user: CurrentUser = Depends(staff_user)):
    return lineage.line_detail(db, key, version or active_base_version(db))


@router.get("/compare")
def compare(a: str = "v1", b: str = "v3", changed_only: bool = True, q: str | None = None,
            db: Session = Depends(get_db), user: CurrentUser = Depends(staff_user)):
    return lineage.compare(db, a, b, changed_only, q)

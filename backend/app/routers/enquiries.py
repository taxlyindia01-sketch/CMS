"""
Enquiries Router - Lead Management API
Handles creation, status updates, and conversion of enquiries

FIXES:
- FIX A: list_enquiries now uses selectinload(Enquiry.ai_drafts) to prevent
         DetachedInstanceError when Pydantic serialises ai_drafts outside the
         lazy-load window.  Was causing "Request failed" on All Enquiries page.

- FIX B: convert_to_client now auto-seeds default workflow stages before
         creating WorkflowProgress records when no stages exist for the
         service type.  Was causing 0/0 · 0% progress in client modal.

- FIX C: convert_to_client now returns company_master_id = None (populated
         by list_clients) so ClientOut schema is consistent.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session, selectinload
from typing import List
from datetime import datetime, timezone

from app.database import get_db, SessionLocal
from app.models.models import (
    Enquiry, AIDraft, Client, WorkflowTemplate,
    WorkflowProgress, EnquiryStatus, ServiceType,
)
from app.schemas.schemas import EnquiryCreate, EnquiryOut, EnquiryUpdate, ClientOut
from app.services.gemini_service import (
    generate_thank_you_letter,
    generate_document_checklist,
    generate_price_quotation,
)
from app.services.utils import generate_client_id, assign_staff_by_workload
from app.services.auth_service import require_auth

router = APIRouter()


# ─── Default workflow stages (mirrors workflows.py seed logic) ────────────────
_DEFAULT_STAGES = {
    ServiceType.COMPANY_INCORPORATION: [
        (1, "Name Approval",       "Apply for company name approval with MCA"),
        (2, "Document Collection", "Collect KYC and incorporation documents"),
        (3, "DSC Generation",      "Digital Signature Certificate for all directors"),
        (4, "DIN Application",     "Director Identification Number for new directors"),
        (5, "MOA/AOA Drafting",    "Draft Memorandum and Articles of Association"),
        (6, "Filing with MCA",     "Submit SPICe+ form on MCA portal"),
        (7, "Certificate Issued",  "Certificate of Incorporation received"),
    ],
    ServiceType.GST_REGISTRATION: [
        (1, "Document Collection", "Collect GST registration documents"),
        (2, "Application Filing",  "File GST registration application"),
        (3, "ARN Generated",       "Application Reference Number received"),
        (4, "GSTIN Issued",        "GST Identification Number issued"),
    ],
    ServiceType.OTHER: [
        (1, "Requirements Gathering", "Understand client requirements"),
        (2, "Processing",             "Processing the service request"),
        (3, "Completion",             "Service completed and delivered"),
    ],
}


def _ensure_workflow_stages(service_type: ServiceType, db: Session) -> None:
    """
    FIX B: Auto-seed default workflow stages for a service type if none exist.
    Called during enquiry → client conversion so that WorkflowProgress records
    are always created.  Idempotent — skips stages that already exist.
    """
    existing = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.service_type == service_type,
        WorkflowTemplate.is_active == True,
    ).first()

    if existing:
        return  # Already has stages, nothing to do

    stages = _DEFAULT_STAGES.get(service_type, _DEFAULT_STAGES[ServiceType.OTHER])
    for order, name, desc in stages:
        db.add(WorkflowTemplate(
            service_type=service_type,
            stage_order=order,
            stage_name=name,
            description=desc,
        ))
    db.commit()


# ─── Background AI draft generation ───────────────────────────────────────────

async def generate_ai_drafts(enquiry_id: int, enquiry_data: dict):
    """Background task: generate all 3 AI drafts after enquiry submission.
    Creates its own DB session — the request session is closed before this runs.
    """
    db = SessionLocal()
    try:
        drafts = [
            ("thank_you_letter",   generate_thank_you_letter),
            ("document_checklist", generate_document_checklist),
            ("price_quotation",    generate_price_quotation),
        ]
        for draft_type, generator in drafts:
            content = await generator(enquiry_data)
            db.add(AIDraft(enquiry_id=enquiry_id, draft_type=draft_type, content=content))
        db.commit()
    except Exception as e:
        print(f"AI draft generation failed: {e}")
    finally:
        db.close()


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=EnquiryOut, status_code=201)
async def create_enquiry(
    request: Request,
    data: EnquiryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new enquiry and trigger AI draft generation in background"""
    require_auth(request, db)
    enquiry = Enquiry(**data.model_dump())
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)

    background_tasks.add_task(
        generate_ai_drafts,
        enquiry.id,
        data.model_dump(mode="json"),
    )

    # Load ai_drafts eagerly so Pydantic can serialise (empty list at this point)
    db.refresh(enquiry)
    _ = enquiry.ai_drafts
    return enquiry


@router.get("/", response_model=List[EnquiryOut])
def list_enquiries(
    request: Request,
    status: str = None,
    db: Session = Depends(get_db),
):
    """
    List all enquiries, optionally filtered by status.

    FIX A: Uses selectinload(Enquiry.ai_drafts) so that the ai_drafts
    collection is fetched in a single IN-query rather than N lazy queries.
    This eliminates DetachedInstanceError when Pydantic serialises after the
    primary query finishes — which was the root cause of "Request failed".
    """
    require_auth(request, db)
    query = db.query(Enquiry).options(selectinload(Enquiry.ai_drafts))

    if status:
        valid_statuses = [e.value for e in EnquiryStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {valid_statuses}",
            )
        query = query.filter(Enquiry.status == status)

    return query.order_by(Enquiry.created_at.desc()).all()


@router.get("/{enquiry_id}", response_model=EnquiryOut)
def get_enquiry(enquiry_id: int, request: Request, db: Session = Depends(get_db)):
    """Get a single enquiry by ID"""
    require_auth(request, db)
    enquiry = (
        db.query(Enquiry)
        .options(selectinload(Enquiry.ai_drafts))
        .filter(Enquiry.id == enquiry_id)
        .first()
    )
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    return enquiry


@router.patch("/{enquiry_id}/status")
def update_enquiry_status(
    enquiry_id: int,
    data: EnquiryUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update enquiry status (Pending / Closed)"""
    require_auth(request, db)
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    if data.status:
        enquiry.status = data.status
        if data.status == EnquiryStatus.CLOSED:
            enquiry.closed_at = datetime.now(timezone.utc)

    if data.assigned_staff_id is not None:
        enquiry.assigned_staff_id = data.assigned_staff_id

    db.commit()
    db.refresh(enquiry)
    return {"message": "Status updated", "status": enquiry.status}


@router.post("/{enquiry_id}/convert", response_model=ClientOut)
def convert_to_client(
    enquiry_id: int,
    request: Request,
    staff_id: int = None,          # optional manual override
    db: Session = Depends(get_db),
):
    """
    Convert a Pending enquiry to a Client.
    - Generates unique Client ID
    - Auto-assigns staff by workload (or uses staff_id query param)
    - FIX B: Auto-seeds workflow stages if none exist for the service type
    - Creates WorkflowProgress records for each stage
    """
    require_auth(request, db)
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    if enquiry.status == EnquiryStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Enquiry already converted")

    if enquiry.status == EnquiryStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot convert a closed enquiry")

    # Resolve staff: manual override > enquiry assignment > auto-assign by workload
    resolved_staff_id = (
        staff_id
        or enquiry.assigned_staff_id
        or assign_staff_by_workload(db)
    )

    # Create client record
    client = Client(
        client_id=generate_client_id(db),
        enquiry_id=enquiry.id,
        company_name=enquiry.proposed_company_name,
        contact_name=enquiry.contact_name,
        contact_email=enquiry.contact_email,
        contact_phone=enquiry.contact_phone,
        assigned_staff_id=resolved_staff_id,
        service_type=enquiry.service_type,
    )
    db.add(client)

    enquiry.status = EnquiryStatus.CONVERTED
    enquiry.assigned_staff_id = resolved_staff_id

    db.commit()
    db.refresh(client)

    # FIX B: ensure workflow stages exist BEFORE creating progress records
    _ensure_workflow_stages(enquiry.service_type, db)

    stages = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.service_type == enquiry.service_type,
            WorkflowTemplate.is_active == True,
        )
        .order_by(WorkflowTemplate.stage_order)
        .all()
    )

    for stage in stages:
        db.add(WorkflowProgress(
            client_id=client.id,
            template_stage_id=stage.id,
            is_completed=False,
        ))

    db.commit()
    db.refresh(client)

    # Build response manually to include company_master_id (None at convert time)
    out = ClientOut.model_validate(client)
    out.company_master_id = None
    return out

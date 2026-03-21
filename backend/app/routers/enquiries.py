"""
Enquiries Router - Lead Management API
Handles creation, status updates, and conversion of enquiries
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.database import get_db, SessionLocal
from app.models.models import Enquiry, AIDraft, Client, WorkflowTemplate, WorkflowProgress, EnquiryStatus
from app.schemas.schemas import EnquiryCreate, EnquiryOut, EnquiryUpdate, ClientOut
from app.services.gemini_service import (
    generate_thank_you_letter,
    generate_document_checklist,
    generate_price_quotation
)
from app.services.utils import generate_client_id, assign_staff_by_workload
from app.services.auth_service import require_auth

router = APIRouter()


async def generate_ai_drafts(enquiry_id: int, enquiry_data: dict):
    """Background task: generate all 3 AI drafts after enquiry submission.
    Creates its own DB session — the request session is closed before this runs.
    """
    db = SessionLocal()
    try:
        drafts = [
            ("thank_you_letter", generate_thank_you_letter),
            ("document_checklist", generate_document_checklist),
            ("price_quotation", generate_price_quotation),
        ]
        for draft_type, generator in drafts:
            content = await generator(enquiry_data)
            draft = AIDraft(
                enquiry_id=enquiry_id,
                draft_type=draft_type,
                content=content
            )
            db.add(draft)
        db.commit()
    except Exception as e:
        print(f"AI draft generation failed: {e}")
    finally:
        db.close()


@router.post("/", response_model=EnquiryOut, status_code=201)
async def create_enquiry(
    request: Request,
    data: EnquiryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new enquiry and trigger AI draft generation in background"""
    require_auth(request, db)
    enquiry = Enquiry(**data.model_dump())
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)

    # Trigger AI drafts in background (non-blocking)
    # FIX #11: model_dump() returns Decimal objects which are not JSON-serializable.
    # mode='json' converts Decimal→str, date→str, etc. for safe background task passing.
    background_tasks.add_task(
        generate_ai_drafts,
        enquiry.id,
        data.model_dump(mode='json')
    )

    return enquiry


@router.get("/", response_model=List[EnquiryOut])
def list_enquiries(
    request: Request,
    status: str = None,
    db: Session = Depends(get_db)
):
    """List all enquiries, optionally filtered by status"""
    require_auth(request, db)
    query = db.query(Enquiry)
    if status:
        # FIX #24: Validate status against known enum values before filtering
        # Prevents arbitrary string injection into ORM filter
        valid_statuses = [e.value for e in EnquiryStatus]
        if status not in valid_statuses:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Invalid status. Valid values: {valid_statuses}")
        query = query.filter(Enquiry.status == status)
    return query.order_by(Enquiry.created_at.desc()).all()


@router.get("/{enquiry_id}", response_model=EnquiryOut)
def get_enquiry(enquiry_id: int, request: Request, db: Session = Depends(get_db)):
    """Get a single enquiry by ID"""
    require_auth(request, db)
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    return enquiry


@router.patch("/{enquiry_id}/status")
def update_enquiry_status(
    enquiry_id: int,
    data: EnquiryUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update enquiry status (Pending / Closed)"""
    require_auth(request, db)
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    if data.status:
        enquiry.status = data.status
        if data.status == EnquiryStatus.CLOSED:
            enquiry.closed_at = datetime.now(timezone.utc)  # FIX #10: was utcnow() (naive/deprecated)

    if data.assigned_staff_id is not None:
        enquiry.assigned_staff_id = data.assigned_staff_id

    db.commit()
    db.refresh(enquiry)
    return {"message": "Status updated", "status": enquiry.status}


@router.post("/{enquiry_id}/convert", response_model=ClientOut)
def convert_to_client(
    enquiry_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Convert a Pending enquiry to a Client.
    - Generates unique Client ID
    - Auto-assigns staff by workload
    - Creates workflow progress records
    """
    require_auth(request, db)
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    if enquiry.status == EnquiryStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Enquiry already converted")

    if enquiry.status == EnquiryStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot convert a closed enquiry")

    # Assign staff by workload
    staff_id = enquiry.assigned_staff_id or assign_staff_by_workload(db)

    # Create client
    client = Client(
        client_id=generate_client_id(db),
        enquiry_id=enquiry.id,
        company_name=enquiry.proposed_company_name,
        contact_name=enquiry.contact_name,
        contact_email=enquiry.contact_email,
        contact_phone=enquiry.contact_phone,
        assigned_staff_id=staff_id,
        service_type=enquiry.service_type,
    )
    db.add(client)

    # Update enquiry status
    enquiry.status = EnquiryStatus.CONVERTED
    enquiry.assigned_staff_id = staff_id

    db.commit()
    db.refresh(client)

    # Create workflow progress records for each template stage
    stages = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.service_type == enquiry.service_type,
        WorkflowTemplate.is_active == True
    ).order_by(WorkflowTemplate.stage_order).all()

    for stage in stages:
        progress = WorkflowProgress(
            client_id=client.id,
            template_stage_id=stage.id,
            is_completed=False
        )
        db.add(progress)

    db.commit()
    return client

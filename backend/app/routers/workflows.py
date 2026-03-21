"""
Workflows Router - Configurable workflow stages for settings page
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import WorkflowTemplate, ServiceType
from app.schemas.schemas import WorkflowTemplateCreate, WorkflowTemplateOut
from app.services.auth_service import require_auth

router = APIRouter()


@router.post("/", response_model=WorkflowTemplateOut, status_code=201)
def create_workflow_stage(request: Request, data: WorkflowTemplateCreate, db: Session = Depends(get_db)):
    """Add a workflow stage to a service type"""
    require_auth(request, db)
    stage = WorkflowTemplate(**data.model_dump())
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


@router.get("/", response_model=List[WorkflowTemplateOut])
def list_workflow_stages(
    request: Request,
    service_type: str = None,
    db: Session = Depends(get_db)
):
    """List all workflow stages, optionally filtered by service type"""
    require_auth(request, db)
    query = db.query(WorkflowTemplate).filter(WorkflowTemplate.is_active == True)
    if service_type:
        query = query.filter(WorkflowTemplate.service_type == service_type)
    return query.order_by(WorkflowTemplate.service_type, WorkflowTemplate.stage_order).all()


@router.delete("/{stage_id}")
def delete_workflow_stage(stage_id: int, request: Request, db: Session = Depends(get_db)):
    """Deactivate a workflow stage"""
    require_auth(request, db)
    stage = db.query(WorkflowTemplate).filter(WorkflowTemplate.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    stage.is_active = False
    db.commit()
    return {"message": "Stage removed"}


@router.post("/seed-defaults")
def seed_default_workflows(request: Request, db: Session = Depends(get_db)):
    """
    Seed default workflow stages for Company Incorporation and GST Registration.
    Run once during initial setup.
    """
    require_auth(request, db)
    defaults = [
        # Company Incorporation
        ("Company Incorporation", ServiceType.COMPANY_INCORPORATION, 1, "Name Approval", "Apply for company name approval with MCA"),
        ("Company Incorporation", ServiceType.COMPANY_INCORPORATION, 2, "Document Collection", "Collect KYC and incorporation documents"),
        ("Company Incorporation", ServiceType.COMPANY_INCORPORATION, 3, "DSC Generation", "Digital Signature Certificate for all directors"),
        ("Company Incorporation", ServiceType.COMPANY_INCORPORATION, 4, "DIN Application", "Director Identification Number for new directors"),
        ("Company Incorporation", ServiceType.COMPANY_INCORPORATION, 5, "MOA/AOA Drafting", "Draft Memorandum and Articles of Association"),
        ("Company Incorporation", ServiceType.COMPANY_INCORPORATION, 6, "Filing with MCA", "Submit SPICe+ form on MCA portal"),
        ("Company Incorporation", ServiceType.COMPANY_INCORPORATION, 7, "Certificate Issued", "Certificate of Incorporation received"),

        # GST Registration
        ("GST Registration", ServiceType.GST_REGISTRATION, 1, "Document Collection", "Collect GST registration documents"),
        ("GST Registration", ServiceType.GST_REGISTRATION, 2, "Application Filing", "File GST registration application"),
        ("GST Registration", ServiceType.GST_REGISTRATION, 3, "ARN Generated", "Application Reference Number received"),
        ("GST Registration", ServiceType.GST_REGISTRATION, 4, "GSTIN Issued", "GST Identification Number issued"),
    ]

    added = 0
    for _, service_type, order, name, desc in defaults:
        exists = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.service_type == service_type,
            WorkflowTemplate.stage_name == name
        ).first()
        if not exists:
            db.add(WorkflowTemplate(
                service_type=service_type,
                stage_order=order,
                stage_name=name,
                description=desc
            ))
            added += 1

    db.commit()
    return {"message": f"Seeded {added} default workflow stages"}

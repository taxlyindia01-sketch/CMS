"""
Clients Router
Handles client profile and workflow tracking
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import Client, WorkflowProgress, WorkflowTemplate
from sqlalchemy.orm import joinedload
from app.schemas.schemas import ClientOut, WorkflowProgressOut
from app.services.auth_service import require_auth

router = APIRouter()


@router.get("/", response_model=List[ClientOut])
def list_clients(request: Request, db: Session = Depends(get_db)):
    """List all active clients"""
    require_auth(request, db)
    return db.query(Client).filter(Client.is_active == True).order_by(Client.created_at.desc()).all()


@router.get("/{client_id_str}")
def get_client_by_client_id(client_id_str: str, db: Session = Depends(get_db)):
    """
    Get client profile by Client ID (e.g., CA-2024-001).
    Used for the client-facing tracking portal.
    """
    client = db.query(Client).filter(Client.client_id == client_id_str).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Build workflow progress
    # FIX #13: Added joinedload(WorkflowProgress.template_stage) to avoid N+1 query
    # Each .template_stage access was a separate SELECT — now one JOIN query
    progress = (
        db.query(WorkflowProgress)
        .options(joinedload(WorkflowProgress.template_stage))
        .filter(WorkflowProgress.client_id == client.id)
        .all()
    )

    stages = []
    for p in sorted(progress, key=lambda x: x.template_stage.stage_order):
        stages.append({
            "stage_name": p.template_stage.stage_name,
            "stage_order": p.template_stage.stage_order,
            "is_completed": p.is_completed,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        })

    current_stage = next((s["stage_name"] for s in stages if not s["is_completed"]), "Completed")

    return {
        "client_id": client.client_id,
        "company_name": client.company_name,
        "contact_name": client.contact_name,
        "service_type": client.service_type,
        "current_milestone": current_stage,
        "staff_name": client.assigned_staff.name if client.assigned_staff else None,
        "staff_email": client.assigned_staff.email if client.assigned_staff else None,
        "staff_phone": client.assigned_staff.phone if client.assigned_staff else None,
        "workflow": stages,
        "created_at": client.created_at.isoformat(),
    }


@router.patch("/{client_db_id}/workflow/{stage_id}")
def update_workflow_stage(
    client_db_id: int,
    stage_id: int,
    is_completed: bool,
    request: Request,
    notes: str = None,
    db: Session = Depends(get_db)
):
    """Mark a workflow stage as completed or pending"""
    require_auth(request, db)
    from datetime import datetime, timezone
    progress = db.query(WorkflowProgress).filter(
        WorkflowProgress.client_id == client_db_id,
        WorkflowProgress.template_stage_id == stage_id
    ).first()

    if not progress:
        raise HTTPException(status_code=404, detail="Stage not found")

    progress.is_completed = is_completed
    progress.completed_at = datetime.now(timezone.utc) if is_completed else None  # FIX #12: was utcnow()
    if notes:
        progress.notes = notes

    db.commit()
    return {"message": "Stage updated"}

"""
Staff Router - Manage CA firm staff members
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import Staff
from app.schemas.schemas import StaffCreate, StaffOut
from app.services.auth_service import require_auth

router = APIRouter()


@router.post("/", response_model=StaffOut, status_code=201)
def create_staff(request: Request, data: StaffCreate, db: Session = Depends(get_db)):
    """Add a new staff member"""
    require_auth(request, db)
    existing = db.query(Staff).filter(Staff.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    staff = Staff(**data.model_dump())
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.get("/", response_model=List[StaffOut])
def list_staff(request: Request, db: Session = Depends(get_db)):
    """List all active staff"""
    require_auth(request, db)
    members = db.query(Staff).filter(Staff.is_active == True).all()
    result = []
    for m in members:
        item = StaffOut.model_validate(m)
        item.active_client_count = len([c for c in m.clients if c.is_active])
        result.append(item)
    return result


@router.delete("/{staff_id}")
def deactivate_staff(staff_id: int, request: Request, db: Session = Depends(get_db)):
    """Deactivate (soft delete) a staff member"""
    require_auth(request, db)
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    staff.is_active = False
    db.commit()
    return {"message": "Staff deactivated"}

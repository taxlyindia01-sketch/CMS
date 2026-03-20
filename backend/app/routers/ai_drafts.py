"""
AI Drafts Router - View and regenerate AI-generated documents
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.auth_service import require_auth
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import AIDraft, Enquiry
from app.schemas.schemas import AIDraftOut
from app.services.gemini_service import (
    generate_thank_you_letter,
    generate_document_checklist,
    generate_price_quotation
)

router = APIRouter()


@router.get("/drafts/{enquiry_id}", response_model=List[AIDraftOut])
def get_drafts(enquiry_id: int, request: Request, db: Session = Depends(get_db)):
    """Get all AI drafts for an enquiry"""
    require_auth(request, db)
    drafts = db.query(AIDraft).filter(AIDraft.enquiry_id == enquiry_id).all()
    return drafts


@router.post("/drafts/{enquiry_id}/regenerate")
async def regenerate_drafts(enquiry_id: int, request: Request, db: Session = Depends(get_db)):
    """Regenerate all AI drafts for an enquiry"""
    require_auth(request, db)
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    # Delete existing drafts
    db.query(AIDraft).filter(AIDraft.enquiry_id == enquiry_id).delete()
    db.commit()

    enquiry_data = {
        "proposed_company_name": enquiry.proposed_company_name,
        "contact_name": enquiry.contact_name,
        "director_names": enquiry.director_names or [],
        "shareholder_names": enquiry.shareholder_names or [],
        "authorised_capital": str(enquiry.authorised_capital or ""),
    }

    generators = [
        ("thank_you_letter", generate_thank_you_letter),
        ("document_checklist", generate_document_checklist),
        ("price_quotation", generate_price_quotation),
    ]

    for draft_type, fn in generators:
        content = await fn(enquiry_data)
        db.add(AIDraft(enquiry_id=enquiry_id, draft_type=draft_type, content=content))

    db.commit()
    return {"message": "Drafts regenerated successfully"}

"""
Company Master Router — Module 2
Handles CompanyMaster profile and all sub-entities:
  Directors, Shareholders, Share Transfers, Charges
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.auth_service import require_auth
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import (
    CompanyMaster, Director, Shareholder,
    ShareTransfer, Charge, Client
)
from app.schemas.company_schemas import (
    CompanyMasterCreate, CompanyMasterUpdate, CompanyMasterOut,
    DirectorCreate, DirectorUpdate, DirectorOut,
    ShareholderCreate, ShareholderUpdate, ShareholderOut,
    ShareTransferCreate, ShareTransferOut,
    ChargeCreate, ChargeOut,
)

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# COMPANY MASTER
# ═══════════════════════════════════════════════════════════

def _get_company_or_404(company_id: int, db: Session) -> CompanyMaster:
    company = db.query(CompanyMaster).filter(CompanyMaster.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company master record not found")
    return company


@router.post("/client/{client_db_id}", response_model=CompanyMasterOut, status_code=201)
def create_company_master(
    client_db_id: int,
    data: CompanyMasterCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create (or initialise) a Company Master record for a converted client.
    Only one master record allowed per client.
    """
    require_auth(request, db)
    client = db.query(Client).filter(Client.id == client_db_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    existing = db.query(CompanyMaster).filter(CompanyMaster.client_id == client_db_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company master already exists for this client. Use PATCH to update.")

    company = CompanyMaster(**data.model_dump(), client_id=client_db_id)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/client/{client_db_id}", response_model=CompanyMasterOut)
def get_company_by_client(client_db_id: int, request: Request, db: Session = Depends(get_db)):
    """Get the company master record for a given client DB id."""
    require_auth(request, db)
    company = db.query(CompanyMaster).filter(CompanyMaster.client_id == client_db_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="No company master record yet. Create one first.")
    return company


@router.get("/cin/{cin}", response_model=CompanyMasterOut)
def get_company_by_cin(cin: str, request: Request, db: Session = Depends(get_db)):
    """Lookup company by CIN."""
    require_auth(request, db)
    company = db.query(CompanyMaster).filter(CompanyMaster.cin == cin).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/", response_model=List[CompanyMasterOut])
def list_companies(request: Request, db: Session = Depends(get_db)):
    """List all company master records."""
    require_auth(request, db)
    return db.query(CompanyMaster).order_by(CompanyMaster.created_at.desc()).all()


@router.patch("/{company_id}", response_model=CompanyMasterOut)
def update_company_master(
    company_id: int,
    data: CompanyMasterUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update any fields of a Company Master record."""
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(company, k, v)
    db.commit()
    db.refresh(company)
    return company


# ═══════════════════════════════════════════════════════════
# DIRECTORS
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/directors", response_model=DirectorOut, status_code=201)
def add_director(company_id: int, data: DirectorCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    director = Director(**data.model_dump(), company_id=company_id)
    db.add(director)
    db.commit()
    db.refresh(director)
    return director


@router.get("/{company_id}/directors", response_model=List[DirectorOut])
def list_directors(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    return db.query(Director).filter(Director.company_id == company_id).all()


@router.patch("/{company_id}/directors/{director_id}", response_model=DirectorOut)
def update_director(
    company_id: int,
    director_id: int,
    data: DirectorUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    director = db.query(Director).filter(
        Director.id == director_id,
        Director.company_id == company_id
    ).first()
    if not director:
        raise HTTPException(status_code=404, detail="Director not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(director, k, v)
    db.commit()
    db.refresh(director)
    return director


@router.delete("/{company_id}/directors/{director_id}")
def delete_director(company_id: int, director_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    director = db.query(Director).filter(
        Director.id == director_id, Director.company_id == company_id
    ).first()
    if not director:
        raise HTTPException(status_code=404, detail="Director not found")
    db.delete(director)
    db.commit()
    return {"message": "Director removed"}


# ═══════════════════════════════════════════════════════════
# SHAREHOLDERS
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/shareholders", response_model=ShareholderOut, status_code=201)
def add_shareholder(company_id: int, data: ShareholderCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    shareholder = Shareholder(**data.model_dump(), company_id=company_id)
    db.add(shareholder)
    db.commit()
    db.refresh(shareholder)
    return shareholder


@router.get("/{company_id}/shareholders", response_model=List[ShareholderOut])
def list_shareholders(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    return db.query(Shareholder).filter(Shareholder.company_id == company_id).all()


@router.patch("/{company_id}/shareholders/{shareholder_id}", response_model=ShareholderOut)
def update_shareholder(
    company_id: int,
    shareholder_id: int,
    data: ShareholderUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    sh = db.query(Shareholder).filter(
        Shareholder.id == shareholder_id, Shareholder.company_id == company_id
    ).first()
    if not sh:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(sh, k, v)
    db.commit()
    db.refresh(sh)
    return sh


@router.delete("/{company_id}/shareholders/{shareholder_id}")
def delete_shareholder(company_id: int, shareholder_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    sh = db.query(Shareholder).filter(
        Shareholder.id == shareholder_id, Shareholder.company_id == company_id
    ).first()
    if not sh:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    db.delete(sh)
    db.commit()
    return {"message": "Shareholder removed"}


# ═══════════════════════════════════════════════════════════
# SHARE TRANSFERS
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/transfers", response_model=ShareTransferOut, status_code=201)
def add_share_transfer(company_id: int, data: ShareTransferCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    transfer = ShareTransfer(**data.model_dump(), company_id=company_id)
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return transfer


@router.get("/{company_id}/transfers", response_model=List[ShareTransferOut])
def list_share_transfers(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    return db.query(ShareTransfer).filter(
        ShareTransfer.company_id == company_id
    ).order_by(ShareTransfer.transfer_date.desc()).all()


# ═══════════════════════════════════════════════════════════
# CHARGES
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/charges", response_model=ChargeOut, status_code=201)
def add_charge(company_id: int, data: ChargeCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    charge = Charge(**data.model_dump(), company_id=company_id)
    db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge


@router.get("/{company_id}/charges", response_model=List[ChargeOut])
def list_charges(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    return db.query(Charge).filter(Charge.company_id == company_id).all()


@router.patch("/{company_id}/charges/{charge_id}", response_model=ChargeOut)
def update_charge(
    company_id: int,
    charge_id: int,
    data: ChargeCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    charge = db.query(Charge).filter(
        Charge.id == charge_id, Charge.company_id == company_id
    ).first()
    if not charge:
        raise HTTPException(status_code=404, detail="Charge not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(charge, k, v)
    db.commit()
    db.refresh(charge)
    return charge


# ═══════════════════════════════════════════════════════════
# FULL COMPANY PROFILE (combined view)
# ═══════════════════════════════════════════════════════════

@router.get("/{company_id}/full-profile")
def get_full_profile(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    """
    Returns complete company profile including directors,
    shareholders, charges and transfer history.
    Used by the Company Master detail page.
    """
    company = _get_company_or_404(company_id, db)

    def director_dict(d: Director):
        return {
            "id": d.id, "full_name": d.full_name, "din": d.din,
            "pan": d.pan, "designation": d.designation,
            "date_of_appointment": d.date_of_appointment.isoformat() if d.date_of_appointment else None,
            "date_of_cessation": d.date_of_cessation.isoformat() if d.date_of_cessation else None,
            "is_active": d.is_active, "email": d.email, "phone": d.phone,
            "residential_address": d.residential_address, "city": d.city,
            "state": d.state, "nationality": d.nationality,
            "shareholding_ratio": float(d.shareholding_ratio or 0),
            "number_of_shares": d.number_of_shares,
            "folio_number": d.folio_number,
            "dsc_expiry_date": d.dsc_expiry_date.isoformat() if d.dsc_expiry_date else None,
        }

    def shareholder_dict(s: Shareholder):
        return {
            "id": s.id, "full_name": s.full_name, "shareholder_type": s.shareholder_type,
            "pan": s.pan, "email": s.email, "phone": s.phone,
            "address": s.address, "city": s.city, "state": s.state,
            "folio_number": s.folio_number,
            "number_of_shares": s.number_of_shares,
            "shareholding_ratio": float(s.shareholding_ratio or 0),
            "date_of_allotment": s.date_of_allotment.isoformat() if s.date_of_allotment else None,
            "class_of_shares": s.class_of_shares,
        }

    return {
        "company": {
            "id": company.id,
            "client_id": company.client_id,
            "cin": company.cin,
            "company_name": company.company_name,
            "company_type": company.company_type,
            "roc": company.roc,
            "registered_office_address": company.registered_office_address,
            "corporate_office_address": company.corporate_office_address,
            "city": company.city, "state": company.state, "pincode": company.pincode,
            "email": company.email, "phone": company.phone, "website": company.website,
            "authorised_capital": float(company.authorised_capital or 0),
            "paidup_capital": float(company.paidup_capital or 0),
            "face_value_per_share": float(company.face_value_per_share or 10),
            "total_shares": company.total_shares,
            "date_of_incorporation": company.date_of_incorporation.isoformat() if company.date_of_incorporation else None,
            "financial_year_end": company.financial_year_end,
            "last_agm_date": company.last_agm_date.isoformat() if company.last_agm_date else None,
            "last_agm_financial_year": company.last_agm_financial_year,
            "last_ar_filed_date": company.last_ar_filed_date.isoformat() if company.last_ar_filed_date else None,
            "last_bs_filed_date": company.last_bs_filed_date.isoformat() if company.last_bs_filed_date else None,
            "bank_name": company.bank_name, "bank_account_number": company.bank_account_number,
            "bank_branch": company.bank_branch, "bank_ifsc": company.bank_ifsc,
            "pan": company.pan, "tan": company.tan, "gstin": company.gstin,
            "msme_number": company.msme_number, "import_export_code": company.import_export_code,
        },
        "directors": [director_dict(d) for d in company.directors],
        "shareholders": [shareholder_dict(s) for s in company.shareholders],
        "charges": [
            {
                "id": c.id, "charge_holder": c.charge_holder,
                "charge_amount": float(c.charge_amount or 0),
                "date_of_creation": c.date_of_creation.isoformat() if c.date_of_creation else None,
                "date_of_satisfaction": c.date_of_satisfaction.isoformat() if c.date_of_satisfaction else None,
                "status": c.status, "property_charged": c.property_charged,
            }
            for c in company.charges
        ],
        "share_transfers": [
            {
                "id": t.id, "from_name": t.from_name, "to_name": t.to_name,
                "number_of_shares": t.number_of_shares,
                "transfer_date": t.transfer_date.isoformat() if t.transfer_date else None,
                "transfer_price_per_share": float(t.transfer_price_per_share or 0),
                "transfer_deed_number": t.transfer_deed_number,
            }
            for t in company.share_transfers
        ],
    }

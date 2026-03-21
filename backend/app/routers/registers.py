"""
Module 4 — Statutory Registers Router
Endpoints:
  GET  /{company_id}/registers/members/pdf
  GET  /{company_id}/registers/members/excel
  GET  /{company_id}/registers/directors/pdf
  GET  /{company_id}/registers/directors/excel
  GET  /{company_id}/registers/charges/pdf
  GET  /{company_id}/registers/charges/excel
  GET  /{company_id}/registers/transfers/pdf
  GET  /{company_id}/registers/transfers/excel
  GET  /{company_id}/registers/all/excel       (combined workbook)
  GET  /{company_id}/registers/preview         (JSON data for UI preview)
  GET  /{company_id}/registers/missing-info    (detect missing fields)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.auth_service import require_auth
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Any, Dict, List

from app.database import get_db
from app.models.models import (
    CompanyMaster, Director, Shareholder,
    ShareTransfer, Charge
)
from app.services.register_generator import (
    generate_members_pdf,
    generate_directors_pdf,
    generate_charges_pdf,
    generate_transfers_pdf,
    generate_members_excel,
    generate_directors_excel,
    generate_charges_excel,
    generate_transfers_excel,
    generate_all_registers_excel,
)

router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_company_or_404(company_id: int, db: Session) -> CompanyMaster:
    c = db.query(CompanyMaster).filter(CompanyMaster.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


def _build_company_dict(c: CompanyMaster) -> Dict:
    return {
        "company_name": c.company_name,
        "cin": c.cin,
        "registered_office_address": c.registered_office_address,
        "date_of_incorporation": c.date_of_incorporation.isoformat() if c.date_of_incorporation else None,
        "paidup_capital": float(c.paidup_capital or 0),
        "authorised_capital": float(c.authorised_capital or 0),
        "company_type": c.company_type,
        "roc": c.roc,
        "pan": c.pan,
        "gstin": c.gstin,
    }


def _build_directors(company_id: int, db: Session) -> List[Dict]:
    dirs = db.query(Director).filter(Director.company_id == company_id).all()
    return [
        {
            "id": d.id,
            "full_name": d.full_name,
            "din": d.din,
            "designation": d.designation,
            "pan": d.pan,
            "aadhaar": d.aadhaar,
            "date_of_appointment": d.date_of_appointment.isoformat() if d.date_of_appointment else None,
            "date_of_cessation": d.date_of_cessation.isoformat() if d.date_of_cessation else None,
            "is_active": d.is_active,
            "email": d.email,
            "phone": d.phone,
            "residential_address": d.residential_address,
            "city": d.city,
            "state": d.state,
            "pincode": d.pincode,
            "nationality": d.nationality,
            "shareholding_ratio": float(d.shareholding_ratio or 0),
            "number_of_shares": d.number_of_shares,
            "folio_number": d.folio_number,
            "dsc_expiry_date": d.dsc_expiry_date.isoformat() if d.dsc_expiry_date else None,
        }
        for d in dirs
    ]


def _build_shareholders(company_id: int, db: Session) -> List[Dict]:
    shs = db.query(Shareholder).filter(Shareholder.company_id == company_id).all()
    return [
        {
            "id": s.id,
            "full_name": s.full_name,
            "shareholder_type": s.shareholder_type,
            "pan": s.pan,
            "aadhaar": s.aadhaar,
            "email": s.email,
            "phone": s.phone,
            "address": s.address,
            "city": s.city,
            "state": s.state,
            "pincode": s.pincode,
            "nationality": s.nationality,
            "folio_number": s.folio_number,
            "number_of_shares": s.number_of_shares,
            "shareholding_ratio": float(s.shareholding_ratio or 0),
            "date_of_allotment": s.date_of_allotment.isoformat() if s.date_of_allotment else None,
            "class_of_shares": s.class_of_shares,
        }
        for s in shs
    ]


def _build_charges(company_id: int, db: Session) -> List[Dict]:
    charges = db.query(Charge).filter(Charge.company_id == company_id).all()
    return [
        {
            "id": c.id,
            "charge_id": c.charge_id,
            "charge_holder": c.charge_holder,
            "charge_amount": float(c.charge_amount or 0),
            "date_of_creation": c.date_of_creation.isoformat() if c.date_of_creation else None,
            "date_of_satisfaction": c.date_of_satisfaction.isoformat() if c.date_of_satisfaction else None,
            "property_charged": c.property_charged,
            "status": c.status,
            "remarks": c.remarks,
        }
        for c in charges
    ]


def _build_transfers(company_id: int, db: Session) -> List[Dict]:
    transfers = db.query(ShareTransfer).filter(
        ShareTransfer.company_id == company_id
    ).order_by(ShareTransfer.transfer_date).all()
    return [
        {
            "id": t.id,
            "from_name": t.from_name,
            "to_name": t.to_name,
            "number_of_shares": t.number_of_shares,
            "transfer_price_per_share": float(t.transfer_price_per_share or 0),
            "transfer_date": t.transfer_date.isoformat() if t.transfer_date else None,
            "transfer_deed_number": t.transfer_deed_number,
            "consideration_amount": float(t.consideration_amount or 0),
            "remarks": t.remarks,
        }
        for t in transfers
    ]


def _check_missing_info(company: CompanyMaster, shareholders, directors, charges, transfers) -> Dict:
    """
    Detect what information is missing for each register.
    Returns dict of register_name -> list of missing fields.
    """
    missing = {
        "members": [],
        "directors": [],
        "charges": [],
        "transfers": [],
        "company": [],
    }

    # Company level
    if not company.cin:
        missing["company"].append("CIN (Corporate Identification Number)")
    if not company.registered_office_address:
        missing["company"].append("Registered Office Address")
    if not company.date_of_incorporation:
        missing["company"].append("Date of Incorporation")
    if not company.paidup_capital:
        missing["company"].append("Paid-up Capital")

    # Members register
    if not shareholders:
        missing["members"].append("No shareholders added — please add shareholders in Company Master")
    else:
        for s in shareholders:
            # Support both ORM objects and dicts
            folio = s["folio_number"] if isinstance(s, dict) else s.folio_number
            pan = s["pan"] if isinstance(s, dict) else s.pan
            doa = s["date_of_allotment"] if isinstance(s, dict) else s.date_of_allotment
            name = s["full_name"] if isinstance(s, dict) else s.full_name
            if not folio:
                missing["members"].append(f"Folio Number missing for: {name}")
            if not pan:
                missing["members"].append(f"PAN missing for: {name}")
            if not doa:
                missing["members"].append(f"Date of Allotment missing for: {name}")

    # Directors register
    if not directors:
        missing["directors"].append("No directors added — please add directors in Company Master")
    else:
        for d in directors:
            # Support both ORM objects and dicts
            din = d["din"] if isinstance(d, dict) else d.din
            doa = d["date_of_appointment"] if isinstance(d, dict) else d.date_of_appointment
            name = d["full_name"] if isinstance(d, dict) else d.full_name
            if not din:
                missing["directors"].append(f"DIN missing for: {name}")
            if not doa:
                missing["directors"].append(f"Date of Appointment missing for: {name}")

    return missing


# ─── Preview endpoint ──────────────────────────────────────────────────────────

@router.get("/{company_id}/registers/preview")
def get_registers_preview(company_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Return all register data as JSON for the UI preview table.
    Also returns missing_info to show popup if needed.
    """
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    shareholders = _build_shareholders(company_id, db)
    directors    = _build_directors(company_id, db)
    charges      = _build_charges(company_id, db)
    transfers    = _build_transfers(company_id, db)
    missing      = _check_missing_info(company, shareholders, directors, charges, transfers)

    return {
        "company": _build_company_dict(company),
        "shareholders": shareholders,
        "directors": directors,
        "charges": charges,
        "transfers": transfers,
        "missing_info": missing,
        "stats": {
            "total_shareholders": len(shareholders),
            "total_shares": sum(int(s.get("number_of_shares") or 0) for s in shareholders),
            "total_directors": len(directors),
            "active_directors": sum(1 for d in directors if d.get("is_active")),
            "total_charges": len(charges),
            "active_charges": sum(1 for c in charges if str(c.get("status","")).lower() == "active"),
            "total_transfers": len(transfers),
        }
    }


@router.get("/{company_id}/registers/missing-info")
def get_missing_info(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company      = _get_company_or_404(company_id, db)
    shareholders = db.query(Shareholder).filter(Shareholder.company_id == company_id).all()
    directors    = db.query(Director).filter(Director.company_id == company_id).all()
    charges      = db.query(Charge).filter(Charge.company_id == company_id).all()
    transfers    = db.query(ShareTransfer).filter(ShareTransfer.company_id == company_id).all()
    return _check_missing_info(company, shareholders, directors, charges, transfers)


# ─── PDF endpoints ─────────────────────────────────────────────────────────────

@router.get("/{company_id}/registers/members/pdf")
def download_members_pdf(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    pdf = generate_members_pdf(
        _build_company_dict(company),
        _build_shareholders(company_id, db)
    )
    filename = f"Register_of_Members_{company.company_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/registers/directors/pdf")
def download_directors_pdf(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    pdf = generate_directors_pdf(
        _build_company_dict(company),
        _build_directors(company_id, db)
    )
    filename = f"Register_of_Directors_{company.company_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/registers/charges/pdf")
def download_charges_pdf(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    pdf = generate_charges_pdf(
        _build_company_dict(company),
        _build_charges(company_id, db)
    )
    filename = f"Register_of_Charges_{company.company_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/registers/transfers/pdf")
def download_transfers_pdf(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    pdf = generate_transfers_pdf(
        _build_company_dict(company),
        _build_transfers(company_id, db)
    )
    filename = f"Register_of_ShareTransfers_{company.company_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ─── Excel endpoints ───────────────────────────────────────────────────────────

@router.get("/{company_id}/registers/members/excel")
def download_members_excel(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    xl = generate_members_excel(
        _build_company_dict(company),
        _build_shareholders(company_id, db)
    )
    filename = f"Register_of_Members_{company.company_name.replace(' ', '_')}.xlsx"
    return Response(
        content=xl,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/registers/directors/excel")
def download_directors_excel(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    xl = generate_directors_excel(
        _build_company_dict(company),
        _build_directors(company_id, db)
    )
    filename = f"Register_of_Directors_{company.company_name.replace(' ', '_')}.xlsx"
    return Response(
        content=xl,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/registers/charges/excel")
def download_charges_excel(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    xl = generate_charges_excel(
        _build_company_dict(company),
        _build_charges(company_id, db)
    )
    filename = f"Register_of_Charges_{company.company_name.replace(' ', '_')}.xlsx"
    return Response(
        content=xl,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{company_id}/registers/transfers/excel")
def download_transfers_excel(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    xl = generate_transfers_excel(
        _build_company_dict(company),
        _build_transfers(company_id, db)
    )
    filename = f"Register_of_ShareTransfers_{company.company_name.replace(' ', '_')}.xlsx"
    return Response(
        content=xl,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ─── Combined all-registers Excel ─────────────────────────────────────────────

@router.get("/{company_id}/registers/all/excel")
def download_all_registers_excel(company_id: int, request: Request, db: Session = Depends(get_db)):
    """Download all 4 registers in a single Excel workbook with cover sheet."""
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    xl = generate_all_registers_excel(
        _build_company_dict(company),
        _build_shareholders(company_id, db),
        _build_directors(company_id, db),
        _build_charges(company_id, db),
        _build_transfers(company_id, db),
    )
    filename = f"Statutory_Registers_{company.company_name.replace(' ', '_')}.xlsx"
    return Response(
        content=xl,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

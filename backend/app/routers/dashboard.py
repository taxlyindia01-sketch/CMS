"""
Dashboard Router
All HTML sub-page routes serve Index.html (the SPA reads the URL path to decide which view to show).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Client, Enquiry, EnquiryStatus, Staff
from app.services.auth_service import (
    get_session_user,
    get_token_from_request,
    require_auth,
)

router = APIRouter()

_SPA = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "Static" / "Index.html"


def _spa() -> FileResponse:
    return FileResponse(str(_SPA), media_type="text/html")


def _guard(request: Request, db: Session):
    """Return redirect to / if not authenticated, else None."""
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if not user:
        return RedirectResponse("/", status_code=302)
    return None


# ── Protected HTML sub-pages (all serve the SPA) ────────────────────────────

@router.get("/enquiries-page", response_class=HTMLResponse)
def enquiries_page(request: Request, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/new-enquiry", response_class=HTMLResponse)
def new_enquiry_page(request: Request, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/clients-page", response_class=HTMLResponse)
def clients_page(request: Request, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/company/{client_db_id}", response_class=HTMLResponse)
def company_page(request: Request, client_db_id: int, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/meetings/{company_id}", response_class=HTMLResponse)
def meetings_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/post-inc/{company_id}", response_class=HTMLResponse)
def post_inc_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/compliance/{company_id}", response_class=HTMLResponse)
def compliance_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/compliance-dashboard", response_class=HTMLResponse)
def compliance_dashboard_page(request: Request, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


@router.get("/registers/{company_id}", response_class=HTMLResponse)
def registers_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _guard(request, db) or _spa()


# ── Public: client tracking portal (no login required) ───────────────────────

@router.get("/track/{client_id_str}", response_class=HTMLResponse)
def track_page(client_id_str: str):
    return _spa()


# ── Dashboard stats API ───────────────────────────────────────────────────────

@router.get("/api/dashboard/stats")
def dashboard_stats(request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    total      = db.query(Enquiry).count()
    pending    = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.PENDING).count()
    converted  = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.CONVERTED).count()
    closed     = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.CLOSED).count()
    active_cl  = db.query(Client).filter(Client.is_active == True).count()
    staff_rows = db.query(Staff).filter(Staff.is_active == True).all()
    return {
        "total_enquiries":    total,
        "pending_enquiries":  pending,
        "converted_clients":  converted,
        "closed_enquiries":   closed,
        "active_registrations": active_cl,
        "staff_workload": [
            {"name": s.name, "designation": s.designation,
             "client_count": len([c for c in s.clients if c.is_active])}
            for s in staff_rows
        ],
    }

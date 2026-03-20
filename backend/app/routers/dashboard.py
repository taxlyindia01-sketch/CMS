"""
Dashboard Router — HTML page serving + stats API
All HTML routes serve Index.html (self-contained SPA).
The SPA reads company_id / client_id from window.location.pathname at runtime.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.models.models import Enquiry, Client, Staff, EnquiryStatus
from app.services.auth_service import get_token_from_request, get_session_user, require_auth

router = APIRouter()

# Path to the single SPA HTML file
_SPA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "Static" / "Index.html"


def _serve_spa() -> FileResponse:
    return FileResponse(str(_SPA_FILE), media_type="text/html")


def _redirect_if_unauth(request: Request, db: Session):
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if not user:
        return RedirectResponse("/", status_code=302)
    return None


# ── All HTML sub-pages serve the SPA — JS reads the URL to know which view to show ──

@router.get("/enquiries-page", response_class=HTMLResponse)
def enquiries_page(request: Request, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/new-enquiry", response_class=HTMLResponse)
def new_enquiry_page(request: Request, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/clients-page", response_class=HTMLResponse)
def clients_page(request: Request, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/company/{client_db_id}", response_class=HTMLResponse)
def company_master_page(request: Request, client_db_id: int, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/meetings/{company_id}", response_class=HTMLResponse)
def meetings_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/post-inc/{company_id}", response_class=HTMLResponse)
def post_inc_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/compliance/{company_id}", response_class=HTMLResponse)
def compliance_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/compliance-dashboard", response_class=HTMLResponse)
def compliance_dashboard_page(request: Request, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


@router.get("/registers/{company_id}", response_class=HTMLResponse)
def registers_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    return _redirect_if_unauth(request, db) or _serve_spa()


# ── Public tracking portal (no auth required) ─────────────────────────────────

@router.get("/track/{client_id_str}", response_class=HTMLResponse)
def track_page(request: Request, client_id_str: str):
    """Public client tracking portal — no login required."""
    return _serve_spa()


# ── Stats API ──────────────────────────────────────────────────────────────────

@router.get("/api/dashboard/stats")
def get_dashboard_stats(request: Request, db: Session = Depends(get_db)):
    """Return aggregated dashboard statistics — requires auth."""
    require_auth(request, db)

    total_enquiries = db.query(Enquiry).count()
    pending   = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.PENDING).count()
    converted = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.CONVERTED).count()
    closed    = db.query(Enquiry).filter(Enquiry.status == EnquiryStatus.CLOSED).count()
    active_clients = db.query(Client).filter(Client.is_active == True).count()

    staff_members = db.query(Staff).filter(Staff.is_active == True).all()
    staff_workload = [
        {
            "name": s.name,
            "designation": s.designation,
            "client_count": len([c for c in s.clients if c.is_active])
        }
        for s in staff_members
    ]

    return {
        "total_enquiries": total_enquiries,
        "pending_enquiries": pending,
        "converted_clients": converted,
        "closed_enquiries": closed,
        "active_registrations": active_clients,
        "staff_workload": staff_workload,
    }

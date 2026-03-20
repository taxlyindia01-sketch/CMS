"""
Dashboard Router — HTML page serving + stats API
Auth router owns: / /login /dashboard /change-password /admin/users
This router owns: all other HTML sub-pages + /api/dashboard/stats
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.models.models import Enquiry, Client, Staff, EnquiryStatus
from app.services.auth_service import get_token_from_request, get_session_user

router = APIRouter()
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _auth_check(request: Request, db: Session):
    """Return user or None. Used to pass user context to templates."""
    token = get_token_from_request(request)
    return get_session_user(token, db) if token else None


def _redirect_if_unauth(request: Request, db: Session):
    """Return RedirectResponse to /login if not authed, else None."""
    user = _auth_check(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return None


def _user_ctx(user) -> dict:
    """Build template context dict from user."""
    if not user:
        return {}
    return {
        "current_user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        }
    }


# ── Protected HTML pages ──────────────────────────────────────────────────────

@router.get("/enquiries-page", response_class=HTMLResponse)
def enquiries_page(request: Request, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("enquiries.html", {"request": request})


@router.get("/new-enquiry", response_class=HTMLResponse)
def new_enquiry_page(request: Request, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("new_enquiry.html", {"request": request})


@router.get("/clients-page", response_class=HTMLResponse)
def clients_page(request: Request, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("clients.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/company/{client_db_id}", response_class=HTMLResponse)
def company_master_page(request: Request, client_db_id: int, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("company_master.html", {"request": request, "client_db_id": client_db_id})


@router.get("/meetings/{company_id}", response_class=HTMLResponse)
def meetings_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("meetings.html", {"request": request, "company_id": company_id})


@router.get("/post-inc/{company_id}", response_class=HTMLResponse)
def post_inc_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("post_inc_alerts.html", {"request": request, "company_id": company_id})


@router.get("/compliance/{company_id}", response_class=HTMLResponse)
def compliance_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("compliance.html", {"request": request, "company_id": company_id})


@router.get("/compliance-dashboard", response_class=HTMLResponse)
def compliance_dashboard_page(request: Request, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("compliance_dashboard.html", {"request": request})


@router.get("/registers/{company_id}", response_class=HTMLResponse)
def registers_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    redir = _redirect_if_unauth(request, db)
    if redir:
        return redir
    return templates.TemplateResponse("registers.html", {"request": request, "company_id": company_id})


# ── Public page (no auth required) ───────────────────────────────────────────
@router.get("/track/{client_id_str}", response_class=HTMLResponse)
def track_page(request: Request, client_id_str: str):
    """Public client tracking portal — no login required."""
    return templates.TemplateResponse("track.html", {"request": request, "client_id": client_id_str})


# ── Stats API ─────────────────────────────────────────────────────────────────
@router.get("/api/dashboard/stats")
def get_dashboard_stats(request: Request, db: Session = Depends(get_db)):
    """Return aggregated dashboard statistics — requires auth."""
    from app.services.auth_service import require_auth
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

"""
Meetings & Post-Incorporation Alerts Router — Module 2B
Handles Board Meetings, AGM, EGM records, Resolutions, Minutes, and Post-Inc Alerts
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.auth_service import require_auth, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import date, timedelta

from app.database import get_db
from app.models.models import (
    Meeting, Resolution, PostIncorporationAlert,
    CompanyMaster, MeetingType, AlertType, AlertStatus
)
from app.schemas.meeting_schemas import (
    MeetingCreate, MeetingUpdate, MeetingOut,
    ResolutionCreate, ResolutionOut,
    AlertCreate, AlertUpdate, AlertOut,
    AIGenerateMeetingRequest
)
from app.services.meeting_ai_service import (
    generate_board_meeting_notice,
    generate_agm_notice,
    generate_egm_notice,
    generate_meeting_minutes,
    generate_resolution_draft,
    generate_inc20a_draft,
    generate_adt1_draft,
    generate_first_board_meeting_draft,
    generate_statutory_meeting_reminder,
)

router = APIRouter()


def _get_company_or_404(company_id: int, db: Session) -> CompanyMaster:
    c = db.query(CompanyMaster).filter(CompanyMaster.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


def company_dict(c: CompanyMaster) -> dict:
    return {
        "company_name": c.company_name,
        "cin": c.cin,
        "registered_office_address": c.registered_office_address,
        "date_of_incorporation": c.date_of_incorporation.isoformat() if c.date_of_incorporation else None,
        "paidup_capital": float(c.paidup_capital or 0),
        "last_agm_financial_year": c.last_agm_financial_year,
    }




# ═══════════════════════════════════════════════════════════
# DASHBOARD — all alerts across all companies
# ═══════════════════════════════════════════════════════════

@router.get("/alerts/dashboard")
def all_alerts_dashboard(request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    """
    Return all pending/overdue alerts across all companies — for compliance dashboard.
    """
    from datetime import datetime
    today = date.today()

    alerts = db.query(PostIncorporationAlert).filter(
        PostIncorporationAlert.status.in_([AlertStatus.PENDING, AlertStatus.IN_PROGRESS, AlertStatus.OVERDUE])
    ).all()

    result = []
    for a in alerts:
        company = db.query(CompanyMaster).filter(CompanyMaster.id == a.company_id).first()
        is_overdue = a.due_date and a.due_date < today and a.status != AlertStatus.COMPLETED
        if is_overdue and a.status != AlertStatus.OVERDUE:
            a.status = AlertStatus.OVERDUE
            db.commit()
        result.append({
            "id": a.id,
            "company_id": a.company_id,
            "company_name": company.company_name if company else "Unknown",
            "alert_type": a.alert_type,
            "title": a.title,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "status": a.status,
            "is_overdue": is_overdue,
            "days_remaining": (a.due_date - today).days if a.due_date else None,
        })

    result.sort(key=lambda x: (x["due_date"] or "9999-12-31"))
    return result



# ═══════════════════════════════════════════════════════════
# MEETINGS
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/meetings", response_model=MeetingOut, status_code=201)
def create_meeting(company_id: int, data: MeetingCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    """Create a new meeting record."""
    _get_company_or_404(company_id, db)
    meeting = Meeting(**data.model_dump(), company_id=company_id)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.get("/{company_id}/meetings", response_model=List[MeetingOut])
def list_meetings(
    company_id: int,
    request: Request,
    meeting_type: str = None,
    db: Session = Depends(get_db)
):
    """List all meetings for a company, optionally filtered by type."""
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    query = db.query(Meeting).filter(Meeting.company_id == company_id)
    if meeting_type:
        query = query.filter(Meeting.meeting_type == meeting_type)
    return query.order_by(Meeting.meeting_date.desc()).all()


@router.get("/{company_id}/meetings/{meeting_id}", response_model=MeetingOut)
def get_meeting(company_id: int, meeting_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id, Meeting.company_id == company_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.patch("/{company_id}/meetings/{meeting_id}", response_model=MeetingOut)
def update_meeting(
    company_id: int,
    meeting_id: int,
    data: MeetingUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id, Meeting.company_id == company_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(meeting, k, v)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.delete("/{company_id}/meetings/{meeting_id}")
def delete_meeting(company_id: int, meeting_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id, Meeting.company_id == company_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    db.delete(meeting)
    db.commit()
    return {"message": "Meeting deleted"}


# ── AI Generation for Meetings ─────────────────────────────

@router.post("/{company_id}/meetings/{meeting_id}/generate-ai")
async def generate_meeting_ai_docs(
    company_id: int,
    meeting_id: int,
    req: AIGenerateMeetingRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    """
    Generate AI drafts for meeting notice and/or minutes.
    Stores results directly on the Meeting record.
    """
    company = _get_company_or_404(company_id, db)
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id, Meeting.company_id == company_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    co = company_dict(company)
    m = {
        "meeting_type": meeting.meeting_type,
        "meeting_number": meeting.meeting_number,
        "meeting_date": meeting.meeting_date.isoformat() if meeting.meeting_date else None,
        "meeting_time": meeting.meeting_time,
        "venue": meeting.venue,
        "agenda_items": meeting.agenda_items or [],
        "chairman": meeting.chairman,
        "quorum_required": meeting.quorum_required,
        "quorum_present": meeting.quorum_present,
        "notice_period_days": meeting.notice_period_days,
        "attendees": meeting.attendees or [],
    }

    from datetime import datetime as dt

    # Generate Notice
    if req.generate_notice:
        if meeting.meeting_type == MeetingType.AGM:
            meeting.ai_notice_draft = await generate_agm_notice(m, co)
        elif meeting.meeting_type == MeetingType.EGM:
            meeting.ai_notice_draft = await generate_egm_notice(m, co)
        else:
            meeting.ai_notice_draft = await generate_board_meeting_notice(m, co)

    # Generate Minutes
    if req.generate_minutes:
        resolution_subjects = req.resolution_subjects or []
        meeting.ai_minutes_draft = await generate_meeting_minutes(m, co, resolution_subjects)

    # Generate Individual Resolution Drafts
    if req.generate_resolutions and req.resolution_subjects:
        for subject in req.resolution_subjects:
            res_type = "Board Resolution" if meeting.meeting_type == MeetingType.BOARD else "Ordinary Resolution"
            draft = await generate_resolution_draft(subject, res_type, co)
            # Check if resolution with this subject already exists
            existing = db.query(Resolution).filter(
                Resolution.meeting_id == meeting_id,
                Resolution.subject == subject
            ).first()
            if existing:
                existing.ai_draft_text = draft
            else:
                db.add(Resolution(
                    meeting_id=meeting_id,
                    subject=subject,
                    ai_draft_text=draft,
                    resolution_type="Board Resolution" if meeting.meeting_type == MeetingType.BOARD else "Ordinary Resolution"
                ))

    meeting.ai_generated_at = dt.utcnow()
    db.commit()
    db.refresh(meeting)
    return {
        "message": "AI documents generated successfully",
        "has_notice": bool(meeting.ai_notice_draft),
        "has_minutes": bool(meeting.ai_minutes_draft),
    }


# ═══════════════════════════════════════════════════════════
# RESOLUTIONS
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/meetings/{meeting_id}/resolutions", response_model=ResolutionOut, status_code=201)
def add_resolution(
    company_id: int,
    meeting_id: int,
    data: ResolutionCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id, Meeting.company_id == company_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    res = Resolution(**data.model_dump(), meeting_id=meeting_id)
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


@router.post("/{company_id}/meetings/{meeting_id}/resolutions/{resolution_id}/generate-ai")
async def generate_single_resolution(
    company_id: int,
    meeting_id: int,
    resolution_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    """Generate AI draft for a specific resolution."""
    company = _get_company_or_404(company_id, db)
    res = db.query(Resolution).filter(
        Resolution.id == resolution_id,
        Resolution.meeting_id == meeting_id
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resolution not found")
    co = company_dict(company)
    draft = await generate_resolution_draft(res.subject, res.resolution_type, co)
    res.ai_draft_text = draft
    db.commit()
    return {"message": "Resolution draft generated", "draft": draft}


@router.patch("/{company_id}/meetings/{meeting_id}/resolutions/{resolution_id}", response_model=ResolutionOut)
def update_resolution(
    company_id: int,
    meeting_id: int,
    resolution_id: int,
    data: ResolutionCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    res = db.query(Resolution).filter(
        Resolution.id == resolution_id,
        Resolution.meeting_id == meeting_id
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resolution not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(res, k, v)
    db.commit()
    db.refresh(res)
    return res


@router.delete("/{company_id}/meetings/{meeting_id}/resolutions/{resolution_id}")
def delete_resolution(company_id: int, meeting_id: int, resolution_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    res = db.query(Resolution).filter(
        Resolution.id == resolution_id, Resolution.meeting_id == meeting_id
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resolution not found")
    db.delete(res)
    db.commit()
    return {"message": "Resolution deleted"}


# ═══════════════════════════════════════════════════════════
# POST-INCORPORATION ALERTS
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/alerts", response_model=AlertOut, status_code=201)
def create_alert(company_id: int, data: AlertCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    alert = PostIncorporationAlert(**data.model_dump(), company_id=company_id)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/{company_id}/alerts", response_model=List[AlertOut])
def list_alerts(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    return db.query(PostIncorporationAlert).filter(
        PostIncorporationAlert.company_id == company_id
    ).order_by(PostIncorporationAlert.due_date).all()


@router.patch("/{company_id}/alerts/{alert_id}", response_model=AlertOut)
def update_alert(
    company_id: int,
    alert_id: int,
    data: AlertUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    alert = db.query(PostIncorporationAlert).filter(
        PostIncorporationAlert.id == alert_id,
        PostIncorporationAlert.company_id == company_id
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(alert, k, v)
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{company_id}/alerts/{alert_id}/generate-ai")
async def generate_alert_ai_draft(
    company_id: int,
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    """Generate AI draft document for a specific post-incorporation alert."""
    company = _get_company_or_404(company_id, db)
    alert = db.query(PostIncorporationAlert).filter(
        PostIncorporationAlert.id == alert_id,
        PostIncorporationAlert.company_id == company_id
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    co = company_dict(company)
    from datetime import datetime as dt

    if alert.alert_type == AlertType.INC_20A:
        draft = await generate_inc20a_draft(co)
    elif alert.alert_type == AlertType.ADT_1:
        draft = await generate_adt1_draft(co)
    elif alert.alert_type == AlertType.FIRST_BOARD_MEETING:
        draft = await generate_first_board_meeting_draft(co)
    else:
        draft = await generate_statutory_meeting_reminder(alert.alert_type, co)

    alert.ai_draft = draft
    alert.ai_generated_at = dt.utcnow()
    db.commit()
    return {"message": "AI draft generated", "draft": draft}


@router.post("/{company_id}/alerts/seed-post-inc")
def seed_post_incorporation_alerts(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    """
    Auto-seed all mandatory post-incorporation compliance alerts
    based on the company's date of incorporation.
    """
    company = _get_company_or_404(company_id, db)
    inc_date = company.date_of_incorporation or date.today()

    alerts_config = [
        {
            "alert_type": AlertType.FIRST_BOARD_MEETING,
            "title": "First Board Meeting",
            "description": "The first Board Meeting must be held within 30 days of incorporation to appoint auditors, open bank accounts, and transact mandatory business.",
            "due_date": inc_date + timedelta(days=30),
            "statutory_deadline": "Within 30 days of date of incorporation",
            "penalty_info": "₹25,000 penalty for company; ₹5,000 for each officer in default per day of default",
            "form_number": "MBP-1 / SS-1",
            "mca_link": "https://www.mca.gov.in",
        },
        {
            "alert_type": AlertType.ADT_1,
            "title": "Appointment of First Auditor (ADT-1)",
            "description": "Board must appoint the first statutory auditor within 30 days. If Board fails, members must appoint within 90 days at EGM. File ADT-1 within 15 days of appointment.",
            "due_date": inc_date + timedelta(days=30),
            "statutory_deadline": "Board: within 30 days | Members: within 90 days",
            "penalty_info": "₹300/day for late filing of ADT-1 (max ₹12,000)",
            "form_number": "ADT-1",
            "mca_link": "https://www.mca.gov.in/content/mca/global/en/mca/e-filing/company-forms-download.html",
        },
        {
            "alert_type": AlertType.INC_20A,
            "title": "INC-20A — Commencement of Business Declaration",
            "description": "Company cannot commence business or exercise borrowing powers without filing INC-20A. Each subscriber must deposit subscription money in company bank account first.",
            "due_date": inc_date + timedelta(days=180),
            "statutory_deadline": "Within 180 days of date of incorporation",
            "penalty_info": "₹50,000 for company + ₹1,000/day for each officer in default. Company may be struck off.",
            "form_number": "INC-20A",
            "mca_link": "https://www.mca.gov.in/content/mca/global/en/mca/e-filing/company-forms-download.html",
        },
        {
            "alert_type": AlertType.SHARE_CERTIFICATE,
            "title": "Issue Share Certificates to Subscribers",
            "description": "Share certificates must be issued to all subscribers within 2 months of incorporation and within 2 months of allotment of shares.",
            "due_date": inc_date + timedelta(days=60),
            "statutory_deadline": "Within 2 months of date of incorporation",
            "penalty_info": "₹25,000 penalty for company; ₹5,000 for each officer in default",
            "form_number": "SH-1",
            "mca_link": "https://www.mca.gov.in",
        },
        {
            "alert_type": AlertType.REGISTERED_OFFICE,
            "title": "Verify & Display Registered Office (INC-22)",
            "description": "Company must have a registered office within 30 days and must display company name and CIN at registered office and all correspondence. File INC-22 if office not declared at incorporation.",
            "due_date": inc_date + timedelta(days=30),
            "statutory_deadline": "Within 30 days of incorporation",
            "penalty_info": "₹1,000/day default continuing (max ₹1,00,000)",
            "form_number": "INC-22",
            "mca_link": "https://www.mca.gov.in",
        },
        {
            "alert_type": AlertType.STATUTORY_AUDIT,
            "title": "Statutory Audit — Year End",
            "description": "Ensure statutory audit is conducted for the first financial year. Auditor must submit audit report before AGM.",
            "due_date": date(inc_date.year + 1, 9, 30),  # Typically within 6 months of FY end
            "statutory_deadline": "Before Annual General Meeting",
            "penalty_info": "Non-compliance affects AGM and annual filing obligations",
            "form_number": "—",
            "mca_link": "https://www.mca.gov.in",
        },
    ]

    added = 0
    for cfg in alerts_config:
        exists = db.query(PostIncorporationAlert).filter(
            PostIncorporationAlert.company_id == company_id,
            PostIncorporationAlert.alert_type == cfg["alert_type"]
        ).first()
        if not exists:
            db.add(PostIncorporationAlert(**cfg, company_id=company_id))
            added += 1

    db.commit()
    return {"message": f"Seeded {added} post-incorporation compliance alerts"}


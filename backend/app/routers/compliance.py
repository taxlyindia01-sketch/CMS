"""
Module 3 — Compliance Reminder System + Auditor Management Router
Handles:
  - Annual/periodic compliance reminders (MGT-7, AOC-4, AGM, DIR-3 KYC, DPT-3, MSME-1 etc.)
  - Auditor record keeping + 5-year renewal alerts
  - ADT-3 (resignation) draft in single click
  - AI-generated checklists, board resolutions, reminder emails
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.auth_service import require_auth
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from typing import List
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from app.database import get_db
from app.models.models import (
    ComplianceReminder, Auditor, CompanyMaster,
    ComplianceStatus, AuditorStatus, ComplianceCategory, ReminderFrequency
)
from app.schemas.compliance_schemas import (
    ComplianceReminderCreate, ComplianceReminderUpdate, ComplianceReminderOut,
    AuditorCreate, AuditorCessation, AuditorOut,
    ComplianceDashboardItem,
)
from app.services.compliance_ai_service import (
    generate_compliance_checklist,
    generate_compliance_board_resolution,
    generate_compliance_reminder_email,
    generate_auditor_reappointment_resolution,
    generate_adt3_resignation_draft,
    generate_auditor_renewal_alert_letter,
    generate_specific_compliance_draft,
)

router = APIRouter()


def _get_company_or_404(company_id: int, db: Session) -> CompanyMaster:
    c = db.query(CompanyMaster).filter(CompanyMaster.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


def _company_dict(c: CompanyMaster) -> dict:
    return {
        "company_name": c.company_name,
        "cin": c.cin,
        "date_of_incorporation": c.date_of_incorporation.isoformat() if c.date_of_incorporation else None,
        "financial_year_end": c.financial_year_end,
    }


def _refresh_statuses(db: Session, company_id: int):
    """Auto-update UPCOMING → DUE_SOON → OVERDUE based on current date."""
    today = date.today()
    soon = today + timedelta(days=30)
    reminders = db.query(ComplianceReminder).filter(
        ComplianceReminder.company_id == company_id,
        ComplianceReminder.status != ComplianceStatus.COMPLETED,
        ComplianceReminder.status != ComplianceStatus.NOT_APPLICABLE,
    ).all()
    for r in reminders:
        if r.due_date < today:
            r.status = ComplianceStatus.OVERDUE
        elif r.due_date <= soon:
            r.status = ComplianceStatus.DUE_SOON
        else:
            r.status = ComplianceStatus.UPCOMING
    db.commit()


# ═══════════════════════════════════════════════════════════
# GLOBAL COMPLIANCE DASHBOARD (across all companies)
# ═══════════════════════════════════════════════════════════

@router.get("/dashboard/all-reminders")
def global_compliance_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Aggregated view of all compliance reminders across all companies.
    Sorted by urgency (overdue first, then due soonest).
    Used on the main compliance dashboard page.
    """
    require_auth(request, db)
    today = date.today()

    # Auto-refresh all statuses
    all_reminders = db.query(ComplianceReminder).filter(
        ComplianceReminder.status != ComplianceStatus.COMPLETED,
        ComplianceReminder.status != ComplianceStatus.NOT_APPLICABLE,
    ).all()
    for r in all_reminders:
        soon = today + timedelta(days=30)
        if r.due_date < today:
            r.status = ComplianceStatus.OVERDUE
        elif r.due_date <= soon:
            r.status = ComplianceStatus.DUE_SOON
    db.commit()

    reminders = db.query(ComplianceReminder).filter(
        ComplianceReminder.status.in_([
            ComplianceStatus.OVERDUE, ComplianceStatus.DUE_SOON, ComplianceStatus.UPCOMING
        ])
    ).order_by(ComplianceReminder.due_date).all()

    result = []
    for r in reminders:
        company = db.query(CompanyMaster).filter(CompanyMaster.id == r.company_id).first()
        days_rem = (r.due_date - today).days if r.due_date else None
        result.append({
            "id": r.id,
            "company_id": r.company_id,
            "company_name": company.company_name if company else "Unknown",
            "compliance_name": r.compliance_name,
            "form_number": r.form_number,
            "category": r.category,
            "financial_year": r.financial_year,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "status": r.status,
            "days_remaining": days_rem,
            "is_overdue": r.due_date < today if r.due_date else False,
        })

    return result


@router.get("/dashboard/auditor-renewals")
def auditor_renewal_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    All auditors whose 5-year term renewal is due within 180 days.
    """
    require_auth(request, db)
    today = date.today()
    alert_window = today + timedelta(days=180)

    auditors = db.query(Auditor).filter(
        Auditor.is_current == True,
        Auditor.status == AuditorStatus.ACTIVE,
        Auditor.renewal_due_date <= alert_window,
    ).all()

    result = []
    for a in auditors:
        company = db.query(CompanyMaster).filter(CompanyMaster.id == a.company_id).first()
        days_to_renewal = (a.renewal_due_date - today).days if a.renewal_due_date else None
        result.append({
            "auditor_id": a.id,
            "company_id": a.company_id,
            "company_name": company.company_name if company else "Unknown",
            "firm_name": a.firm_name,
            "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
            "renewal_due_date": a.renewal_due_date.isoformat() if a.renewal_due_date else None,
            "days_to_renewal": days_to_renewal,
            "urgent": days_to_renewal is not None and days_to_renewal <= 60,
        })

    result.sort(key=lambda x: (x["days_to_renewal"] or 9999))
    return result

# ═══════════════════════════════════════════════════════════
# COMPLIANCE REMINDERS — CRUD
# ═══════════════════════════════════════════════════════════

@router.post("/{company_id}/reminders", response_model=ComplianceReminderOut, status_code=201)
def create_reminder(company_id: int, data: ComplianceReminderCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    reminder = ComplianceReminder(**data.model_dump(), company_id=company_id)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/{company_id}/reminders", response_model=List[ComplianceReminderOut])
def list_reminders(
    company_id: int,
    request: Request,
    category: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    _refresh_statuses(db, company_id)
    query = db.query(ComplianceReminder).filter(ComplianceReminder.company_id == company_id)
    if category:
        query = query.filter(ComplianceReminder.category == category)
    if status:
        query = query.filter(ComplianceReminder.status == status)
    return query.order_by(ComplianceReminder.due_date).all()


@router.patch("/{company_id}/reminders/{reminder_id}", response_model=ComplianceReminderOut)
def update_reminder(
    company_id: int,
    reminder_id: int,
    data: ComplianceReminderUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    require_auth(request, db)
    r = db.query(ComplianceReminder).filter(
        ComplianceReminder.id == reminder_id,
        ComplianceReminder.company_id == company_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{company_id}/reminders/{reminder_id}")
def delete_reminder(company_id: int, reminder_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    r = db.query(ComplianceReminder).filter(
        ComplianceReminder.id == reminder_id,
        ComplianceReminder.company_id == company_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(r)
    db.commit()
    return {"message": "Reminder deleted"}


# ── AI Draft Generation for Reminders ─────────────────────

@router.post("/{company_id}/reminders/{reminder_id}/generate-ai")
async def generate_reminder_ai(
    company_id: int,
    reminder_id: int,
    request: Request,
    doc_type: str = "all",   # "checklist" | "resolution" | "email" | "all"
    db: Session = Depends(get_db)
):
    """
    Generate AI documents for a compliance reminder.
    doc_type: 'checklist', 'resolution', 'email', or 'all'
    """
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    r = db.query(ComplianceReminder).filter(
        ComplianceReminder.id == reminder_id,
        ComplianceReminder.company_id == company_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")

    today = date.today()
    days_rem = (r.due_date - today).days if r.due_date else None

    co = _company_dict(company)
    rem = {
        "compliance_name": r.compliance_name,
        "form_number": r.form_number,
        "financial_year": r.financial_year,
        "due_date": r.due_date.isoformat() if r.due_date else None,
        "statutory_deadline": r.statutory_deadline,
        "penalty_info": r.penalty_info,
        "days_remaining": days_rem,
    }

    from datetime import datetime as dt

    # Try form-specific prompt first
    if doc_type in ("checklist", "all") and r.form_number:
        if r.form_number in ["MGT-7", "AOC-4", "DIR-3 KYC", "MSME-1", "DPT-3", "MGT-14"]:
            combined = await generate_specific_compliance_draft(r.form_number, co)
            r.ai_checklist = combined
            r.ai_board_resolution = combined
        else:
            if doc_type in ("checklist", "all"):
                r.ai_checklist = await generate_compliance_checklist(rem, co)
            if doc_type in ("resolution", "all"):
                r.ai_board_resolution = await generate_compliance_board_resolution(rem, co)
    else:
        if doc_type in ("checklist", "all"):
            r.ai_checklist = await generate_compliance_checklist(rem, co)
        if doc_type in ("resolution", "all"):
            r.ai_board_resolution = await generate_compliance_board_resolution(rem, co)

    if doc_type in ("email", "all"):
        r.ai_reminder_email = await generate_compliance_reminder_email(rem, co)

    r.ai_generated_at = dt.utcnow()
    db.commit()
    return {
        "message": "AI documents generated",
        "has_checklist": bool(r.ai_checklist),
        "has_resolution": bool(r.ai_board_resolution),
        "has_email": bool(r.ai_reminder_email),
    }


# ── Seed Default Compliance Calendar ──────────────────────

@router.post("/{company_id}/reminders/seed-calendar")
def seed_compliance_calendar(
    company_id: int,
    request: Request,
    financial_year: str = None,
    db: Session = Depends(get_db)
):
    """
    Auto-generate all standard annual compliance reminders for a company.
    Based on Companies Act 2013 standard due dates.
    """
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)

    # Determine FY
    today = date.today()
    fy_start_year = today.year if today.month >= 4 else today.year - 1
    fy = financial_year or f"{fy_start_year}-{str(fy_start_year + 1)[2:]}"
    fy_end = date(fy_start_year + 1, 3, 31)

    # AGM: within 6 months of FY end = 30 Sep (for companies other than OPC)
    agm_date = date(fy_start_year + 1, 9, 30)
    # AOC-4: within 30 days of AGM
    aoc4_date = agm_date + timedelta(days=30)
    # MGT-7: within 60 days of AGM
    mgt7_date = agm_date + timedelta(days=60)

    defaults = [
        # ── Annual Filing ──────────────────────────────────────────────────────────
        dict(compliance_name="Annual General Meeting (AGM)", form_number="AGM",
             category=ComplianceCategory.AGM_RELATED, financial_year=fy,
             due_date=agm_date, frequency=ReminderFrequency.ANNUAL,
             statutory_deadline="Within 6 months from end of financial year (Sec 96)",
             penalty_info="₹1,00,000 for company + ₹5,000 per day for officers"),

        dict(compliance_name="Financial Statements Filing (AOC-4)", form_number="AOC-4",
             category=ComplianceCategory.ANNUAL_FILING, financial_year=fy,
             due_date=aoc4_date, frequency=ReminderFrequency.ANNUAL,
             statutory_deadline="Within 30 days of AGM (Sec 137)",
             penalty_info="₹10,000 + ₹100/day (max ₹2,00,000) for company; ₹10,000 + ₹100/day for officers",
             mca_link="https://www.mca.gov.in/content/mca/global/en/mca/e-filing/company-forms-download.html"),

        dict(compliance_name="Annual Return (MGT-7)", form_number="MGT-7",
             category=ComplianceCategory.ANNUAL_FILING, financial_year=fy,
             due_date=mgt7_date, frequency=ReminderFrequency.ANNUAL,
             statutory_deadline="Within 60 days of AGM (Sec 92)",
             penalty_info="₹50,000 + ₹100/day (max ₹5,00,000) for company; ₹50,000 + ₹100/day for CS/officer",
             mca_link="https://www.mca.gov.in/content/mca/global/en/mca/e-filing/company-forms-download.html"),

        # ── Director KYC ───────────────────────────────────────────────────────────
        dict(compliance_name="DIR-3 KYC — Director Annual KYC", form_number="DIR-3 KYC",
             category=ComplianceCategory.DIRECTOR_KYC,
             due_date=date(today.year, 9, 30), frequency=ReminderFrequency.ANNUAL,
             statutory_deadline="30 September every year",
             penalty_info="DIN marked as 'Deactivated' + ₹5,000 for reactivation",
             mca_link="https://www.mca.gov.in"),

        # ── Deposits ──────────────────────────────────────────────────────────────
        dict(compliance_name="DPT-3 — Return of Deposits / Outstanding Loans", form_number="DPT-3",
             category=ComplianceCategory.DEPOSIT_RELATED, financial_year=fy,
             due_date=date(fy_start_year + 1, 6, 30), frequency=ReminderFrequency.ANNUAL,
             statutory_deadline="30 June every year (Rule 16, Companies Acceptance of Deposits Rules)",
             penalty_info="₹5,000 + ₹500/day for company; ₹5,000 + ₹500/day for officers"),

        # ── MSME ──────────────────────────────────────────────────────────────────
        dict(compliance_name="MSME-1 — Half-Yearly Return (Oct–Mar)", form_number="MSME-1",
             category=ComplianceCategory.MSME_RELATED,
             due_date=date(fy_start_year + 1, 4, 30), frequency=ReminderFrequency.BIANNUAL,
             statutory_deadline="30 April (for Oct–Mar period)",
             penalty_info="₹25,000 for company + ₹25,000 for each officer in default"),

        dict(compliance_name="MSME-1 — Half-Yearly Return (Apr–Sep)", form_number="MSME-1",
             category=ComplianceCategory.MSME_RELATED,
             due_date=date(fy_start_year + 1, 10, 31), frequency=ReminderFrequency.BIANNUAL,
             statutory_deadline="31 October (for Apr–Sep period)",
             penalty_info="₹25,000 for company + ₹25,000 for each officer in default"),

        # ── Board Meetings ─────────────────────────────────────────────────────────
        dict(compliance_name="Board Meeting — Q1 (Apr–Jun)", form_number="BM-Q1",
             category=ComplianceCategory.ROC_FILING,
             due_date=date(fy_start_year, 9, 30), frequency=ReminderFrequency.QUARTERLY,
             statutory_deadline="Within 120 days of last board meeting (Sec 173)",
             penalty_info="₹25,000 for company + ₹5,000 per director in default"),

        dict(compliance_name="Board Meeting — Q3 (Oct–Dec)", form_number="BM-Q3",
             category=ComplianceCategory.ROC_FILING,
             due_date=date(fy_start_year + 1, 3, 31), frequency=ReminderFrequency.QUARTERLY,
             statutory_deadline="Within 120 days of last board meeting (Sec 173)",
             penalty_info="₹25,000 for company + ₹5,000 per director in default"),

        # ── MGT-14 ────────────────────────────────────────────────────────────────
        dict(compliance_name="MGT-14 — Filing of Board/Special Resolutions", form_number="MGT-14",
             category=ComplianceCategory.ROC_FILING, financial_year=fy,
             due_date=agm_date + timedelta(days=30), frequency=ReminderFrequency.ANNUAL,
             statutory_deadline="Within 30 days of passing resolution (Sec 117)",
             penalty_info="₹5,00,000 for company + ₹1,00,000 for officers; ₹500/day continuing default"),
    ]

    added = 0
    for cfg in defaults:
        exists = db.query(ComplianceReminder).filter(
            ComplianceReminder.company_id == company_id,
            ComplianceReminder.form_number == cfg.get("form_number"),
            ComplianceReminder.financial_year == cfg.get("financial_year"),
        ).first()
        if not exists:
            db.add(ComplianceReminder(**cfg, company_id=company_id))
            added += 1

    db.commit()
    _refresh_statuses(db, company_id)
    return {"message": f"Seeded {added} compliance reminders for FY {fy}"}


# ═══════════════════════════════════════════════════════════
# AUDITOR MANAGEMENT
# ═══════════════════════════════════════════════════════════

def _compute_renewal_date(appointment_date: date) -> date:
    """5 years from appointment date."""
    return appointment_date + relativedelta(years=5)


@router.post("/{company_id}/auditors", response_model=AuditorOut, status_code=201)
def add_auditor(company_id: int, data: AuditorCreate, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)

    # Deactivate previous current auditor
    if data.is_current:
        db.query(Auditor).filter(
            Auditor.company_id == company_id,
            Auditor.is_current == True
        ).update({"is_current": False})

    # Compute renewal date = 5 years from appointment
    renewal_due = _compute_renewal_date(data.appointment_date)
    appt_year = data.appointment_date.year
    reapp_year = f"{appt_year + 5}-{str(appt_year + 6)[2:]}"

    auditor = Auditor(
        **data.model_dump(),
        company_id=company_id,
        renewal_due_date=renewal_due,
        reappointment_due_year=reapp_year,
    )
    db.add(auditor)
    db.commit()
    db.refresh(auditor)
    return auditor


@router.get("/{company_id}/auditors", response_model=List[AuditorOut])
def list_auditors(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    return db.query(Auditor).filter(
        Auditor.company_id == company_id
    ).order_by(Auditor.appointment_date.desc()).all()


@router.get("/{company_id}/auditors/current")
def get_current_auditor(company_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request, db)
    _get_company_or_404(company_id, db)
    auditor = db.query(Auditor).filter(
        Auditor.company_id == company_id,
        Auditor.is_current == True,
        Auditor.status == AuditorStatus.ACTIVE
    ).first()
    if not auditor:
        return {"message": "No active auditor found", "auditor": None}

    today = date.today()
    days_to_renewal = (auditor.renewal_due_date - today).days if auditor.renewal_due_date else None

    return {
        "auditor": {
            "id": auditor.id,
            "firm_name": auditor.firm_name,
            "partner_name": auditor.partner_name,
            "membership_number": auditor.membership_number,
            "firm_registration": auditor.firm_registration,
            "appointment_date": auditor.appointment_date.isoformat(),
            "renewal_due_date": auditor.renewal_due_date.isoformat() if auditor.renewal_due_date else None,
            "reappointment_due_year": auditor.reappointment_due_year,
            "days_to_renewal": days_to_renewal,
            "renewal_alert": days_to_renewal is not None and days_to_renewal <= 180,
            "renewal_urgent": days_to_renewal is not None and days_to_renewal <= 60,
            "status": auditor.status,
        }
    }


@router.post("/{company_id}/auditors/{auditor_id}/resign")
async def record_auditor_resignation(
    company_id: int,
    auditor_id: int,
    data: AuditorCessation,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Record auditor resignation and generate ADT-3 draft in one call.
    """
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    auditor = db.query(Auditor).filter(
        Auditor.id == auditor_id, Auditor.company_id == company_id
    ).first()
    if not auditor:
        raise HTTPException(status_code=404, detail="Auditor not found")

    # Update status
    auditor.status = data.status
    auditor.cessation_date = data.cessation_date
    auditor.cessation_reason = data.cessation_reason
    auditor.adt3_srn = data.adt3_srn
    auditor.is_current = False

    # Generate ADT-3 draft automatically
    co = _company_dict(company)
    aud = {
        "firm_name": auditor.firm_name,
        "partner_name": auditor.partner_name,
        "membership_number": auditor.membership_number,
        "firm_registration": auditor.firm_registration,
        "appointment_date": auditor.appointment_date.isoformat() if auditor.appointment_date else None,
        "cessation_date": data.cessation_date.isoformat(),
    }

    from datetime import datetime as dt
    auditor.ai_adt3_draft = await generate_adt3_resignation_draft(aud, co)
    auditor.ai_generated_at = dt.utcnow()

    db.commit()
    db.refresh(auditor)
    return {
        "message": "Resignation recorded and ADT-3 draft generated",
        "adt3_draft": auditor.ai_adt3_draft,
        "auditor_id": auditor.id,
    }


@router.post("/{company_id}/auditors/{auditor_id}/generate-reappointment")
async def generate_reappointment_docs(
    company_id: int,
    auditor_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Generate Board Resolution + AGM Resolution + Consent letter for re-appointment."""
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    auditor = db.query(Auditor).filter(
        Auditor.id == auditor_id, Auditor.company_id == company_id
    ).first()
    if not auditor:
        raise HTTPException(status_code=404, detail="Auditor not found")

    co = _company_dict(company)
    aud = {
        "firm_name": auditor.firm_name,
        "partner_name": auditor.partner_name,
        "membership_number": auditor.membership_number,
        "firm_registration": auditor.firm_registration,
        "appointment_date": auditor.appointment_date.isoformat() if auditor.appointment_date else None,
    }

    from datetime import datetime as dt
    auditor.ai_reappoint_draft = await generate_auditor_reappointment_resolution(aud, co)
    auditor.ai_generated_at = dt.utcnow()
    db.commit()
    return {"message": "Reappointment documents generated", "draft": auditor.ai_reappoint_draft}


@router.post("/{company_id}/auditors/{auditor_id}/generate-renewal-alert")
async def generate_renewal_alert(
    company_id: int,
    auditor_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Generate renewal alert letter for auditor whose 5-year term is approaching."""
    require_auth(request, db)
    company = _get_company_or_404(company_id, db)
    auditor = db.query(Auditor).filter(
        Auditor.id == auditor_id, Auditor.company_id == company_id
    ).first()
    if not auditor:
        raise HTTPException(status_code=404, detail="Auditor not found")

    co = _company_dict(company)
    aud = {
        "firm_name": auditor.firm_name,
        "appointment_date": auditor.appointment_date.isoformat() if auditor.appointment_date else None,
        "renewal_due_date": auditor.renewal_due_date.isoformat() if auditor.renewal_due_date else None,
    }

    draft = await generate_auditor_renewal_alert_letter(aud, co)
    auditor.renewal_alert_sent = True
    db.commit()
    return {"message": "Renewal alert generated", "draft": draft}


@router.get("/{company_id}/auditors/{auditor_id}/adt3-draft")
def get_adt3_draft(company_id: int, auditor_id: int, request: Request, db: Session = Depends(get_db)):
    """Return existing ADT-3 draft for a resigned auditor."""
    require_auth(request, db)
    auditor = db.query(Auditor).filter(
        Auditor.id == auditor_id, Auditor.company_id == company_id
    ).first()
    if not auditor:
        raise HTTPException(status_code=404, detail="Auditor not found")
    return {"adt3_draft": auditor.ai_adt3_draft, "generated_at": auditor.ai_generated_at}

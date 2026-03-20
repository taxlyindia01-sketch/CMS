"""
Module 3 Schemas — Compliance Reminders & Auditor Management
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from app.models.models import (
    ComplianceCategory, ComplianceStatus, ReminderFrequency,
    AuditorStatus
)


# ─── Compliance Reminder ─────────────────────

class ComplianceReminderCreate(BaseModel):
    compliance_name: str
    form_number: Optional[str] = None
    category: ComplianceCategory
    description: Optional[str] = None
    frequency: Optional[ReminderFrequency] = ReminderFrequency.ANNUAL
    financial_year: Optional[str] = None
    due_date: date
    statutory_deadline: Optional[str] = None
    penalty_info: Optional[str] = None
    mca_link: Optional[str] = None
    status: Optional[ComplianceStatus] = ComplianceStatus.UPCOMING
    notes: Optional[str] = None


class ComplianceReminderUpdate(BaseModel):
    status: Optional[ComplianceStatus] = None
    completed_date: Optional[date] = None
    completed_by: Optional[str] = None
    filing_reference: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[date] = None
    financial_year: Optional[str] = None


class ComplianceReminderOut(ComplianceReminderCreate):
    id: int
    company_id: int
    completed_date: Optional[date] = None
    completed_by: Optional[str] = None
    filing_reference: Optional[str] = None
    ai_checklist: Optional[str] = None
    ai_board_resolution: Optional[str] = None
    ai_reminder_email: Optional[str] = None
    ai_generated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Auditor ─────────────────────────────────

class AuditorCreate(BaseModel):
    firm_name: str
    partner_name: Optional[str] = None
    membership_number: Optional[str] = None
    firm_registration: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    appointment_date: date
    appointment_agm_year: Optional[str] = None
    term_end_date: Optional[date] = None
    adt1_srn: Optional[str] = None
    status: Optional[AuditorStatus] = AuditorStatus.ACTIVE
    is_current: Optional[bool] = True


class AuditorCessation(BaseModel):
    cessation_date: date
    cessation_reason: Optional[str] = "Preoccupied elsewhere and unable to devote requisite time"
    adt3_srn: Optional[str] = None
    status: AuditorStatus = AuditorStatus.RESIGNED


class AuditorOut(AuditorCreate):
    id: int
    company_id: int
    cessation_date: Optional[date] = None
    cessation_reason: Optional[str] = None
    adt3_srn: Optional[str] = None
    reappointment_due_year: Optional[str] = None
    renewal_due_date: Optional[date] = None
    renewal_alert_sent: bool = False
    ai_adt3_draft: Optional[str] = None
    ai_reappoint_draft: Optional[str] = None
    ai_generated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Dashboard Summary ────────────────────────

class ComplianceDashboardItem(BaseModel):
    id: int
    company_id: int
    company_name: str
    compliance_name: str
    form_number: Optional[str]
    category: str
    due_date: Optional[str]
    status: str
    days_remaining: Optional[int]
    is_overdue: bool

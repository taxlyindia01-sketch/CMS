"""
Module 2B Schemas — Meetings, Resolutions & Post-Incorporation Alerts
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import date, datetime
from app.models.models import (
    MeetingType, MeetingStatus, ResolutionType, AlertType, AlertStatus
)


# ─── Meeting Schemas ─────────────────────────

class MeetingCreate(BaseModel):
    meeting_type: MeetingType
    meeting_number: Optional[str] = None
    meeting_date: date
    meeting_time: Optional[str] = None
    venue: Optional[str] = None
    video_conf_link: Optional[str] = None
    status: Optional[MeetingStatus] = MeetingStatus.SCHEDULED
    notice_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    quorum_required: Optional[int] = None
    quorum_present: Optional[int] = None
    chairman: Optional[str] = None
    agenda_items: Optional[List[str]] = Field(default_factory=list)
    minutes_text: Optional[str] = None
    minutes_approved_date: Optional[date] = None
    attendees: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class MeetingUpdate(MeetingCreate):
    meeting_type: Optional[MeetingType] = None
    meeting_date: Optional[date] = None


class MeetingOut(MeetingCreate):
    id: int
    company_id: int
    ai_notice_draft: Optional[str] = None
    ai_minutes_draft: Optional[str] = None
    ai_generated_at: Optional[datetime] = None
    created_at: datetime
    resolutions: List[Any] = []

    model_config = {"from_attributes": True}


# ─── Resolution Schemas ──────────────────────

class ResolutionCreate(BaseModel):
    resolution_number: Optional[str] = None
    resolution_type: Optional[ResolutionType] = ResolutionType.BOARD
    subject: str
    resolution_text: Optional[str] = None
    passed: Optional[bool] = True
    dissenting_votes: Optional[int] = 0
    notes: Optional[str] = None


class ResolutionOut(ResolutionCreate):
    id: int
    meeting_id: int
    ai_draft_text: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Post-Inc Alert Schemas ──────────────────

class AlertCreate(BaseModel):
    alert_type: AlertType
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    statutory_deadline: Optional[str] = None
    penalty_info: Optional[str] = None
    form_number: Optional[str] = None
    mca_link: Optional[str] = None
    status: Optional[AlertStatus] = AlertStatus.PENDING
    completed_date: Optional[date] = None
    completed_by: Optional[str] = None
    notes: Optional[str] = None


class AlertUpdate(BaseModel):
    status: Optional[AlertStatus] = None
    completed_date: Optional[date] = None
    completed_by: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[date] = None


class AlertOut(AlertCreate):
    id: int
    company_id: int
    ai_draft: Optional[str] = None
    ai_generated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── AI Generation Request ───────────────────

class AIGenerateMeetingRequest(BaseModel):
    generate_notice: bool = True
    generate_minutes: bool = True
    generate_resolutions: bool = True
    resolution_subjects: Optional[List[str]] = Field(default_factory=list)

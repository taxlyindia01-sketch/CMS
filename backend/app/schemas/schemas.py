"""
Pydantic Schemas for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from app.models.models import EnquiryStatus, ServiceType


# ─── Staff Schemas ───────────────────────────

class StaffBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    designation: Optional[str] = None

class StaffCreate(StaffBase):
    pass

class StaffOut(StaffBase):
    id: int
    is_active: bool
    active_client_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Enquiry Schemas ─────────────────────────

class EnquiryCreate(BaseModel):
    proposed_company_name: str
    company_address: Optional[str] = None
    authorised_capital: Optional[Decimal] = None
    paidup_capital: Optional[Decimal] = None
    director_names: Optional[List[str]] = Field(default_factory=list)
    shareholder_names: Optional[List[str]] = Field(default_factory=list)
    shareholding_pattern: Optional[Dict[str, float]] = Field(default_factory=dict)
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    service_type: ServiceType = ServiceType.COMPANY_INCORPORATION

class EnquiryUpdate(BaseModel):
    status: Optional[EnquiryStatus] = None
    assigned_staff_id: Optional[int] = None

class EnquiryOut(BaseModel):
    id: int
    proposed_company_name: str
    company_address: Optional[str]
    authorised_capital: Optional[Decimal]
    paidup_capital: Optional[Decimal]
    director_names: List[str]
    shareholder_names: List[str]
    shareholding_pattern: Dict[str, Any]
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    status: EnquiryStatus
    service_type: ServiceType
    assigned_staff_id: Optional[int]
    created_at: datetime
    ai_drafts: List[Any] = []

    model_config = {"from_attributes": True}


# ─── Client Schemas ──────────────────────────

class ClientOut(BaseModel):
    id: int
    client_id: str
    company_name: str
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    assigned_staff_id: Optional[int]
    is_active: bool
    service_type: ServiceType
    created_at: datetime
    # FIX: company_master_id is the CompanyMaster.id (NOT Client.id).
    # All governance routes (/api/meetings, /api/compliance, /api/registers)
    # use CompanyMaster.id. Frontend uses this field to build correct URLs.
    company_master_id: Optional[int] = None

    model_config = {"from_attributes": True}


# ─── Workflow Schemas ────────────────────────

class WorkflowTemplateCreate(BaseModel):
    service_type: ServiceType
    stage_name: str
    stage_order: int
    description: Optional[str] = None

class WorkflowTemplateOut(BaseModel):
    id: int
    service_type: ServiceType
    stage_name: str
    stage_order: int
    description: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}

class WorkflowProgressOut(BaseModel):
    id: int
    template_stage_id: int
    stage_name: str
    stage_order: int
    is_completed: bool
    completed_at: Optional[datetime]
    notes: Optional[str]

    model_config = {"from_attributes": True}


# ─── AI Draft Schemas ────────────────────────

class AIDraftOut(BaseModel):
    id: int
    draft_type: str
    content: str
    generated_at: datetime

    model_config = {"from_attributes": True}


# ─── Dashboard Schema ────────────────────────

class DashboardStats(BaseModel):
    total_enquiries: int
    pending_enquiries: int
    converted_clients: int
    closed_enquiries: int
    active_registrations: int
    staff_workload: List[Dict[str, Any]]

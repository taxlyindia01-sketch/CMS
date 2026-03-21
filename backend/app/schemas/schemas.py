"""
Pydantic Schemas for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
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
    company_address: Optional[str] = None
    authorised_capital: Optional[Decimal] = None
    paidup_capital: Optional[Decimal] = None
    # FIX: These JSON columns can be NULL in DB (rows inserted before defaults were set).
    # Using Optional with default=[] prevents Pydantic validation errors on NULL values.
    director_names: Optional[List[str]] = Field(default_factory=list)
    shareholder_names: Optional[List[str]] = Field(default_factory=list)
    shareholding_pattern: Optional[Dict[str, Any]] = Field(default_factory=dict)
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: EnquiryStatus
    service_type: ServiceType
    assigned_staff_id: Optional[int] = None
    created_at: datetime
    ai_drafts: List[Any] = Field(default_factory=list)

    # FIX: Coerce None → [] for JSON array columns that may be NULL in DB
    @field_validator('director_names', 'shareholder_names', mode='before')
    @classmethod
    def coerce_list(cls, v):
        return v if v is not None else []

    @field_validator('shareholding_pattern', mode='before')
    @classmethod
    def coerce_dict(cls, v):
        return v if v is not None else {}

    model_config = {"from_attributes": True}


# ─── Client Schemas ──────────────────────────

class ClientOut(BaseModel):
    id: int
    client_id: str
    company_name: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    is_active: bool
    service_type: ServiceType
    created_at: datetime
    # company_master_id is CompanyMaster.id (NOT Client.id).
    # All governance routes use CompanyMaster.id.
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
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}

class WorkflowProgressOut(BaseModel):
    id: int
    template_stage_id: int
    stage_name: str
    stage_order: int
    is_completed: bool
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

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

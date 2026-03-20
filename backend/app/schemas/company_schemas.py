"""
Module 2 Schemas — Company Master Records
Pydantic schemas for CompanyMaster, Director, Shareholder, ShareTransfer, Charge
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from app.models.models import ChargeStatus


# ─── Company Master ──────────────────────────

class CompanyMasterCreate(BaseModel):
    cin: Optional[str] = None
    company_name: str
    company_type: Optional[str] = "Private Limited"
    roc: Optional[str] = None

    # Address
    registered_office_address: Optional[str] = None
    corporate_office_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = "India"
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None

    # Capital
    authorised_capital: Optional[Decimal] = None
    paidup_capital: Optional[Decimal] = None
    face_value_per_share: Optional[Decimal] = 10.0
    total_shares: Optional[int] = None

    # Dates
    date_of_incorporation: Optional[date] = None
    financial_year_end: Optional[str] = "31-Mar"
    last_agm_date: Optional[date] = None
    last_agm_financial_year: Optional[str] = None
    last_ar_filed_date: Optional[date] = None
    last_bs_filed_date: Optional[date] = None

    # Bank
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_ifsc: Optional[str] = None

    # Tax Registrations
    pan: Optional[str] = None
    tan: Optional[str] = None
    gstin: Optional[str] = None
    msme_number: Optional[str] = None
    import_export_code: Optional[str] = None


class CompanyMasterUpdate(CompanyMasterCreate):
    company_name: Optional[str] = None


class CompanyMasterOut(CompanyMasterCreate):
    id: int
    client_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── Director ────────────────────────────────

class DirectorCreate(BaseModel):
    full_name: str
    din: Optional[str] = None
    pan: Optional[str] = None
    aadhaar: Optional[str] = None
    designation: Optional[str] = "Director"
    date_of_appointment: Optional[date] = None
    date_of_cessation: Optional[date] = None
    is_active: Optional[bool] = True
    email: Optional[str] = None
    phone: Optional[str] = None
    residential_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    nationality: Optional[str] = "Indian"
    shareholding_ratio: Optional[Decimal] = 0.0
    number_of_shares: Optional[int] = 0
    folio_number: Optional[str] = None
    dsc_expiry_date: Optional[date] = None


class DirectorUpdate(DirectorCreate):
    full_name: Optional[str] = None


class DirectorOut(DirectorCreate):
    id: int
    company_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Shareholder ─────────────────────────────

class ShareholderCreate(BaseModel):
    full_name: str
    shareholder_type: Optional[str] = "Individual"
    pan: Optional[str] = None
    aadhaar: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    nationality: Optional[str] = "Indian"
    folio_number: Optional[str] = None
    number_of_shares: int = 0
    shareholding_ratio: Optional[Decimal] = 0.0
    date_of_allotment: Optional[date] = None
    class_of_shares: Optional[str] = "Equity"


class ShareholderUpdate(ShareholderCreate):
    full_name: Optional[str] = None
    number_of_shares: Optional[int] = None


class ShareholderOut(ShareholderCreate):
    id: int
    company_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Share Transfer ───────────────────────────

class ShareTransferCreate(BaseModel):
    from_shareholder_id: Optional[int] = None
    to_shareholder_id: Optional[int] = None
    from_name: Optional[str] = None
    to_name: Optional[str] = None
    number_of_shares: int
    transfer_price_per_share: Optional[Decimal] = None
    transfer_date: date
    transfer_deed_number: Optional[str] = None
    consideration_amount: Optional[Decimal] = None
    remarks: Optional[str] = None


class ShareTransferOut(ShareTransferCreate):
    id: int
    company_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Charge ──────────────────────────────────

class ChargeCreate(BaseModel):
    charge_id: Optional[str] = None
    charge_holder: str
    charge_amount: Optional[Decimal] = None
    date_of_creation: Optional[date] = None
    date_of_satisfaction: Optional[date] = None
    property_charged: Optional[str] = None
    status: Optional[ChargeStatus] = ChargeStatus.ACTIVE
    remarks: Optional[str] = None


class ChargeOut(ChargeCreate):
    id: int
    company_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

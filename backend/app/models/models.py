"""
Database Models - Module 1 & 2: Lead & Client Management + Company Master Records
All SQLAlchemy ORM models for the CA system
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Enum, JSON, Boolean, Numeric, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class EnquiryStatus(str, enum.Enum):
    PENDING = "Pending"
    CONVERTED = "Converted to Client"
    CLOSED = "Closed"


class ServiceType(str, enum.Enum):
    COMPANY_INCORPORATION = "Company Incorporation"
    GST_REGISTRATION = "GST Registration"
    OTHER = "Other"


# ─────────────────────────────────────────────
# Staff Model
# ─────────────────────────────────────────────

class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20))
    designation = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    clients = relationship("Client", back_populates="assigned_staff")
    enquiries = relationship("Enquiry", back_populates="assigned_staff")

    @property
    def active_client_count(self):
        return len([c for c in self.clients if c.is_active])


# ─────────────────────────────────────────────
# Enquiry Model (Lead)
# ─────────────────────────────────────────────

class Enquiry(Base):
    __tablename__ = "enquiries"

    id = Column(Integer, primary_key=True, index=True)

    # Proposed Company Details
    proposed_company_name = Column(String(255), nullable=False)
    company_address = Column(Text)
    authorised_capital = Column(Numeric(15, 2))
    paidup_capital = Column(Numeric(15, 2))

    # Director & Shareholder Info (stored as JSON for flexibility)
    director_names = Column(JSON, default=[])       # ["Name1", "Name2"]
    shareholder_names = Column(JSON, default=[])    # ["Name1", "Name2"]
    shareholding_pattern = Column(JSON, default={}) # {"Name1": 50, "Name2": 50}

    # Contact Info
    contact_name = Column(String(150))
    contact_email = Column(String(150))
    contact_phone = Column(String(20))

    # Status & Assignment
    status = Column(Enum(EnquiryStatus), default=EnquiryStatus.PENDING, nullable=False)
    service_type = Column(Enum(ServiceType), default=ServiceType.COMPANY_INCORPORATION)
    assigned_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assigned_staff = relationship("Staff", back_populates="enquiries")
    ai_drafts = relationship("AIDraft", back_populates="enquiry")
    client = relationship("Client", back_populates="enquiry", uselist=False)


# ─────────────────────────────────────────────
# AI Draft Model
# ─────────────────────────────────────────────

class AIDraft(Base):
    __tablename__ = "ai_drafts"

    id = Column(Integer, primary_key=True, index=True)
    enquiry_id = Column(Integer, ForeignKey("enquiries.id"), nullable=False)

    draft_type = Column(String(100))  # "thank_you_letter", "document_list", "price_quotation"
    content = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    enquiry = relationship("Enquiry", back_populates="ai_drafts")


# ─────────────────────────────────────────────
# Client Model
# ─────────────────────────────────────────────

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(20), unique=True, nullable=False, index=True)  # e.g. CA-2024-001

    # Linked enquiry
    enquiry_id = Column(Integer, ForeignKey("enquiries.id"), unique=True, nullable=False)

    # Basic Info (populated from enquiry)
    company_name = Column(String(255), nullable=False)
    contact_name = Column(String(150))
    contact_email = Column(String(150))
    contact_phone = Column(String(20))

    # Assignment
    assigned_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    service_type = Column(Enum(ServiceType), default=ServiceType.COMPANY_INCORPORATION)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    enquiry = relationship("Enquiry", back_populates="client")
    assigned_staff = relationship("Staff", back_populates="clients")
    workflow_progresses = relationship("WorkflowProgress", back_populates="client")
    company_master = relationship("CompanyMaster", back_populates="client", uselist=False)


# ─────────────────────────────────────────────
# Workflow Stage Model (configurable in Settings)
# ─────────────────────────────────────────────

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id = Column(Integer, primary_key=True, index=True)
    service_type = Column(Enum(ServiceType), nullable=False)
    stage_name = Column(String(150), nullable=False)
    stage_order = Column(Integer, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    # Relationship
    progresses = relationship("WorkflowProgress", back_populates="template_stage")


class WorkflowProgress(Base):
    __tablename__ = "workflow_progress"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    template_stage_id = Column(Integer, ForeignKey("workflow_templates.id"), nullable=False)

    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text)

    # Relationships
    client = relationship("Client", back_populates="workflow_progresses")
    template_stage = relationship("WorkflowTemplate", back_populates="progresses")


# ═════════════════════════════════════════════════════════════════════════════
# MODULE 2 — COMPANY MASTER RECORDS
# ═════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────
# Company Master Model
# ─────────────────────────────────────────────

class CompanyMaster(Base):
    __tablename__ = "company_master"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), unique=True, nullable=False)

    # ── Core Identifiers ──────────────────────
    cin = Column(String(21), unique=True, nullable=True, index=True)   # e.g. U74999MH2024PTC123456
    company_name = Column(String(255), nullable=False)
    company_type = Column(String(100), default="Private Limited")      # Pvt Ltd, OPC, LLP, etc.
    roc = Column(String(100), nullable=True)                           # ROC Mumbai, ROC Delhi...

    # ── Address ───────────────────────────────
    registered_office_address = Column(Text)
    corporate_office_address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    pincode = Column(String(10))
    country = Column(String(50), default="India")
    email = Column(String(150))
    phone = Column(String(20))
    website = Column(String(200))

    # ── Capital ───────────────────────────────
    authorised_capital = Column(Numeric(15, 2))
    paidup_capital = Column(Numeric(15, 2))
    face_value_per_share = Column(Numeric(10, 2), default=10.0)
    total_shares = Column(Integer)

    # ── Important Dates ───────────────────────
    date_of_incorporation = Column(Date)
    financial_year_end = Column(String(10), default="31-Mar")          # e.g. "31-Mar"
    last_agm_date = Column(Date)
    last_agm_financial_year = Column(String(20))                       # e.g. "2023-24"
    last_ar_filed_date = Column(Date)
    last_bs_filed_date = Column(Date)

    # ── Bank Details ──────────────────────────
    bank_name = Column(String(150))
    bank_account_number = Column(String(50))
    bank_branch = Column(String(150))
    bank_ifsc = Column(String(20))

    # ── Tax Registrations ─────────────────────
    pan = Column(String(10))
    tan = Column(String(10))
    gstin = Column(String(15))
    msme_number = Column(String(50))
    import_export_code = Column(String(20))

    # ── Timestamps ────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ─────────────────────────
    client = relationship("Client", back_populates="company_master")
    directors = relationship("Director", back_populates="company", cascade="all, delete-orphan")
    shareholders = relationship("Shareholder", back_populates="company", cascade="all, delete-orphan")
    share_transfers = relationship("ShareTransfer", back_populates="company", cascade="all, delete-orphan")
    charges = relationship("Charge", back_populates="company", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="company", cascade="all, delete-orphan")
    post_inc_alerts = relationship("PostIncorporationAlert", back_populates="company", cascade="all, delete-orphan")
    compliance_reminders = relationship("ComplianceReminder", back_populates="company", cascade="all, delete-orphan")
    auditors = relationship("Auditor", back_populates="company", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# Director Model
# ─────────────────────────────────────────────

class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    # ── Identity ──────────────────────────────
    full_name = Column(String(150), nullable=False)
    din = Column(String(8), nullable=True, index=True)             # Director Identification Number
    pan = Column(String(10))
    aadhaar = Column(String(12))                                    # Last 4 digits shown only in UI

    # ── Designation ───────────────────────────
    designation = Column(String(100), default="Director")          # MD, WTD, Independent, etc.
    date_of_appointment = Column(Date)
    date_of_cessation = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)

    # ── Contact ───────────────────────────────
    email = Column(String(150))
    phone = Column(String(20))

    # ── Address ───────────────────────────────
    residential_address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    pincode = Column(String(10))
    nationality = Column(String(50), default="Indian")

    # ── Shareholding ──────────────────────────
    shareholding_ratio = Column(Numeric(8, 4), default=0.0)        # Percentage (e.g. 50.00, up to 9999.9999)
    number_of_shares = Column(Integer, default=0)
    folio_number = Column(String(50))

    # ── DSC Details ───────────────────────────
    dsc_expiry_date = Column(Date, nullable=True)

    # ── Timestamps ────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ─────────────────────────
    company = relationship("CompanyMaster", back_populates="directors")


# ─────────────────────────────────────────────
# Shareholder Model
# ─────────────────────────────────────────────

class Shareholder(Base):
    __tablename__ = "shareholders"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    # ── Identity ──────────────────────────────
    full_name = Column(String(150), nullable=False)
    shareholder_type = Column(String(30), default="Individual")    # Individual, Corporate, NRI, etc.
    pan = Column(String(10))
    aadhaar = Column(String(12))

    # ── Contact ───────────────────────────────
    email = Column(String(150))
    phone = Column(String(20))

    # ── Address ───────────────────────────────
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    pincode = Column(String(10))
    nationality = Column(String(50), default="Indian")

    # ── Shareholding ──────────────────────────
    folio_number = Column(String(50), nullable=True, index=True)
    number_of_shares = Column(Integer, default=0, nullable=False)
    shareholding_ratio = Column(Numeric(8, 4), default=0.0)        # Percentage (up to 9999.9999)
    date_of_allotment = Column(Date)
    class_of_shares = Column(String(50), default="Equity")

    # ── Timestamps ────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ─────────────────────────
    company = relationship("CompanyMaster", back_populates="shareholders")
    transfers_from = relationship("ShareTransfer", foreign_keys="[ShareTransfer.from_shareholder_id]", back_populates="from_shareholder")
    transfers_to = relationship("ShareTransfer", foreign_keys="[ShareTransfer.to_shareholder_id]", back_populates="to_shareholder")


# ─────────────────────────────────────────────
# Share Transfer Model
# ─────────────────────────────────────────────

class ShareTransfer(Base):
    __tablename__ = "share_transfers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    from_shareholder_id = Column(Integer, ForeignKey("shareholders.id"), nullable=True)
    to_shareholder_id = Column(Integer, ForeignKey("shareholders.id"), nullable=True)

    from_name = Column(String(150))                                 # Denormalized for history
    to_name = Column(String(150))

    number_of_shares = Column(Integer, nullable=False)
    transfer_price_per_share = Column(Numeric(12, 2))
    transfer_date = Column(Date, nullable=False)
    transfer_deed_number = Column(String(50))
    consideration_amount = Column(Numeric(15, 2))
    remarks = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    company = relationship("CompanyMaster", back_populates="share_transfers")
    from_shareholder = relationship("Shareholder", foreign_keys=[from_shareholder_id], back_populates="transfers_from")
    to_shareholder = relationship("Shareholder", foreign_keys=[to_shareholder_id], back_populates="transfers_to")


# ─────────────────────────────────────────────
# Charge Model (Register of Charges)
# ─────────────────────────────────────────────

class ChargeStatus(str, enum.Enum):
    ACTIVE = "Active"
    SATISFIED = "Satisfied"
    MODIFIED = "Modified"


class Charge(Base):
    __tablename__ = "charges"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    charge_id = Column(String(50), nullable=True)                  # MCA Charge ID
    charge_holder = Column(String(255), nullable=False)            # Bank/lender name
    charge_amount = Column(Numeric(15, 2))
    date_of_creation = Column(Date)
    date_of_satisfaction = Column(Date, nullable=True)
    property_charged = Column(Text)                                # Description of assets charged
    status = Column(Enum(ChargeStatus), default=ChargeStatus.ACTIVE)
    remarks = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("CompanyMaster", back_populates="charges")


# ═════════════════════════════════════════════════════════════════════════════
# MODULE 2B — MEETINGS (Board, AGM, EGM) & POST-INCORPORATION ALERTS
# ═════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class MeetingType(str, enum.Enum):
    BOARD           = "Board Meeting"
    AGM             = "Annual General Meeting"
    EGM             = "Extraordinary General Meeting"
    COMMITTEE       = "Committee Meeting"
    POSTAL_BALLOT   = "Postal Ballot"


class MeetingStatus(str, enum.Enum):
    SCHEDULED   = "Scheduled"
    COMPLETED   = "Completed"
    ADJOURNED   = "Adjourned"
    CANCELLED   = "Cancelled"


class ResolutionType(str, enum.Enum):
    ORDINARY    = "Ordinary Resolution"
    SPECIAL     = "Special Resolution"
    BOARD       = "Board Resolution"


class AlertType(str, enum.Enum):
    INC_20A             = "INC-20A"           # Declaration of commencement of business
    ADT_1               = "ADT-1"             # Auditor appointment
    FIRST_BOARD_MEETING = "First Board Meeting"
    STATUTORY_AUDIT     = "Statutory Audit Appointment"
    DIR_12              = "DIR-12"            # Change in directors
    SHARE_CERTIFICATE   = "Share Certificate Issuance"
    REGISTERED_OFFICE   = "Registered Office Verification"
    OTHER               = "Other"


class AlertStatus(str, enum.Enum):
    PENDING     = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED   = "Completed"
    OVERDUE     = "Overdue"


# ─────────────────────────────────────────────
# Meeting Model
# ─────────────────────────────────────────────

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    # ── Core Details ──────────────────────────
    meeting_type    = Column(Enum(MeetingType), nullable=False)
    meeting_number  = Column(String(50))               # e.g. "1st BM 2024", "AGM 2023-24"
    meeting_date    = Column(Date, nullable=False)
    meeting_time    = Column(String(20))               # e.g. "11:00 AM"
    venue           = Column(Text)
    video_conf_link = Column(String(500))              # For hybrid/virtual meetings
    status          = Column(Enum(MeetingStatus), default=MeetingStatus.SCHEDULED)

    # ── Notice & Quorum ───────────────────────
    notice_date             = Column(Date)             # Date notice was issued
    notice_period_days      = Column(Integer)          # e.g. 7 for BM, 21 for AGM
    quorum_required         = Column(Integer)          # Minimum directors/members required
    quorum_present          = Column(Integer)          # Actual attendance
    chairman                = Column(String(150))      # Name of chairman

    # ── Agenda & Minutes ──────────────────────
    agenda_items    = Column(JSON, default=[])         # ["Item 1: ...", "Item 2: ..."]
    minutes_text    = Column(Text)                     # Full minutes draft
    minutes_approved_date = Column(Date)

    # ── AI Drafts ─────────────────────────────
    ai_notice_draft     = Column(Text)                 # AI-generated meeting notice
    ai_minutes_draft    = Column(Text)                 # AI-generated minutes
    ai_generated_at     = Column(DateTime(timezone=True))

    # ── Attendance ────────────────────────────
    attendees       = Column(JSON, default=[])         # [{"name": "...", "din": "...", "present": true}]

    # ── Timestamps ────────────────────────────
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ─────────────────────────
    company     = relationship("CompanyMaster", back_populates="meetings")
    resolutions = relationship("Resolution", back_populates="meeting", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# Resolution Model
# ─────────────────────────────────────────────

class Resolution(Base):
    __tablename__ = "resolutions"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)

    resolution_number   = Column(String(20))           # e.g. "BR-001/2024"
    resolution_type     = Column(Enum(ResolutionType), default=ResolutionType.BOARD)
    subject             = Column(String(500), nullable=False)
    resolution_text     = Column(Text)                 # Full resolution body
    ai_draft_text       = Column(Text)                 # AI-generated draft
    passed              = Column(Boolean, default=True)
    dissenting_votes    = Column(Integer, default=0)
    notes               = Column(Text)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    meeting     = relationship("Meeting", back_populates="resolutions")


# ─────────────────────────────────────────────
# Post-Incorporation Alert Model
# ─────────────────────────────────────────────

class PostIncorporationAlert(Base):
    __tablename__ = "post_incorporation_alerts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    # ── Alert Details ─────────────────────────
    alert_type          = Column(Enum(AlertType), nullable=False)
    title               = Column(String(300), nullable=False)
    description         = Column(Text)
    due_date            = Column(Date)
    statutory_deadline  = Column(String(200))          # e.g. "Within 180 days of incorporation"
    penalty_info        = Column(Text)                 # Penalty for non-compliance
    form_number         = Column(String(50))           # e.g. "INC-20A", "ADT-1"
    mca_link            = Column(String(500))

    # ── Status ────────────────────────────────
    status              = Column(Enum(AlertStatus), default=AlertStatus.PENDING)
    completed_date      = Column(Date)
    completed_by        = Column(String(150))
    notes               = Column(Text)

    # ── AI Draft ──────────────────────────────
    ai_draft            = Column(Text)                 # AI-generated draft document
    ai_generated_at     = Column(DateTime(timezone=True))

    # ── Timestamps ────────────────────────────
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    company     = relationship("CompanyMaster", back_populates="post_inc_alerts")


# ═════════════════════════════════════════════════════════════════════════════
# MODULE 3 — COMPLIANCE REMINDER SYSTEM + AUDITOR MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────
# Enums — Module 3
# ─────────────────────────────────────────────

class ComplianceCategory(str, enum.Enum):
    ANNUAL_FILING       = "Annual Filing"
    AGM_RELATED         = "AGM Related"
    DIRECTOR_KYC        = "Director KYC"
    AUDITOR             = "Auditor"
    MSME_RELATED        = "MSME Related"
    DEPOSIT_RELATED     = "Deposit Related"
    ROC_FILING          = "ROC Filing"
    GST                 = "GST"
    INCOME_TAX          = "Income Tax"
    OTHER               = "Other"


class ComplianceStatus(str, enum.Enum):
    UPCOMING    = "Upcoming"
    DUE_SOON    = "Due Soon"       # within 30 days
    OVERDUE     = "Overdue"
    COMPLETED   = "Completed"
    NOT_APPLICABLE = "N/A"


class ReminderFrequency(str, enum.Enum):
    ANNUAL      = "Annual"
    BIANNUAL    = "Bi-Annual"
    QUARTERLY   = "Quarterly"
    MONTHLY     = "Monthly"
    ONE_TIME    = "One Time"
    EVERY_5_YEARS = "Every 5 Years"


class AuditorStatus(str, enum.Enum):
    ACTIVE      = "Active"
    RESIGNED    = "Resigned"
    REMOVED     = "Removed"
    TERM_ENDED  = "Term Ended"


# ─────────────────────────────────────────────
# ComplianceReminder — one record per compliance item per company
# ─────────────────────────────────────────────

class ComplianceReminder(Base):
    __tablename__ = "compliance_reminders"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    # ── Identity ──────────────────────────────
    compliance_name     = Column(String(300), nullable=False)   # e.g. "MGT-7 Annual Return"
    form_number         = Column(String(50))                    # e.g. "MGT-7"
    category            = Column(Enum(ComplianceCategory), nullable=False)
    description         = Column(Text)
    frequency           = Column(Enum(ReminderFrequency), default=ReminderFrequency.ANNUAL)

    # ── Dates ─────────────────────────────────
    financial_year      = Column(String(20))                    # e.g. "2024-25"
    due_date            = Column(Date, nullable=False)
    statutory_deadline  = Column(String(300))
    penalty_info        = Column(Text)
    mca_link            = Column(String(500))

    # ── Status ────────────────────────────────
    status              = Column(Enum(ComplianceStatus), default=ComplianceStatus.UPCOMING)
    completed_date      = Column(Date)
    completed_by        = Column(String(150))
    filing_reference    = Column(String(200))                   # SRN / acknowledgment
    notes               = Column(Text)

    # ── AI Drafts ─────────────────────────────
    ai_checklist        = Column(Text)
    ai_board_resolution = Column(Text)
    ai_reminder_email   = Column(Text)
    ai_generated_at     = Column(DateTime(timezone=True))

    # ── Timestamps ────────────────────────────
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    company     = relationship("CompanyMaster", back_populates="compliance_reminders")


# ─────────────────────────────────────────────
# Auditor — tracks appointment history + renewal alerts
# ─────────────────────────────────────────────

class Auditor(Base):
    __tablename__ = "auditors"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_master.id"), nullable=False)

    # ── Firm / Individual Details ─────────────
    firm_name           = Column(String(255), nullable=False)
    partner_name        = Column(String(150))
    membership_number   = Column(String(20))        # ICAI Membership No.
    firm_registration   = Column(String(20))        # FRN
    email               = Column(String(150))
    phone               = Column(String(20))
    address             = Column(Text)

    # ── Appointment Details ───────────────────
    appointment_date    = Column(Date, nullable=False)
    appointment_agm_year = Column(String(20))       # e.g. "2019-20"
    reappointment_due_year = Column(String(20))     # Calculated: 5 years from appt
    term_end_date       = Column(Date)              # Typically 5 years from appointment AGM
    adt1_srn            = Column(String(50))        # ADT-1 filing SRN

    # ── Status ────────────────────────────────
    status              = Column(Enum(AuditorStatus), default=AuditorStatus.ACTIVE)
    is_current          = Column(Boolean, default=True)

    # ── Resignation / Removal ─────────────────
    cessation_date      = Column(Date)
    cessation_reason    = Column(Text)
    adt3_srn            = Column(String(50))        # ADT-3 filing SRN (on resignation)

    # ── AI Draft Fields ───────────────────────
    ai_adt3_draft       = Column(Text)              # AI-generated ADT-3 resignation letter
    ai_reappoint_draft  = Column(Text)              # AI-generated reappointment resolution
    ai_generated_at     = Column(DateTime(timezone=True))

    # ── Renewal Alert ─────────────────────────
    renewal_alert_sent  = Column(Boolean, default=False)
    renewal_due_date    = Column(Date)              # Computed: 5 years from appointment

    # ── Timestamps ────────────────────────────
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    company     = relationship("CompanyMaster", back_populates="auditors")


# ═════════════════════════════════════════════════════════════════════════════
# AUTH — User Accounts & Sessions
# ═════════════════════════════════════════════════════════════════════════════

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"   # Full access: all clients, settings, user management
    ADMIN       = "admin"         # Full access except user management
    MANAGER     = "manager"       # All clients, no settings/user mgmt
    STAFF       = "staff"         # Only own assigned clients
    VIEWER      = "viewer"        # Read-only across all clients


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(150), nullable=False)
    email       = Column(String(200), unique=True, nullable=False, index=True)
    phone       = Column(String(20))
    role        = Column(Enum(UserRole), default=UserRole.STAFF, nullable=False)

    # ── Auth ──────────────────────────────────
    password_hash   = Column(String(256), nullable=False)
    password_salt   = Column(String(64), nullable=False)
    is_active       = Column(Boolean, default=True)
    must_change_pwd = Column(Boolean, default=True)   # Force change on first login

    # ── Linked staff member (optional) ────────
    staff_id    = Column(Integer, ForeignKey("staff.id"), nullable=True)

    # ── Session tracking ──────────────────────
    last_login  = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)

    # ── Timestamps ────────────────────────────
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())
    created_by  = Column(Integer, nullable=True)   # user_id who created this account

    linked_staff = relationship("Staff", foreign_keys=[staff_id])
    sessions     = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    """Server-side session store — token maps to user."""
    __tablename__ = "user_sessions"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("user_accounts.id"), nullable=False)
    token       = Column(String(128), unique=True, nullable=False, index=True)
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    ip_address  = Column(String(50))
    user_agent  = Column(String(300))
    is_revoked  = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("UserAccount", back_populates="sessions")


class AuditLog(Base):
    """Track all significant actions for security/compliance."""
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("user_accounts.id"), nullable=True)
    user_email  = Column(String(200))
    action      = Column(String(200), nullable=False)   # e.g. "LOGIN", "CREATE_ENQUIRY"
    resource    = Column(String(100))                   # e.g. "enquiry", "client"
    resource_id = Column(String(50))
    details     = Column(JSON)
    ip_address  = Column(String(50))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

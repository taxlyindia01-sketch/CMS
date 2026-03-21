"""
CA Compliance & Client Management System
Main FastAPI Application Entry Point
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, SessionLocal
from app.routers import (
    enquiries, clients, staff, workflows,
    ai_drafts, company_master, meetings,
    compliance, registers, auth, dashboard,
)

# Create all DB tables on startup
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup tasks:
    1. Seed super-admin if none exists
    2. Seed default workflow stages for all service types — so fresh installs
       always have workflow progress records when an enquiry is converted,
       instead of showing 0/0 · 0% with an empty timeline.
    """
    db = SessionLocal()
    try:
        from app.services.auth_service import ensure_super_admin
        ensure_super_admin(db)

        # Seed default workflows at startup (idempotent — skips existing stages)
        from app.models.models import WorkflowTemplate, ServiceType
        from app.routers.enquiries import _ensure_workflow_stages
        for svc in [
            ServiceType.COMPANY_INCORPORATION,
            ServiceType.GST_REGISTRATION,
            ServiceType.OTHER,
        ]:
            _ensure_workflow_stages(svc, db)

        print("✅ Startup seeds complete")
    except Exception as e:
        print(f"⚠️  Startup seed error (non-fatal): {e}")
    finally:
        db.close()
    yield


app = FastAPI(
    title="CA Compliance & Client Management System",
    description="Client onboarding, incorporation workflow, compliance tracking",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8004,http://127.0.0.1:8004,http://localhost:3000,"
    "http://localhost:8000,http://localhost:8007,http://127.0.0.1:8007",
)
_ALLOWED_ORIGINS = [o.strip() for o in _raw.split(",") if o.strip()]
_ALLOWED_METHODS = os.getenv("ALLOWED_METHODS", "GET,POST,PATCH,PUT,DELETE,OPTIONS").split(",")
_ALLOWED_HEADERS = os.getenv("ALLOWED_HEADERS", "Content-Type,Authorization,X-Requested-With").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=_ALLOWED_METHODS,
    allow_headers=_ALLOWED_HEADERS,
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,           tags=["Auth"])
app.include_router(dashboard.router,      prefix="",                   tags=["Dashboard"])
app.include_router(enquiries.router,      prefix="/api/enquiries",     tags=["Enquiries"])
app.include_router(clients.router,        prefix="/api/clients",       tags=["Clients"])
app.include_router(staff.router,          prefix="/api/staff",         tags=["Staff"])
app.include_router(workflows.router,      prefix="/api/workflows",     tags=["Workflows"])
app.include_router(ai_drafts.router,      prefix="/api/ai",            tags=["AI Drafts"])
app.include_router(company_master.router, prefix="/api/company",       tags=["Company Master"])
app.include_router(meetings.router,       prefix="/api/meetings",      tags=["Meetings & Alerts"])
app.include_router(compliance.router,     prefix="/api/compliance",    tags=["Compliance"])
app.include_router(registers.router,      prefix="/api/registers",     tags=["Registers"])

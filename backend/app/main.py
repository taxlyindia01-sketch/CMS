"""
CA Compliance & Client Management System
Main FastAPI Application Entry Point
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

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
    """Startup: seed super-admin if none exists."""
    db = SessionLocal()
    try:
        from app.services.auth_service import ensure_super_admin
        ensure_super_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="CA Compliance & Client Management System",
    description="Client onboarding, incorporation workflow, compliance tracking",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the server's own origin + localhost for dev.
# Add your production domain to ALLOWED_ORIGINS env var if needed.
_raw = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8004,http://127.0.0.1:8004,http://localhost:3000,http://localhost:8000"
)
_ALLOWED_ORIGINS = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# auth owns: GET /, /login, /app, /change-password, /admin/users + all /api/auth/*
app.include_router(auth.router,           tags=["Auth"])
# dashboard owns: all other HTML sub-pages + GET /api/dashboard/stats
app.include_router(dashboard.router,      prefix="",                   tags=["Dashboard"])
# API routers
app.include_router(enquiries.router,      prefix="/api/enquiries",     tags=["Enquiries"])
app.include_router(clients.router,        prefix="/api/clients",       tags=["Clients"])
app.include_router(staff.router,          prefix="/api/staff",         tags=["Staff"])
app.include_router(workflows.router,      prefix="/api/workflows",     tags=["Workflows"])
app.include_router(ai_drafts.router,      prefix="/api/ai",            tags=["AI Drafts"])
app.include_router(company_master.router, prefix="/api/company",       tags=["Company Master"])
app.include_router(meetings.router,       prefix="/api/meetings",      tags=["Meetings & Alerts"])
app.include_router(compliance.router,     prefix="/api/compliance",    tags=["Compliance"])
app.include_router(registers.router,      prefix="/api/registers",     tags=["Registers"])

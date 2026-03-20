"""
CA Compliance & Client Management System
Main FastAPI Application Entry Point — with Authentication
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from pathlib import Path

# Project root = two levels up from this file (backend/app/main.py -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

from app.database import engine, Base, SessionLocal
from app.routers import (
    enquiries, clients, staff, workflows,
    ai_drafts, company_master, meetings,
    compliance, registers, auth, dashboard
)

# Create all tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

import os
_ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,   # ← explicit list; "*" is invalid with credentials=True
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "frontend" / "static")), name="static")

# Auth router owns "/" and "/login" and "/dashboard"
app.include_router(auth.router, tags=["Auth"])
# Dashboard pages (all other HTML pages)
app.include_router(dashboard.router, prefix="", tags=["Dashboard"])
# API routers
app.include_router(enquiries.router,      prefix="/api/enquiries",   tags=["Enquiries"])
app.include_router(clients.router,        prefix="/api/clients",     tags=["Clients"])
app.include_router(staff.router,          prefix="/api/staff",       tags=["Staff"])
app.include_router(workflows.router,      prefix="/api/workflows",   tags=["Workflows"])
app.include_router(ai_drafts.router,      prefix="/api/ai",          tags=["AI Drafts"])
app.include_router(company_master.router, prefix="/api/company",     tags=["Company Master"])
app.include_router(meetings.router,       prefix="/api/meetings",    tags=["Meetings & Alerts"])
app.include_router(compliance.router,     prefix="/api/compliance",  tags=["Compliance & Auditors"])
app.include_router(registers.router,      prefix="/api/registers",   tags=["Statutory Registers"])

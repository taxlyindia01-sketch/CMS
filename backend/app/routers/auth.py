"""
Auth Router
Handles: login, logout, change password, user management (CRUD), audit log
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_db
from app.models.models import UserAccount, UserSession, AuditLog, UserRole, Staff
from app.schemas.auth_schemas import (
    LoginRequest, ChangePasswordRequest,
    UserCreateRequest, UserUpdateRequest, UserOut,
)
from app.services.auth_service import (
    verify_password, hash_password, generate_temp_password,
    create_session, get_token_from_request, get_session_user,
    revoke_session, revoke_all_user_sessions,
    require_auth, require_role, can, log_action,
    COOKIE_NAME, SESSION_DURATION_HOURS,
)

router = APIRouter()
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ── Pages ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def landing_or_redirect(request: Request, db: Session = Depends(get_db)):
    """Root: redirect logged-in users to dashboard, else show landing."""
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect(request: Request, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.must_change_pwd:
        return RedirectResponse("/change-password", status_code=302)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
    })


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request):
    return templates.TemplateResponse("change_password.html", {"request": request})


@router.get("/admin/users", response_class=HTMLResponse)
def users_admin_page(request: Request, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not can(user, "manage_users"):
        return templates.TemplateResponse("403.html", {"request": request}, status_code=403)
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "current_user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
    })


# ── Auth API ───────────────────────────────────────────────────────────────────

@router.post("/api/auth/login")
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(UserAccount).filter(
        UserAccount.email == data.email.strip().lower(),
        UserAccount.is_active == True,
    ).first()

    if not user or not verify_password(data.password, user.password_hash, user.password_salt):
        log_action(db, "LOGIN_FAILED", details={"email": data.email},
                   ip=request.client.host if request.client else None)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_session(
        user.id, db,
        ip=request.client.host if request.client else None,
        ua=request.headers.get("user-agent"),
    )

    # Update login stats
    user.last_login = datetime.now(timezone.utc)
    user.login_count = (user.login_count or 0) + 1
    db.commit()

    log_action(db, "LOGIN_SUCCESS", user=user,
               ip=request.client.host if request.client else None)

    # Set cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_DURATION_HOURS * 3600,
    )

    return {
        "success": True,
        "token": token,
        "must_change_pwd": user.must_change_pwd,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
        "redirect": "/change-password" if user.must_change_pwd else "/dashboard",
    }


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    if token:
        revoke_session(token, db)
    response.delete_cookie(COOKIE_NAME)
    return {"success": True}


@router.get("/api/auth/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "must_change_pwd": user.must_change_pwd,
        "permissions": {
            "manage_users": can(user, "manage_users"),
            "view_all_clients": can(user, "view_all_clients"),
            "manage_settings": can(user, "manage_settings"),
            "delete_records": can(user, "delete_records"),
            "export_data": can(user, "export_data"),
            "view_audit_log": can(user, "view_audit_log"),
        }
    }


@router.post("/api/auth/change-password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_auth(request, db)

    if not verify_password(data.current_password, user.password_hash, user.password_salt):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    new_hash, new_salt = hash_password(data.new_password)
    user.password_hash = new_hash
    user.password_salt = new_salt
    user.must_change_pwd = False
    db.commit()

    log_action(db, "PASSWORD_CHANGED", user=user)
    return {"success": True, "message": "Password changed successfully"}


# ── User Management API (Super Admin / Admin only) ─────────────────────────────

@router.get("/api/auth/users", response_model=List[UserOut])
def list_users(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    require_role(user, UserRole.SUPER_ADMIN, UserRole.ADMIN)
    return db.query(UserAccount).order_by(UserAccount.created_at.desc()).all()


@router.post("/api/auth/users", response_model=UserOut, status_code=201)
def create_user(
    data: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = require_auth(request, db)
    require_role(current_user, UserRole.SUPER_ADMIN, UserRole.ADMIN)

    # Only super_admin can create super_admin
    if data.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admin can create super admin accounts")

    existing = db.query(UserAccount).filter(UserAccount.email == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    raw_password = data.password or generate_temp_password()
    pwd_hash, salt = hash_password(raw_password)

    new_user = UserAccount(
        name=data.name,
        email=data.email.strip().lower(),
        phone=data.phone,
        role=data.role,
        password_hash=pwd_hash,
        password_salt=salt,
        must_change_pwd=True,
        staff_id=data.staff_id,
        created_by=current_user.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_action(db, "USER_CREATED", user=current_user,
               resource="user_account", resource_id=new_user.id,
               details={"email": new_user.email, "role": new_user.role})

    # Return with temp password in response (shown once)
    result = UserOut.model_validate(new_user)
    # Attach temp password as extra field
    return_data = result.model_dump()
    return_data["temp_password"] = raw_password if not data.password else None
    return return_data


@router.patch("/api/auth/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = require_auth(request, db)
    require_role(current_user, UserRole.SUPER_ADMIN, UserRole.ADMIN)

    target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Cannot demote/change super admin unless you are super admin
    if target.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot modify super admin accounts")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(target, k, v)
    db.commit()
    db.refresh(target)

    log_action(db, "USER_UPDATED", user=current_user, resource="user_account", resource_id=user_id)
    return target


@router.post("/api/auth/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = require_auth(request, db)
    require_role(current_user, UserRole.SUPER_ADMIN, UserRole.ADMIN)

    target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    temp_pwd = generate_temp_password()
    pwd_hash, salt = hash_password(temp_pwd)
    target.password_hash = pwd_hash
    target.password_salt = salt
    target.must_change_pwd = True
    db.commit()

    # Revoke all existing sessions
    revoke_all_user_sessions(user_id, db)

    log_action(db, "PASSWORD_RESET", user=current_user, resource="user_account", resource_id=user_id)
    return {"success": True, "temp_password": temp_pwd, "message": "Password reset. Share temp password securely."}


@router.delete("/api/auth/users/{user_id}")
def deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = require_auth(request, db)
    require_role(current_user, UserRole.SUPER_ADMIN)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = False
    revoke_all_user_sessions(user_id, db)
    db.commit()

    log_action(db, "USER_DEACTIVATED", user=current_user, resource="user_account", resource_id=user_id)
    return {"success": True, "message": "User deactivated"}


# ── Audit Log ──────────────────────────────────────────────────────────────────

@router.get("/api/auth/audit-log")
def get_audit_log(
    request: Request,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    user = require_auth(request, db)
    if not can(user, "view_audit_log"):
        raise HTTPException(status_code=403, detail="Access denied")

    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "user_email": l.user_email,
            "action": l.action,
            "resource": l.resource,
            "resource_id": l.resource_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


# ── Single-page app route ──────────────────────────────────────────────────────

@router.get("/app", response_class=HTMLResponse)
def spa_page(request: Request):
    """Single HTML file — landing + login + dashboard in one page."""
    return templates.TemplateResponse("app.html", {"request": request})

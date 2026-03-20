"""
Auth Router
All HTML page routes serve Index.html (self-contained SPA).
No Jinja2 templates required.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AuditLog, UserAccount, UserRole
from app.schemas.auth_schemas import (
    ChangePasswordRequest,
    LoginRequest,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
)
from app.services.auth_service import (
    COOKIE_NAME,
    SESSION_DURATION_HOURS,
    can,
    create_session,
    generate_temp_password,
    get_session_user,
    get_token_from_request,
    hash_password,
    log_action,
    require_auth,
    require_role,
    revoke_all_user_sessions,
    revoke_session,
    verify_password,
)

router = APIRouter()

# Absolute path to the SPA HTML file.
# File lives at:  <project_root>/frontend/Static/Index.html
# auth.py lives at: <project_root>/backend/app/routers/auth.py
#   → .parent = routers/  .parent.parent = app/  .parent.parent.parent = backend/
#   → .parent.parent.parent.parent = <project_root>/
_SPA = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "Static" / "Index.html"


def _spa() -> FileResponse:
    """Serve the single-page application HTML file."""
    return FileResponse(str(_SPA), media_type="text/html")


# ── HTML Page Routes ──────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    """Landing page — redirect authenticated users straight into the app."""
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if user and not user.must_change_pwd:
        return RedirectResponse("/app", status_code=302)
    return _spa()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if user and not user.must_change_pwd:
        return RedirectResponse("/app", status_code=302)
    return _spa()


@router.get("/app", response_class=HTMLResponse)
def spa_app(request: Request):
    """Main SPA shell — JS handles all view routing internally."""
    return _spa()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect():
    return RedirectResponse("/app", status_code=302)


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page():
    return _spa()


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if not user:
        return RedirectResponse("/", status_code=302)
    return _spa()


# ── Auth API ──────────────────────────────────────────────────────────────────

@router.post("/api/auth/login")
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
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

    user.last_login = datetime.now(timezone.utc)
    user.login_count = (user.login_count or 0) + 1
    db.commit()

    log_action(db, "LOGIN_SUCCESS", user=user,
               ip=request.client.host if request.client else None)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_DURATION_HOURS * 3600,
    )

    return {
        "ok": True,
        "token": token,
        "must_change_pwd": user.must_change_pwd,
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
        "redirect": "/change-password" if user.must_change_pwd else "/app",
    }


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    if token:
        revoke_session(token, db)
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


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
            "manage_users":    can(user, "manage_users"),
            "view_all_clients":can(user, "view_all_clients"),
            "manage_settings": can(user, "manage_settings"),
            "delete_records":  can(user, "delete_records"),
            "export_data":     can(user, "export_data"),
            "view_audit_log":  can(user, "view_audit_log"),
        },
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
    return {"ok": True, "message": "Password changed successfully"}


@router.get("/api/auth/users", response_model=List[UserOut])
def list_users(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    require_role(user, UserRole.SUPER_ADMIN, UserRole.ADMIN)
    return db.query(UserAccount).order_by(UserAccount.created_at.desc()).all()


@router.post("/api/auth/users", status_code=201)
def create_user(
    data: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    current = require_auth(request, db)
    require_role(current, UserRole.SUPER_ADMIN, UserRole.ADMIN)
    if data.role == UserRole.SUPER_ADMIN and current.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admin can create super admin accounts")
    if db.query(UserAccount).filter(UserAccount.email == data.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    raw_pwd = data.password or generate_temp_password()
    pwd_hash, salt = hash_password(raw_pwd)
    new_user = UserAccount(
        name=data.name, email=data.email.strip().lower(), phone=data.phone,
        role=data.role, password_hash=pwd_hash, password_salt=salt,
        must_change_pwd=True, staff_id=data.staff_id, created_by=current.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    log_action(db, "USER_CREATED", user=current, resource="user_account",
               resource_id=new_user.id, details={"email": new_user.email})
    result = UserOut.model_validate(new_user).model_dump()
    result["temp_password"] = raw_pwd if not data.password else None
    return result


@router.patch("/api/auth/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    current = require_auth(request, db)
    require_role(current, UserRole.SUPER_ADMIN, UserRole.ADMIN)
    target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == UserRole.SUPER_ADMIN and current.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot modify super admin accounts")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(target, k, v)
    db.commit()
    db.refresh(target)
    log_action(db, "USER_UPDATED", user=current, resource="user_account", resource_id=user_id)
    return UserOut.model_validate(target)


@router.post("/api/auth/users/{user_id}/reset-password")
def reset_password(user_id: int, request: Request, db: Session = Depends(get_db)):
    current = require_auth(request, db)
    require_role(current, UserRole.SUPER_ADMIN, UserRole.ADMIN)
    target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    temp = generate_temp_password()
    pwd_hash, salt = hash_password(temp)
    target.password_hash = pwd_hash
    target.password_salt = salt
    target.must_change_pwd = True
    db.commit()
    revoke_all_user_sessions(user_id, db)
    log_action(db, "PASSWORD_RESET", user=current, resource="user_account", resource_id=user_id)
    return {"ok": True, "temp_password": temp}


@router.delete("/api/auth/users/{user_id}")
def deactivate_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    current = require_auth(request, db)
    require_role(current, UserRole.SUPER_ADMIN)
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    revoke_all_user_sessions(user_id, db)
    db.commit()
    log_action(db, "USER_DEACTIVATED", user=current, resource="user_account", resource_id=user_id)
    return {"ok": True}


@router.get("/api/auth/audit-log")
def audit_log(request: Request, limit: int = 100, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    if not can(user, "view_audit_log"):
        raise HTTPException(status_code=403, detail="Access denied")
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id, "user_email": l.user_email, "action": l.action,
            "resource": l.resource, "resource_id": l.resource_id,
            "details": l.details, "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]

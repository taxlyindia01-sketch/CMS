"""
Auth Service — stdlib only (hashlib + secrets)
No external jwt/passlib dependency needed.

Password: PBKDF2-HMAC-SHA256 with random salt
Sessions: random 64-byte hex token stored in DB with expiry
"""

import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException, Request, status

from app.models.models import UserAccount, UserSession, AuditLog, UserRole


# ─── Constants ────────────────────────────────────────────────────────────────
SESSION_DURATION_HOURS = 12
PBKDF2_ITERATIONS      = 260_000


# ─── Password Helpers ─────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    """PBKDF2-HMAC-SHA256 password hash."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return dk.hex()


def generate_salt() -> str:
    return secrets.token_hex(32)


def hash_password(password: str) -> Tuple[str, str]:
    """Returns (hash, salt)."""
    salt = generate_salt()
    return _hash_password(password, salt), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    computed = _hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)


def generate_temp_password(length: int = 12) -> str:
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ─── Session Helpers ──────────────────────────────────────────────────────────

def create_session(user_id: int, db: Session,
                   ip: str = None, ua: str = None) -> str:
    token = secrets.token_hex(64)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_DURATION_HOURS)
    sess = UserSession(
        user_id=user_id,
        token=token,
        expires_at=expires,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(sess)
    db.commit()
    return token


def get_session_user(token: str, db: Session) -> Optional[UserAccount]:
    """Return user if token is valid and not expired."""
    if not token:
        return None
    now = datetime.now(timezone.utc)
    sess = db.query(UserSession).filter(
        UserSession.token == token,
        UserSession.is_revoked == False,
        UserSession.expires_at > now,
    ).first()
    if not sess:
        return None
    user = db.query(UserAccount).filter(
        UserAccount.id == sess.user_id,
        UserAccount.is_active == True,
    ).first()
    return user


def revoke_session(token: str, db: Session):
    sess = db.query(UserSession).filter(UserSession.token == token).first()
    if sess:
        sess.is_revoked = True
        db.commit()


def revoke_all_user_sessions(user_id: int, db: Session):
    db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_revoked == False,
    ).update({"is_revoked": True})
    db.commit()


# ─── Request Auth Helpers ─────────────────────────────────────────────────────

COOKIE_NAME = "ca_session"


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract token from cookie or Authorization header."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


def require_auth(request: Request, db: Session) -> UserAccount:
    """Raise 401 if not authenticated, else return user."""
    token = get_token_from_request(request)
    user = get_session_user(token, db) if token else None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"X-Redirect": "/login"},
        )
    return user


def require_role(user: UserAccount, *roles: UserRole):
    """Raise 403 if user doesn't have required role."""
    if user.role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required roles: {[r.value for r in roles]}",
        )


# ─── Role Permission Matrix ───────────────────────────────────────────────────

ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: {
        "manage_users": True,
        "view_all_clients": True,
        "manage_settings": True,
        "manage_workflows": True,
        "delete_records": True,
        "export_data": True,
        "view_audit_log": True,
    },
    UserRole.ADMIN: {
        "manage_users": False,
        "view_all_clients": True,
        "manage_settings": True,
        "manage_workflows": True,
        "delete_records": True,
        "export_data": True,
        "view_audit_log": True,
    },
    UserRole.MANAGER: {
        "manage_users": False,
        "view_all_clients": True,
        "manage_settings": False,
        "manage_workflows": False,
        "delete_records": False,
        "export_data": True,
        "view_audit_log": False,
    },
    UserRole.STAFF: {
        "manage_users": False,
        "view_all_clients": False,    # Only own clients
        "manage_settings": False,
        "manage_workflows": False,
        "delete_records": False,
        "export_data": True,
        "view_audit_log": False,
    },
    UserRole.VIEWER: {
        "manage_users": False,
        "view_all_clients": True,
        "manage_settings": False,
        "manage_workflows": False,
        "delete_records": False,
        "export_data": False,
        "view_audit_log": False,
    },
}


def can(user: UserAccount, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(user.role, {})
    return perms.get(permission, False)


# ─── Audit Logging ────────────────────────────────────────────────────────────

def log_action(
    db: Session,
    action: str,
    user: Optional[UserAccount] = None,
    resource: str = None,
    resource_id: str = None,
    details: dict = None,
    ip: str = None,
):
    entry = AuditLog(
        user_id=user.id if user else None,
        user_email=user.email if user else "system",
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id else None,
        details=details,
        ip_address=ip,
    )
    db.add(entry)
    db.commit()


# ─── Bootstrap: Create Super Admin ────────────────────────────────────────────

def ensure_super_admin(db: Session):
    """
    Called on startup. Creates the default super admin account
    if no super_admin exists.
    Default credentials:
      email: admin@taxly.com
      password: Admin@1234 (must change on first login)
    """
    existing = db.query(UserAccount).filter(
        UserAccount.role == UserRole.SUPER_ADMIN
    ).first()
    if existing:
        return

    pwd_hash, salt = hash_password("Admin@1234")
    admin = UserAccount(
        name="System Administrator",
        email="admin@taxly.com",
        role=UserRole.SUPER_ADMIN,
        password_hash=pwd_hash,
        password_salt=salt,
        is_active=True,
        must_change_pwd=True,
    )
    db.add(admin)
    db.commit()
    print("✅ Default Super Admin created: admin@taxly.com / Admin@1234")

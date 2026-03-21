"""Auth Pydantic schemas."""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.models import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class UserCreateRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    role: UserRole = UserRole.STAFF
    staff_id: Optional[int] = None
    password: Optional[str] = None   # If blank, auto-generates


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    staff_id: Optional[int] = None


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    role: UserRole
    is_active: bool
    must_change_pwd: bool
    last_login: Optional[datetime]
    login_count: int
    staff_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}

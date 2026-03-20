"""
Utility service: Client ID generation and staff assignment
"""

from sqlalchemy.orm import Session
from datetime import datetime
from app.models.models import Staff, Client


def generate_client_id(db: Session) -> str:
    """
    Generate unique Client ID in format: CA-YYYY-NNN
    e.g., CA-2024-001, CA-2024-002
    """
    year = datetime.now().year
    # Count clients created this year
    count = db.query(Client).filter(
        Client.client_id.like(f"CA-{year}-%")
    ).count()
    return f"CA-{year}-{(count + 1):03d}"


def assign_staff_by_workload(db: Session) -> int | None:
    """
    Assign staff member with least number of active clients.
    Returns staff ID or None if no staff available.
    """
    staff_members = db.query(Staff).filter(Staff.is_active == True).all()
    if not staff_members:
        return None

    # Find staff with minimum client count
    min_staff = min(staff_members, key=lambda s: len(s.clients))
    return min_staff.id

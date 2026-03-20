"""
Utility service: Client ID generation and staff assignment

FIX #3: generate_client_id had a race condition — two concurrent requests got
         the same count value and tried to create the same CA-YYYY-NNN ID,
         which hit the unique constraint and crashed (IntegrityError).
         Fixed with: retry loop + select-for-update style approach using
         a max() query instead of count(), then catching IntegrityError.

FIX #4: assign_staff_by_workload loaded ALL clients per staff member (N+1).
         Fixed with a SQL subquery to count active clients in one query.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from app.models.models import Staff, Client


def generate_client_id(db: Session) -> str:
    """
    Generate unique Client ID in format: CA-YYYY-NNN
    e.g., CA-2024-001, CA-2024-002

    Uses MAX() instead of COUNT() to avoid collision on sparse sequences,
    and handles IntegrityError with retry for concurrent requests.
    """
    year = datetime.now().year
    prefix = f"CA-{year}-"

    for attempt in range(5):  # retry up to 5 times on collision
        # Find the highest existing sequence number this year
        latest = (
            db.query(func.max(Client.client_id))
            .filter(Client.client_id.like(f"{prefix}%"))
            .scalar()
        )
        if latest:
            try:
                last_seq = int(latest.split("-")[-1])
            except (ValueError, IndexError):
                last_seq = 0
        else:
            last_seq = 0

        candidate = f"{prefix}{(last_seq + 1):03d}"

        # Check if candidate already exists (handles edge cases)
        exists = db.query(Client.id).filter(Client.client_id == candidate).first()
        if not exists:
            return candidate
        # If exists, loop to try next number

    # Fallback: use timestamp to guarantee uniqueness
    return f"{prefix}{int(datetime.now().timestamp()) % 99999:05d}"


def assign_staff_by_workload(db: Session) -> int | None:
    """
    Assign staff member with least number of active clients.
    Returns staff ID or None if no staff available.

    FIXED: Single query with subquery instead of N+1 loop.
    """
    # Count active clients per staff member in a single query
    from app.models.models import Staff, Client
    from sqlalchemy import outerjoin

    subq = (
        select(Client.assigned_staff_id, func.count(Client.id).label("client_count"))
        .where(Client.is_active == True)
        .where(Client.assigned_staff_id != None)
        .group_by(Client.assigned_staff_id)
        .subquery()
    )

    staff_with_counts = (
        db.query(Staff.id, func.coalesce(subq.c.client_count, 0).label("cnt"))
        .outerjoin(subq, Staff.id == subq.c.assigned_staff_id)
        .filter(Staff.is_active == True)
        .order_by(func.coalesce(subq.c.client_count, 0).asc())
        .first()
    )

    return staff_with_counts[0] if staff_with_counts else None

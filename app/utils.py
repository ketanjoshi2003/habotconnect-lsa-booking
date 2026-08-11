"""
Utility helpers: validation, reference generation, overlap checking.

Centralised here so routes stay thin and testable.
"""

from datetime import date, time
from app import db
from app.models import BookingRequest


def generate_booking_reference():
    """Generate a human-readable booking reference: HB-YYYYMMDD-XXXX."""
    today = date.today().strftime("%Y%m%d")
    prefix = f"HB-{today}-"
    # Count today's bookings to get the next sequence number
    count = BookingRequest.query.filter(
        BookingRequest.reference.like(f"{prefix}%")
    ).count()
    return f"{prefix}{count + 1:04d}"


def validate_time_range(start_time, end_time):
    """Ensure start_time < end_time and both are valid time objects."""
    if not start_time or not end_time:
        return False, "Both start_time and end_time are required."
    if start_time >= end_time:
        return False, "start_time must be earlier than end_time."
    return True, None


def check_booking_overlap(lsa_id, session_date, start_time, end_time, exclude_id=None):
    """
    Check for overlapping bookings for the same LSA on the same date.

    Uses a single indexed query (idx_booking_overlap) to detect:
        WHERE lsa_id = ? AND session_date = ?
          AND start_time < proposed_end AND end_time > proposed_start

    This is the N+1-prevention core: one query, not one-per-booking.

    Returns True if an overlap is found, False otherwise.
    """
    query = BookingRequest.query.filter(
        BookingRequest.lsa_id == lsa_id,
        BookingRequest.session_date == session_date,
        BookingRequest.start_time < end_time,
        BookingRequest.end_time > start_time,
        # Only active statuses conflict (not cancelled/failed)
        BookingRequest.booking_status.in_([
            BookingRequest.STATUS_PENDING,
            BookingRequest.STATUS_CONFIRMED,
        ]),
    )
    if exclude_id:
        query = query.filter(BookingRequest.id != exclude_id)

    existing = query.first()
    return existing is not None

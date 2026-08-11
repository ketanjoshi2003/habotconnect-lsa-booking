"""
Booking API endpoints.

POST /api/v1/bookings/   — Create a new booking (with double-booking prevention)
GET  /api/v1/bookings/   — List all bookings
GET  /api/v1/bookings/<id>/ — Retrieve a single booking by ID
"""

from flask import Blueprint, request, jsonify
from app import db
from app.models import BookingRequest, Parent, LSAProfile
from app.utils import generate_booking_reference, validate_time_range, check_booking_overlap
from app.services.mock_payment import MockPaymentService
from datetime import datetime, date

bookings_bp = Blueprint("bookings", __name__)


@bookings_bp.route("/bookings/", methods=["POST"])
def create_booking():
    """
    Create a new booking request.

    Payload:
        {
            "parent_id": 1,
            "lsa_id": 2,
            "session_date": "2026-08-15",
            "start_time": "10:00",
            "end_time": "12:00",
            "notes": "Optional notes"
        }

    The endpoint:
      1. Validates payload (required fields, types)
      2. Checks that parent and LSA exist
      3. Validates time range (start < end)
      4. Checks for overlapping bookings (double-booking prevention)
      5. Creates the booking record
      6. Initiates payment via mock gateway
      7. Returns the created booking with 201 status

    Returns:
        201 — booking created successfully
        400 — validation error (missing fields, bad data, overlap)
        404 — parent or LSA not found
        500 — internal server error
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON", "code": 400}), 400

    # --- Required field validation ---
    required = ["parent_id", "lsa_id", "session_date", "start_time", "end_time"]
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return jsonify({
            "error": f"Missing required fields: {', '.join(missing)}",
            "code": 400,
        }), 400

    # --- Parse and validate data types ---
    try:
        parent_id = int(data["parent_id"])
        lsa_id = int(data["lsa_id"])
        session_date = datetime.strptime(data["session_date"], "%Y-%m-%d").date()
        start_time = datetime.strptime(data["start_time"], "%H:%M").time()
        end_time = datetime.strptime(data["end_time"], "%H:%M").time()
    except (ValueError, TypeError) as e:
        return jsonify({
            "error": f"Invalid data format: {str(e)}",
            "code": 400,
        }), 400

    # --- Validate time range ---
    valid, msg = validate_time_range(start_time, end_time)
    if not valid:
        return jsonify({"error": msg, "code": 400}), 400

    # --- Verify parent exists ---
    parent = db.session.get(Parent, parent_id)
    if not parent:
        return jsonify({"error": f"Parent with id {parent_id} not found", "code": 404}), 404

    if not parent.is_active:
        return jsonify({"error": "Parent account is inactive", "code": 400}), 400

    # --- Verify LSA exists ---
    lsa = db.session.get(LSAProfile, lsa_id)
    if not lsa:
        return jsonify({"error": f"LSA with id {lsa_id} not found", "code": 404}), 404

    if not lsa.is_active:
        return jsonify({"error": "LSA is not currently available", "code": 400}), 400

    # --- Double-booking prevention (N+1-safe single query) ---
    if check_booking_overlap(lsa_id, session_date, start_time, end_time):
        return jsonify({
            "error": "Booking conflict: LSA already has a session in this time slot",
            "code": 409,
            "conflict": True,
        }), 409

    # --- Calculate amount (hourly_rate × hours) ---
    from datetime import timedelta
    duration_hours = (
        datetime.combine(date.min, end_time) - datetime.combine(date.min, start_time)
    ).total_seconds() / 3600
    amount = float(lsa.hourly_rate) * duration_hours

    # --- Create booking ---
    booking = BookingRequest(
        reference=generate_booking_reference(),
        parent_id=parent_id,
        lsa_id=lsa_id,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        amount=amount,
        currency="AED",
        notes=data.get("notes"),
        booking_status=BookingRequest.STATUS_PENDING,
        payment_status=BookingRequest.PAYMENT_PENDING,
    )

    db.session.add(booking)
    db.session.flush()  # Get the booking ID without committing

    # --- Initiate mock payment ---
    try:
        payment_service = MockPaymentService()
        payment_result = payment_service.initiate_payment(
            booking_id=booking.id,
            reference=booking.reference,
            amount=amount,
            currency="AED",
        )
        booking.payment_reference = payment_result.get("payment_id")
    except Exception as e:
        # Log the error but don't fail the booking — payment can be retried
        booking.payment_status = BookingRequest.PAYMENT_FAILED
        booking.payment_reference = None
        app_logger = __import__("logging").getLogger(__name__)
        app_logger.error(f"Payment initiation failed for booking {booking.reference}: {e}")

    db.session.commit()

    return jsonify(booking.to_dict()), 201


@bookings_bp.route("/bookings/", methods=["GET"])
def list_bookings():
    """
    List all bookings with optional status filter.

    Query params:
        ?status=pending|confirmed|completed|cancelled|failed
        ?lsa_id=1
        ?parent_id=1

    Returns:
        200 — list of bookings
    """
    query = BookingRequest.query

    status = request.args.get("status")
    if status:
        query = query.filter(BookingRequest.booking_status == status)

    lsa_id = request.args.get("lsa_id", type=int)
    if lsa_id:
        query = query.filter(BookingRequest.lsa_id == lsa_id)

    parent_id = request.args.get("parent_id", type=int)
    if parent_id:
        query = query.filter(BookingRequest.parent_id == parent_id)

    # Order by most recent first
    bookings = query.order_by(BookingRequest.created_at.desc()).all()
    return jsonify([b.to_dict() for b in bookings]), 200


@bookings_bp.route("/bookings/<int:booking_id>/", methods=["GET"])
def get_booking(booking_id):
    """Retrieve a single booking by ID."""
    booking = db.session.get(BookingRequest, booking_id)
    if not booking:
        return jsonify({"error": f"Booking with id {booking_id} not found", "code": 404}), 404
    return jsonify(booking.to_dict()), 200

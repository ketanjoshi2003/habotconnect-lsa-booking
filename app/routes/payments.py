"""
Payment webhook endpoint + mock payment gateway.

POST /api/v1/payments/webhook/   — Receives payment success/failure events
POST /api/v1/payments/mock-gateway/ — Mock payment gateway (simulates external service)
"""

from flask import Blueprint, request, jsonify
from app import db
from app.models import BookingRequest
import requests
import logging

payments_bp = Blueprint("payments", __name__)
logger = logging.getLogger(__name__)


@payments_bp.route("/payments/webhook/", methods=["POST"])
def payment_webhook():
    """
    Webhook endpoint that listens for payment success/failure events
    from the payment gateway and dynamically transitions booking states.

    Expected payload (from payment gateway):
        {
            "payment_id": "pay_abc123",
            "booking_reference": "HB-20260811-0001",
            "status": "success" | "failed",
            "amount": 150.00,
            "currency": "AED"
        }

    State transitions:
        payment success → booking_status: confirmed, payment_status: payment_success
        payment failed  → booking_status: failed,   payment_status: payment_failed
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON", "code": 400}), 400

    # --- Validate required fields ---
    required = ["payment_id", "booking_reference", "status"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({
            "error": f"Missing required fields: {', '.join(missing)}",
            "code": 400,
        }), 400

    booking_reference = data["booking_reference"]
    payment_status = data["status"].lower()
    payment_id = data["payment_id"]

    # --- Find the booking ---
    booking = BookingRequest.query.filter_by(reference=booking_reference).first()
    if not booking:
        return jsonify({
            "error": f"Booking with reference {booking_reference} not found",
            "code": 404,
        }), 404

    # --- Idempotency check: don't process a webhook twice ---
    if booking.payment_reference == payment_id and booking.payment_status in [
        BookingRequest.PAYMENT_SUCCESS,
        BookingRequest.PAYMENT_FAILED,
    ]:
        return jsonify({
            "message": "Webhook already processed (idempotent)",
            "booking_reference": booking.reference,
            "status": booking.booking_status,
        }), 200

    # --- Record the payment_id for idempotency tracking ---
    booking.payment_reference = payment_id

    # --- Dynamic state transition based on payment event ---
    if payment_status == "success":
        booking.booking_status = BookingRequest.STATUS_CONFIRMED
        booking.payment_status = BookingRequest.PAYMENT_SUCCESS
        logger.info(f"Payment success for booking {booking.reference}")
    elif payment_status == "failed":
        booking.booking_status = BookingRequest.STATUS_FAILED
        booking.payment_status = BookingRequest.PAYMENT_FAILED
        logger.warning(f"Payment failed for booking {booking.reference}")
    else:
        return jsonify({
            "error": f"Unknown payment status: {payment_status}. Expected 'success' or 'failed'",
            "code": 400,
        }), 400

    db.session.commit()

    return jsonify({
        "message": f"Booking {booking.reference} updated to {booking.booking_status}",
        "booking_reference": booking.reference,
        "booking_status": booking.booking_status,
        "payment_status": booking.payment_status,
    }), 200


@payments_bp.route("/payments/mock-gateway/", methods=["POST"])
def mock_payment_gateway():
    """
    Mock external payment gateway endpoint.

    In production, this would be replaced by a real gateway (Stripe, Razorpay, etc.).
    For this simulation, it always returns 'success' unless ?force_fail=1 is passed.

    This demonstrates the Third-Party Mock Integration requirement:
    the booking flow calls this endpoint via Python's `requests` library
    with proper exception handling and logging.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body", "code": 400}), 400

    force_fail = request.args.get("force_fail", default="0") == "1"

    import uuid
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"

    if force_fail:
        return jsonify({
            "payment_id": payment_id,
            "status": "failed",
            "message": "Payment declined (forced failure for testing)",
            "amount": data.get("amount"),
            "currency": data.get("currency"),
        }), 200

    return jsonify({
        "payment_id": payment_id,
        "status": "success",
        "message": "Payment processed successfully (mock)",
        "amount": data.get("amount"),
        "currency": data.get("currency"),
    }), 200

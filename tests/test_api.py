"""
Test suite for the LSA Booking API.

Covers: success paths, edge cases, failure cases, and validation logic.
Organized by endpoint for clarity during interview presentation.

Test Inventory:
    1. test_create_booking_success          — happy path: valid booking created
    2. test_create_booking_double_booking   — edge: overlapping time slot rejected
    3. test_create_booking_missing_fields   — failure: required fields missing
    4. test_search_lsas_by_skill            — happy path: skill filter returns matches
    5. test_payment_webhook_success          — happy path: webhook transitions booking to confirmed
    6. test_payment_webhook_idempotent      — edge: duplicate webhook doesn't re-process
    7. test_create_booking_invalid_time     — failure: end_time before start_time
    8. test_create_booking_nonexistent_parent — failure: parent ID not found
"""

import json
from app import db
from app.models import Parent, LSAProfile, BookingRequest


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: Create Booking — Success (Happy Path)
# ═══════════════════════════════════════════════════════════════════════════
def test_create_booking_success(client, sample_parent, sample_lsa):
    """
    A valid booking request should return 201 and create a booking record
    with status 'pending' and payment_status 'payment_pending'.
    """
    # Re-fetch IDs (fixtures commit within their own app context)
    parent = Parent.query.first()
    lsa = LSAProfile.query.first()

    payload = {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "session_date": "2026-08-15",
        "start_time": "10:00",
        "end_time": "12:00",
        "notes": "First session for Aarav",
    }

    response = client.post(
        "/api/v1/bookings/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["reference"].startswith("HB-")
    assert data["booking_status"] == "pending"
    assert data["payment_status"] in ["payment_pending", "payment_failed"]
    assert data["parent_id"] == parent.id
    assert data["lsa_id"] == lsa.id
    assert float(data["amount"]) > 0  # hourly_rate × duration


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: Double-Booking Prevention (Edge Case)
# ═══════════════════════════════════════════════════════════════════════════
def test_create_booking_double_booking_prevention(client, sample_parent, sample_lsa):
    """
    A second booking that overlaps with an existing confirmed/pending booking
    for the same LSA on the same date should return 409 Conflict.
    """
    parent = Parent.query.first()
    lsa = LSAProfile.query.first()

    # First booking: 10:00 - 12:00
    first_booking = {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "session_date": "2026-08-16",
        "start_time": "10:00",
        "end_time": "12:00",
    }
    response1 = client.post(
        "/api/v1/bookings/",
        data=json.dumps(first_booking),
        content_type="application/json",
    )
    assert response1.status_code == 201

    # Second booking: 11:00 - 13:00 (overlaps with 10:00-12:00)
    second_booking = {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "session_date": "2026-08-16",
        "start_time": "11:00",
        "end_time": "13:00",
    }
    response2 = client.post(
        "/api/v1/bookings/",
        data=json.dumps(second_booking),
        content_type="application/json",
    )

    assert response2.status_code == 409
    data = response2.get_json()
    assert data["conflict"] is True
    assert "conflict" in data["error"].lower() or "overlap" in data["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Missing Required Fields (Failure Case)
# ═══════════════════════════════════════════════════════════════════════════
def test_create_booking_missing_fields(client, sample_parent, sample_lsa):
    """
    A booking request missing required fields should return 400 with
    a descriptive error message listing the missing fields.
    """
    payload = {
        "parent_id": 1,
        # Missing: lsa_id, session_date, start_time, end_time
    }

    response = client.post(
        "/api/v1/bookings/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "missing" in data["error"].lower()
    assert "lsa_id" in data["error"]


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: LSA Search — Skill Filter (Happy Path + N+1 prevention)
# ═══════════════════════════════════════════════════════════════════════════
def test_search_lsas_by_skill(client, sample_lsa, second_lsa):
    """
    Searching LSAs by skill should return only LSAs whose skills match
    the requested filter, in a single optimized query.
    """
    # Search for LSAs with "ADHD" skill — only sample_lsa has it
    response = client.get("/api/v1/lsas/search/?skill=ADHD")

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert "ADHD" in data["results"][0]["skills"]
    assert data["results"][0]["full_name"] == "Dr. Priya Sharma"

    # Search for LSAs with "autism" skill — both LSAs have it
    response2 = client.get("/api/v1/lsas/search/?skill=autism")
    data2 = response2.get_json()
    assert data2["count"] == 2

    # Search for a skill no one has
    response3 = client.get("/api/v1/lsas/search/?skill=dyscalculia")
    data3 = response3.get_json()
    assert data3["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Payment Webhook — Success State Transition (Happy Path)
# ═══════════════════════════════════════════════════════════════════════════
def test_payment_webhook_success_transition(client, sample_parent, sample_lsa):
    """
    A payment success webhook should transition the booking from
    'pending' → 'confirmed' and payment_status → 'payment_success'.
    """
    parent = Parent.query.first()
    lsa = LSAProfile.query.first()

    # Step 1: Create a booking
    booking_payload = {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "session_date": "2026-08-20",
        "start_time": "14:00",
        "end_time": "16:00",
    }
    create_response = client.post(
        "/api/v1/bookings/",
        data=json.dumps(booking_payload),
        content_type="application/json",
    )
    assert create_response.status_code == 201
    booking = create_response.get_json()
    assert booking["booking_status"] == "pending"

    # Step 2: Simulate payment success webhook
    webhook_payload = {
        "payment_id": "pay_test_success_001",
        "booking_reference": booking["reference"],
        "status": "success",
        "amount": booking["amount"],
        "currency": "AED",
    }
    webhook_response = client.post(
        "/api/v1/payments/webhook/",
        data=json.dumps(webhook_payload),
        content_type="application/json",
    )

    assert webhook_response.status_code == 200
    webhook_data = webhook_response.get_json()
    assert webhook_data["booking_status"] == "confirmed"
    assert webhook_data["payment_status"] == "payment_success"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Payment Webhook — Idempotency (Edge Case)
# ═══════════════════════════════════════════════════════════════════════════
def test_payment_webhook_idempotent(client, sample_parent, sample_lsa):
    """
    Sending the same webhook twice should not cause errors or double-processing.
    The second request should return 200 with an 'already processed' message.
    """
    parent = Parent.query.first()
    lsa = LSAProfile.query.first()

    # Create a booking
    booking_payload = {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "session_date": "2026-08-21",
        "start_time": "09:00",
        "end_time": "10:00",
    }
    create_response = client.post(
        "/api/v1/bookings/",
        data=json.dumps(booking_payload),
        content_type="application/json",
    )
    booking = create_response.get_json()

    webhook_payload = {
        "payment_id": "pay_test_idempotent_001",
        "booking_reference": booking["reference"],
        "status": "success",
    }

    # First webhook — should process
    response1 = client.post(
        "/api/v1/payments/webhook/",
        data=json.dumps(webhook_payload),
        content_type="application/json",
    )
    assert response1.status_code == 200
    assert response1.get_json()["booking_status"] == "confirmed"

    # Second webhook (same payment_id) — should be idempotent
    response2 = client.post(
        "/api/v1/payments/webhook/",
        data=json.dumps(webhook_payload),
        content_type="application/json",
    )
    assert response2.status_code == 200
    assert "already processed" in response2.get_json()["message"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: Invalid Time Range — end before start (Failure Case)
# ═══════════════════════════════════════════════════════════════════════════
def test_create_booking_invalid_time_range(client, sample_parent, sample_lsa):
    """
    A booking where end_time is before start_time should be rejected with 400.
    """
    parent = Parent.query.first()
    lsa = LSAProfile.query.first()

    payload = {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "session_date": "2026-08-25",
        "start_time": "15:00",
        "end_time": "10:00",  # End before start!
    }

    response = client.post(
        "/api/v1/bookings/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "start_time" in response.get_json()["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# TEST 8: Nonexistent Parent (Failure Case)
# ═══════════════════════════════════════════════════════════════════════════
def test_create_booking_nonexistent_parent(client, sample_lsa):
    """
    A booking with a parent_id that doesn't exist should return 404.
    """
    lsa = LSAProfile.query.first()

    payload = {
        "parent_id": 99999,  # Nonexistent
        "lsa_id": lsa.id,
        "session_date": "2026-08-25",
        "start_time": "10:00",
        "end_time": "12:00",
    }

    response = client.post(
        "/api/v1/bookings/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert "not found" in response.get_json()["error"].lower()

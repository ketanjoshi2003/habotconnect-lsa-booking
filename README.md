# LSA Service Booking API — HabotConnect Hiring Project

**Candidate:** Ketan Joshi
**Email:** ketanjoshi2003@gmail.com
**Phone:** +91 9773461815
**GitHub:** github.com/ketanjoshi2003
**Date:** August 2026

---

## Project Overview

A production-ready RESTful API backend for an LSA (Learning Support Assistant) booking platform. Parents can search for LSAs by skill, book sessions with double-booking prevention, and process payments through a mock payment gateway with webhook-driven state transitions.

Built with **Flask** (MVC architecture), **SQLAlchemy ORM**, and **PostgreSQL/SQLite**.

---

## Why Flask (MVC) over Django (MVT)?

This project uses **Flask with the MVC (Model-View-Controller) pattern** rather than Django's MVT (Model-View-Template). The decision is based on the following rationale:

| Factor | Flask (MVC) | Django (MVT) |
|--------|-------------|--------------|
| Architecture | Explicit: Models, Views (routes), Controllers (service logic) | Convention: Models, Views (view functions), Templates |
| Flexibility | Unopinionated — you choose every component | Opinionated — batteries included but rigid |
| ORM | SQLAlchemy (industry standard, works with any DB) | Django ORM (tightly coupled to Django) |
| API Focus | Lightweight, perfect for REST APIs | Heavier, includes admin/templating we don't need |
| Testability | Simple app factory, easy to mock | More setup required for isolated tests |

**Key insight:** For a pure REST API with no server-rendered templates, Flask's MVC pattern provides a cleaner separation of concerns. The "View" in MVC is the JSON response (not an HTML template), and the "Controller" is the route handler that orchestrates model operations. This maps directly to how modern APIs are structured.

---

## Architecture

```
habotconnect-lsa-booking/
├── app/
│   ├── __init__.py          # Application factory (create_app)
│   ├── models.py            # SQLAlchemy models (Parent, LSAProfile, BookingRequest)
│   ├── utils.py             # Validation & overlap-checking helpers
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── bookings.py      # POST/GET /api/v1/bookings/
│   │   ├── lsas.py          # GET /api/v1/lsas/search/
│   │   └── payments.py      # POST /api/v1/payments/webhook/ + mock gateway
│   └── services/
│       ├── __init__.py
│       └── mock_payment.py  # MockPaymentService (requests library integration)
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   └── test_api.py          # 8 test cases (success, edge, failure)
├── .github/workflows/
│   └── ci.yml               # GitHub Actions CI/CD pipeline
├── config.py                # Config classes (dev + test)
├── run.py                   # Entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Database Schema

### Entity Relationship

```
Parent (1) ──────── (∞) Booking_Request (∞) ──────── (1) LSA_Profile
```

### Tables

**parents**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PK, Auto-increment |
| full_name | String(150) | NOT NULL, Indexed |
| email | String(255) | NOT NULL, UNIQUE, Indexed |
| phone | String(20) | NOT NULL |
| child_name | String(150) | NOT NULL |
| child_age | Integer | Nullable |
| learning_needs | JSON | Default [] |
| is_active | Boolean | Default True |
| created_at | DateTime | Default UTC now |
| updated_at | DateTime | Auto-update on change |

**lsa_profiles**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PK, Auto-increment |
| full_name | String(150) | NOT NULL, Indexed |
| email | String(255) | NOT NULL, UNIQUE, Indexed |
| phone | String(20) | NOT NULL |
| skills | JSON | NOT NULL, Default [] |
| hourly_rate | Numeric(10,2) | NOT NULL |
| bio | Text | Nullable |
| availability | JSON | Default {} |
| is_verified | Boolean | Default False |
| is_active | Boolean | Default True |
| rating_avg | Float | Default 0.0 |
| total_sessions | Integer | Default 0 |
| created_at | DateTime | Default UTC now |
| updated_at | DateTime | Auto-update on change |

**booking_requests**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PK, Auto-increment |
| reference | String(50) | UNIQUE, NOT NULL, Indexed |
| parent_id | Integer | FK → parents.id, Indexed |
| lsa_id | Integer | FK → lsa_profiles.id, Indexed |
| session_date | Date | NOT NULL, Indexed |
| start_time | Time | NOT NULL |
| end_time | Time | NOT NULL |
| booking_status | String(20) | Default "pending" |
| payment_status | String(20) | Default "payment_pending" |
| payment_reference | String(100) | Nullable |
| amount | Numeric(10,2) | NOT NULL |
| currency | String(3) | Default "AED" |
| notes | Text | Nullable |
| created_at | DateTime | Default UTC now |
| updated_at | DateTime | Auto-update on change |

**Composite Index:** `idx_booking_overlap` on (lsa_id, session_date, start_time, end_time) — used by the double-booking prevention query for O(log n) lookup.

---

## Query Optimization — N+1 Problem Prevention

### The N+1 Problem

The naive approach to searching LSAs by skill:

```python
# BAD: N+1 queries
lsas = LSAProfile.query.all()          # 1 query
for lsa in lsas:                       # N queries
    if "ADHD" in lsa.skills:           # lazy-loaded per row
        results.append(lsa)
# Total: 1 + N queries
```

This is the classic N+1 problem — one query to fetch all rows, then N additional queries (or in-memory operations) to access related data.

### Our Solution: Single Database-Level Query

```python
# GOOD: 1 query, database-side filtering
query = LSAProfile.query.filter(
    LSAProfile.is_active == True,
    LSAProfile.skills.contains("ADHD")  # JSON containment at DB level
)
lsas = query.limit(limit).all()         # 1 query total
```

**Key optimizations:**
1. **JSON containment** (`skills.contains()`) pushes the skill filter to the database — only matching rows are fetched.
2. **No lazy loading** — `to_dict()` accesses only already-loaded columns.
3. **Composite index** on `booking_requests(lsa_id, session_date, start_time, end_time)` makes the overlap check a single indexed lookup instead of scanning all bookings.
4. **`selectinload` / `joinedload`** available for relationship loading if needed (not required here since we avoid traversing relationships in the hot path).

### Double-Booking Prevention Query

```sql
SELECT * FROM booking_requests
WHERE lsa_id = :lsa_id
  AND session_date = :date
  AND start_time < :proposed_end
  AND end_time > :proposed_start
  AND booking_status IN ('pending', 'confirmed')
```

This uses the composite index `idx_booking_overlap` for efficient lookup. The logic: two time ranges overlap if and only if one starts before the other ends AND ends after the other starts.

---

## API Endpoints

### 1. POST /api/v1/bookings/

Create a new booking request with double-booking prevention.

**Request:**
```json
{
    "parent_id": 1,
    "lsa_id": 2,
    "session_date": "2026-08-15",
    "start_time": "10:00",
    "end_time": "12:00",
    "notes": "Optional notes"
}
```

**Response (201):**
```json
{
    "id": 1,
    "reference": "HB-20260811-0001",
    "parent_id": 1,
    "lsa_id": 2,
    "session_date": "2026-08-15",
    "start_time": "10:00:00",
    "end_time": "12:00:00",
    "booking_status": "pending",
    "payment_status": "payment_pending",
    "amount": 150.00,
    "currency": "AED"
}
```

**Error Responses:**
- `400` — Missing fields, invalid data format, start_time >= end_time
- `404` — Parent or LSA not found
- `409` — Double-booking conflict (overlapping time slot)

### 2. GET /api/v1/bookings/

List all bookings. Optional filters: `?status=pending&lsa_id=1&parent_id=1`

**Response (200):**
```json
[
    {"id": 1, "reference": "HB-20260811-0001", ...}
]
```

### 3. GET /api/v1/bookings/<id>/

Retrieve a single booking by ID.

### 4. GET /api/v1/lsas/search/

Search for LSAs by skill with N+1-safe querying.

**Query Parameters:**
- `?skill=ADHD` — filter by skill (repeatable: `?skill=ADHD&skill=dyslexia`)
- `?min_rating=4.0` — minimum average rating
- `?sort=rating` — sort by rating (desc) or rate (asc)
- `?limit=20` — max results (default 50, max 100)

**Response (200):**
```json
{
    "count": 2,
    "results": [
        {"id": 1, "full_name": "Dr. Priya Sharma", "skills": ["ADHD", "dyslexia"], ...}
    ]
}
```

### 5. POST /api/v1/payments/webhook/

Webhook endpoint for payment gateway callbacks. Transitions booking state based on payment events.

**Request:**
```json
{
    "payment_id": "pay_abc123",
    "booking_reference": "HB-20260811-0001",
    "status": "success",
    "amount": 150.00,
    "currency": "AED"
}
```

**State Transitions:**
| Payment Status | Booking Status | Payment Status |
|---------------|---------------|----------------|
| success | confirmed | payment_success |
| failed | failed | payment_failed |

**Idempotency:** Duplicate webhooks with the same `payment_id` are safely ignored.

### 6. POST /api/v1/payments/mock-gateway/

Mock payment gateway endpoint (simulates Stripe/Razorpay). Use `?force_fail=1` to simulate a payment failure.

---

## Mock Payment Integration

The `MockPaymentService` class wraps calls to the (mock) payment gateway using Python's `requests` library with:

- **Timeout handling** (10 second timeout)
- **Connection error handling** (network failures)
- **HTTP error handling** (non-2xx responses)
- **Structured logging** for every payment attempt (info + error levels)
- **Configurable endpoint** via environment variable (`PAYMENT_GATEWAY_URL`)

To switch to a real payment gateway in production, simply change the `PAYMENT_GATEWAY_URL` environment variable — no code changes needed.

---

## Test Suite

8 automated tests using `pytest`, covering success, edge, and failure cases:

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | test_create_booking_success | Success | Valid booking creates record with 201 |
| 2 | test_create_booking_double_booking_prevention | Edge | Overlapping time slot returns 409 |
| 3 | test_create_booking_missing_fields | Failure | Missing required fields returns 400 |
| 4 | test_search_lsas_by_skill | Success | Skill filter returns correct LSAs |
| 5 | test_payment_webhook_success_transition | Success | Webhook transitions booking to confirmed |
| 6 | test_payment_webhook_idempotent | Edge | Duplicate webhook is safely ignored |
| 7 | test_create_booking_invalid_time_range | Failure | End before start returns 400 |
| 8 | test_create_booking_nonexistent_parent | Failure | Nonexistent parent returns 404 |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/ketanjoshi2003/habotconnect-lsa-booking.git
cd habotconnect-lsa-booking

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your configuration (defaults work for local dev)

# 5. Run the development server
python run.py
```

The API will be available at `http://localhost:5000`.

### Running Tests

```bash
# Run all tests with verbose output
python -m pytest tests/ -v

# Run a specific test
python -m pytest tests/test_api.py::test_create_booking_success -v

# Run with coverage (if pytest-cov installed)
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

### Database Migrations

```bash
# Initialize migrations (first time only)
flask db init

# Create a migration
flask db migrate -m "Initial schema"

# Apply migrations
flask db upgrade
```

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) automatically:

1. Triggers on every push or pull request to `main`/`master`
2. Sets up Python 3.12 on Ubuntu
3. Installs all dependencies
4. Runs the full pytest suite with verbose output
5. Uploads test results as an artifact on failure

---

## Tech Stack

- **Framework:** Flask 3.0 (MVC pattern)
- **ORM:** SQLAlchemy 2.0 + Flask-SQLAlchemy
- **Database:** SQLite (dev) / PostgreSQL (production-ready)
- **Migrations:** Flask-Migrate (Alembic)
- **Testing:** pytest + pytest-flask
- **CI/CD:** GitHub Actions
- **HTTP Client:** requests (for mock payment integration)
- **Configuration:** python-dotenv

---

## Design Decisions Summary

1. **Flask over Django:** Lightweight, explicit MVC, better fit for a pure REST API without templating overhead.
2. **JSON columns for skills/learning_needs:** Flexible schema for tag-based data, enables database-level filtering without JOIN tables.
3. **Composite index for overlap detection:** Single indexed query for double-booking check instead of scanning all bookings.
4. **Idempotent webhook processing:** Prevents double-processing when payment gateways retry webhooks.
5. **Application factory pattern:** Enables clean test isolation with per-test database creation.
6. **Service layer for payments:** Separates external API integration from route logic, making it easy to swap gateways.

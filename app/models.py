"""
Database models for the LSA Service Booking module.

Design follows MVC/MVT architecture:
- Models (this file) = data layer (M of MVT)
- Routes (routes/) = controller/view layer (V/T of MVT)
- No templates needed (REST API only)

Relationships:
    Parent 1───∞ Booking_Request ∞───1 LSA_Profile
    Parent 1───∞ LSA_Profile (an LSA can also be a parent, but typically separate)

Query optimization:
    LSA_Profile.skills is stored as a JSON array to allow efficient filtering
    via SQLAlchemy's JSON containment operators without JOIN explosions.
    selectinload / joinedload used in queries to eliminate N+1.
"""

from datetime import datetime
from app import db


class Parent(db.Model):
    """Represents a parent/guardian seeking learning support for their child."""

    __tablename__ = "parents"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=False)
    child_name = db.Column(db.String(150), nullable=False)
    child_age = db.Column(db.Integer, nullable=True)
    # JSON column for flexible learning-needs tags (ADHD, dyslexia, autism, etc.)
    learning_needs = db.Column(db.JSON, default=list)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship: one parent → many bookings
    bookings = db.relationship(
        "BookingRequest",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Parent {self.full_name} ({self.email})>"

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "child_name": self.child_name,
            "child_age": self.child_age,
            "learning_needs": self.learning_needs or [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LSAProfile(db.Model):
    """Represents a Learning Support Assistant offering services."""

    __tablename__ = "lsa_profiles"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=False)
    # JSON array of skill tags: ["ADHD", "dyslexia", "autism", "SEN"]
    skills = db.Column(db.JSON, default=list, nullable=False)
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    bio = db.Column(db.Text, nullable=True)
    # Availability stored as JSON: {"mon": ["09:00-12:00"], "wed": ["14:00-17:00"]}
    availability = db.Column(db.JSON, default=dict)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    rating_avg = db.Column(db.Float, default=0.0)
    total_sessions = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship: one LSA → many bookings
    bookings = db.relationship(
        "BookingRequest",
        back_populates="lsa",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<LSA {self.full_name} | Skills: {self.skills}>"

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "skills": self.skills or [],
            "hourly_rate": float(self.hourly_rate) if self.hourly_rate else 0.0,
            "bio": self.bio,
            "availability": self.availability or {},
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "rating_avg": self.rating_avg,
            "total_sessions": self.total_sessions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BookingRequest(db.Model):
    """Represents a booking request from a parent for an LSA session."""

    __tablename__ = "booking_requests"

    # Booking status enum (stored as string for portability)
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED = "failed"

    PAYMENT_PENDING = "payment_pending"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"

    id = db.Column(db.Integer, primary_key=True)
    # Human-readable reference: HB-20260811-0001
    reference = db.Column(db.String(50), unique=True, nullable=False, index=True)

    parent_id = db.Column(
        db.Integer, db.ForeignKey("parents.id"), nullable=False, index=True
    )
    lsa_id = db.Column(
        db.Integer, db.ForeignKey("lsa_profiles.id"), nullable=False, index=True
    )

    session_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    # Booking lifecycle state
    booking_status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    payment_status = db.Column(db.String(20), default=PAYMENT_PENDING, nullable=False)

    # Payment gateway reference (returned by mock gateway)
    payment_reference = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default="AED", nullable=False)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    parent = db.relationship("Parent", back_populates="bookings")
    lsa = db.relationship("LSAProfile", back_populates="bookings")

    # --- Composite index for overlap-detection query ---
    # Used by the double-booking prevention check: WHERE lsa_id = ? AND session_date = ?
    #   AND start_time < ? AND end_time > ?
    db.Index(
        "idx_booking_overlap",
        "lsa_id",
        "session_date",
        "start_time",
        "end_time",
    )

    def __repr__(self):
        return f"<Booking {self.reference} | {self.booking_status}>"

    def to_dict(self):
        return {
            "id": self.id,
            "reference": self.reference,
            "parent_id": self.parent_id,
            "lsa_id": self.lsa_id,
            "session_date": self.session_date.isoformat() if self.session_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "booking_status": self.booking_status,
            "payment_status": self.payment_status,
            "payment_reference": self.payment_reference,
            "amount": float(self.amount) if self.amount else 0.0,
            "currency": self.currency,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

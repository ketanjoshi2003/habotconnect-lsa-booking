"""Initial schema: Parent, LSAProfile, BookingRequest

Revision ID: 0001
Revises:
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- parents table ---
    op.create_table(
        "parents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("child_name", sa.String(150), nullable=False),
        sa.Column("child_age", sa.Integer(), nullable=True),
        sa.Column("learning_needs", sa.JSON(), server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_parents_full_name", "parents", ["full_name"])
    op.create_index("ix_parents_email", "parents", ["email"])

    # --- lsa_profiles table ---
    op.create_table(
        "lsa_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("availability", sa.JSON(), server_default="{}"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("rating_avg", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lsa_profiles_full_name", "lsa_profiles", ["full_name"])
    op.create_index("ix_lsa_profiles_email", "lsa_profiles", ["email"])

    # --- booking_requests table ---
    op.create_table(
        "booking_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reference", sa.String(50), nullable=False, unique=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("parents.id"), nullable=False),
        sa.Column("lsa_id", sa.Integer(), sa.ForeignKey("lsa_profiles.id"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("booking_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="payment_pending"),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_booking_requests_reference", "booking_requests", ["reference"])
    op.create_index("ix_booking_requests_parent_id", "booking_requests", ["parent_id"])
    op.create_index("ix_booking_requests_lsa_id", "booking_requests", ["lsa_id"])
    op.create_index("ix_booking_requests_session_date", "booking_requests", ["session_date"])
    # Composite index for double-booking overlap detection
    op.create_index(
        "idx_booking_overlap",
        "booking_requests",
        ["lsa_id", "session_date", "start_time", "end_time"],
    )


def downgrade():
    op.drop_index("idx_booking_overlap", table_name="booking_requests")
    op.drop_index("ix_booking_requests_session_date", table_name="booking_requests")
    op.drop_index("ix_booking_requests_lsa_id", table_name="booking_requests")
    op.drop_index("ix_booking_requests_parent_id", table_name="booking_requests")
    op.drop_index("ix_booking_requests_reference", table_name="booking_requests")
    op.drop_table("booking_requests")

    op.drop_index("ix_lsa_profiles_email", table_name="lsa_profiles")
    op.drop_index("ix_lsa_profiles_full_name", table_name="lsa_profiles")
    op.drop_table("lsa_profiles")

    op.drop_index("ix_parents_email", table_name="parents")
    op.drop_index("ix_parents_full_name", table_name="parents")
    op.drop_table("parents")

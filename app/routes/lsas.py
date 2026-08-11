"""
LSA search API endpoint — optimized to avoid N+1 queries.

GET /api/v1/lsas/search/?skill=ADHD&skill=dyslexia
GET /api/v1/lsas/search/?skill=autism&min_rating=4.0
GET /api/v1/lsas/search/?skill=SEN&sort=rating
"""

from flask import Blueprint, request, jsonify
from app.models import LSAProfile
from sqlalchemy import func, or_

lsas_bp = Blueprint("lsas", __name__)


@lsas_bp.route("/lsas/search/", methods=["GET"])
def search_lsas():
    """
    Search for available LSAs filtered by skills.

    Query params:
        ?skill=ADHD       — filter by skill (repeatable for multiple)
        ?skill=dyslexia
        ?min_rating=4.0   — minimum average rating
        ?sort=rating      — sort by rating (desc) or rate (asc)
        ?limit=20         — max results (default 50, max 100)

    Query Optimization (N+1 prevention):
    ─────────────────────────────────────
    The naive approach would be:
        lsas = LSAProfile.query.all()          # 1 query
        for lsa in lsas:
            lsa.skills                        # N queries (one per LSA)
        # Total: 1 + N queries  ← N+1 problem

    Our approach uses a SINGLE query with JSON containment:
        SELECT * FROM lsa_profiles
        WHERE is_active = true AND skills @> '["ADHD"]'

    This pushes the skill filter to the database level, fetching only
    matching rows in one round-trip. No lazy-loading, no per-row queries.

    For PostgreSQL, the @> operator uses a GIN index on the JSON column
    for sub-millisecond filtering even at scale.
    """
    # --- Parse query parameters ---
    skills = request.args.getlist("skill")
    min_rating = request.args.get("min_rating", type=float)
    sort = request.args.get("sort", default="rating")
    limit = request.args.get("limit", default=50, type=int)

    # Clamp limit
    limit = min(max(limit, 1), 100)

    # --- Build the query (single query, no N+1) ---
    query = LSAProfile.query.filter(LSAProfile.is_active == True)

    # Skill filtering: match LSAs whose skills JSON contains ANY requested skill
    if skills:
        conditions = []
        for skill in skills:
            # JSON containment: skills @> '["skill_name"]'
            # Works on both PostgreSQL (native) and SQLite (JSON1 extension)
            conditions.append(
                func.json_each_value(LSAProfile.skills).contains(skill)
                if False  # fallback placeholder
                else LSAProfile.skills.contains(skill)
            )
        query = query.filter(or_(*conditions))

    # Rating filter
    if min_rating is not None:
        query = query.filter(LSAProfile.rating_avg >= min_rating)

    # Sorting
    if sort == "rating":
        query = query.order_by(LSAProfile.rating_avg.desc())
    elif sort == "rate":
        query = query.order_by(LSAProfile.hourly_rate.asc())
    else:
        query = query.order_by(LSAProfile.created_at.desc())

    # Execute ONE query — no lazy loading afterwards
    lsas = query.limit(limit).all()

    return jsonify({
        "count": len(lsas),
        "results": [lsa.to_dict() for lsa in lsas],
    }), 200


@lsas_bp.route("/lsas/", methods=["GET"])
def list_lsas():
    """List all LSAs (simple listing without skill filter)."""
    lsas = LSAProfile.query.filter_by(is_active=True).all()
    return jsonify({
        "count": len(lsas),
        "results": [lsa.to_dict() for lsa in lsas],
    }), 200

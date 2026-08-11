"""
Pytest fixtures and configuration.

Sets up an isolated in-memory SQLite database for each test session,
with a Flask test client for API testing.
"""

import pytest
from app import create_app, db
from app.models import Parent, LSAProfile
from config import TestConfig


@pytest.fixture(scope="function")
def app():
    """Create a fresh app + database for each test."""
    app = create_app("config.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Flask test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture(scope="function")
def sample_parent(app):
    """Insert a sample parent into the database."""
    with app.app_context():
        parent = Parent(
            full_name="Rajesh Kumar",
            email="rajesh@example.com",
            phone="+919876543210",
            child_name="Aarav Kumar",
            child_age=8,
            learning_needs=["ADHD", "dyslexia"],
        )
        db.session.add(parent)
        db.session.commit()
        return parent


@pytest.fixture(scope="function")
def sample_lsa(app):
    """Insert a sample LSA into the database."""
    with app.app_context():
        lsa = LSAProfile(
            full_name="Dr. Priya Sharma",
            email="priya@example.com",
            phone="+971501234567",
            skills=["ADHD", "dyslexia", "autism", "SEN"],
            hourly_rate=75.00,
            bio="Certified SEN specialist with 8 years experience.",
            availability={"mon": ["09:00-12:00"], "wed": ["14:00-17:00"]},
            is_verified=True,
            is_active=True,
            rating_avg=4.7,
            total_sessions=120,
        )
        db.session.add(lsa)
        db.session.commit()
        return lsa


@pytest.fixture(scope="function")
def second_lsa(app):
    """Insert a second LSA for search/filter tests."""
    with app.app_context():
        lsa = LSAProfile(
            full_name="Sarah Williams",
            email="sarah@example.com",
            phone="+971509876543",
            skills=["autism", "SEN"],
            hourly_rate=60.00,
            bio="Speech and language therapist.",
            is_verified=True,
            is_active=True,
            rating_avg=4.2,
            total_sessions=45,
        )
        db.session.add(lsa)
        db.session.commit()
        return lsa

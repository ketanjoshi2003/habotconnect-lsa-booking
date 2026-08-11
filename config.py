import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///habotconnect.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Mock payment gateway base URL (points to our own mock endpoint in dev)
    PAYMENT_GATEWAY_URL = os.environ.get(
        "PAYMENT_GATEWAY_URL", "http://localhost:5000/api/v1/payments/mock-gateway"
    )
    PAYMENT_GATEWAY_API_KEY = os.environ.get(
        "PAYMENT_GATEWAY_API_KEY", "test-mock-key-12345"
    )


class TestConfig(Config):
    """Configuration for automated testing — in-memory SQLite for speed."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    PAYMENT_GATEWAY_URL = "http://localhost:5000/api/v1/payments/mock-gateway"

"""
Application entry point.

Run the development server:
    python run.py

Run with production config:
    CONFIG=config.Config python run.py
"""

import os
from app import create_app, db
from app.models import Parent, LSAProfile, BookingRequest

app = create_app(os.environ.get("CONFIG", "config.Config"))


@app.shell_context_processor
def make_shell_context():
    """Populate `flask shell` with common imports."""
    return {
        "db": db,
        "Parent": Parent,
        "LSAProfile": LSAProfile,
        "BookingRequest": BookingRequest,
    }


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)

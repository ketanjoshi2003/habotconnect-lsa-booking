from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class="config.Config"):
    """Application factory pattern — creates and configures the Flask app."""
    # strict_slashes=False so both /api/v1/bookings and /api/v1/bookings/ work
    app = Flask(__name__)
    app.url_map.strict_slashes = False
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    # Register API blueprints
    from app.routes.bookings import bookings_bp
    from app.routes.lsas import lsas_bp
    from app.routes.payments import payments_bp

    app.register_blueprint(bookings_bp, url_prefix="/api/v1")
    app.register_blueprint(lsas_bp, url_prefix="/api/v1")
    app.register_blueprint(payments_bp, url_prefix="/api/v1")

    # Root endpoint — API landing page with available routes
    @app.route("/")
    def index():
        return {
            "service": "HabotConnect LSA Booking API",
            "version": "1.0",
            "endpoints": {
                "health": "GET /health",
                "create_booking": "POST /api/v1/bookings/",
                "list_bookings": "GET /api/v1/bookings/",
                "get_booking": "GET /api/v1/bookings/<id>/",
                "search_lsas": "GET /api/v1/lsas/search/?skill=ADHD",
                "list_lsas": "GET /api/v1/lsas/",
                "payment_webhook": "POST /api/v1/payments/webhook/",
                "mock_gateway": "POST /api/v1/payments/mock-gateway/",
            },
        }, 200

    # Health check endpoint
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "HabotConnect LSA Booking API"}, 200

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Resource not found", "code": 404}, 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return {"error": "Method not allowed", "code": 405}, 405

    @app.errorhandler(500)
    def internal_error(e):
        return {"error": "Internal server error", "code": 500}, 500

    # In dev, auto-create tables unless running migrations (flask db ...).
    # In production, use: flask db upgrade
    import os
    if os.environ.get("FLASK_RUN_MIGRATE") != "1" and app.config.get("FLASK_ENV") != "production":
        with app.app_context():
            db.create_all()

    return app

import os
from flask import Flask, send_from_directory
from werkzeug.security import generate_password_hash

from models import db, User


def _normalize_db_url(url):
    # Render/Heroku-style URLs sometimes use postgres:// which SQLAlchemy 2.x rejects
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    database_url = _normalize_db_url(os.environ.get("DATABASE_URL"))
    if not database_url:
        # Local dev fallback so the app runs without a Postgres instance handy
        database_url = "sqlite:///" + os.path.join(os.path.dirname(__file__), "dev.db")

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    )

    db.init_app(app)

    with app.app_context():
        db.create_all()

        admin_email = os.environ.get("ADMIN_EMAIL")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if admin_email and admin_password and User.query.count() == 0:
            admin_email = admin_email.strip().lower()
            admin = User(
                name="Admin",
                email=admin_email,
                password_hash=generate_password_hash(admin_password),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

    from routes.auth import auth_bp
    from routes.companies import companies_bp
    from routes.deals import deals_bp
    from routes.tasks import tasks_bp
    from routes.activities import activities_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(deals_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(dashboard_bp)

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(404)
    def not_found(e):
        if not str(e).startswith("404: /api"):
            return send_from_directory(app.static_folder, "index.html")
        return e

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_ENV") != "production")

from flask import Flask, abort, render_template
from sqlalchemy import func

from config import Config

from .extensions import csrf, db, login_manager


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from .admin.routes import admin_bp
    from .auth.routes import auth_bp
    from .maintenance.routes import maintenance_bp
    from .ml.routes import ml_bp
    from .reporter.routes import reporter_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(reporter_bp, url_prefix="/reporter")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(maintenance_bp, url_prefix="/maintenance")

    from .models import CATEGORIES, Complaint

    @app.route("/")
    def home():
        counts = dict(Complaint.query.with_entities(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all())
        return render_template("home.html", categories=[(category, counts.get(category, 0)) for category in CATEGORIES])

    @app.route("/coverage/<category>")
    def category_coverage(category):
        if category not in CATEGORIES:
            abort(404)
        complaints = Complaint.query.filter_by(category=category).order_by(Complaint.created_at.desc()).all()
        status_counts = dict(
            Complaint.query.with_entities(Complaint.status, func.count(Complaint.id))
            .filter_by(category=category)
            .group_by(Complaint.status)
            .all()
        )
        priority_counts = dict(
            Complaint.query.with_entities(Complaint.priority, func.count(Complaint.id))
            .filter_by(category=category)
            .group_by(Complaint.priority)
            .all()
        )
        return render_template(
            "category_coverage.html",
            category=category,
            complaints=complaints,
            status_counts=status_counts,
            priority_counts=priority_counts,
            total=len(complaints),
        )

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()

    return app

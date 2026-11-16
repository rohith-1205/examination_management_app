import os

from flask import Flask, jsonify, render_template, request
from flask_login import LoginManager

from config import Config
from models import User, db
from routes.admin import admin_bp
from routes.api import api_bp
from routes.auth import auth_bp
from routes.examiner import examiner_bp
from routes.student import student_bp
from seed import seed_data

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    try:
        user = db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
    if user is None or (user.role != "admin" and user.status != "active"):
        return None
    return user


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(examiner_bp, url_prefix="/examiner")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "You do not have permission to access this resource."}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "API endpoint or resource not found."}), 404
        return render_template("errors/404.html"), 404

    with app.app_context():
        db.create_all()
        seed_data()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

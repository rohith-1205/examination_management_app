import os

from flask import Flask, render_template
from flask_login import LoginManager

from config import Config
from models import db
from routes.admin import admin_bp
from routes.api import api_bp
from routes.auth import auth_bp
from routes.examiner import examiner_bp
from routes.student import student_bp

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return None


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

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

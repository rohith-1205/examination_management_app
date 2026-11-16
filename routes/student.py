from flask import Blueprint, render_template

from utils import role_required

student_bp = Blueprint("student", __name__)


@student_bp.route("/dashboard")
@role_required("student")
def dashboard():
    return render_template("dashboard.html", dashboard_title="Student Dashboard")

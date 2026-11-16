from flask import Blueprint, render_template

from utils import role_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    return render_template("dashboard.html", dashboard_title="Admin Dashboard")

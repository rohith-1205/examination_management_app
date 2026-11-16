import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from models import User, db

auth_bp = Blueprint("auth", __name__)


def dashboard_for(role):
    return {
        "admin": "admin.dashboard",
        "examiner": "examiner.dashboard",
        "student": "student.dashboard",
    }.get(role, "index")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_for(current_user.role)))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html"), 401

        if user.status == "inactive":
            flash("Your account is deactivated.", "danger")
            return redirect(url_for("auth.login"))

        if user.role == "examiner" and user.status == "pending":
            return render_template("auth/pending.html")

        if user.status != "active":
            flash("Your account is waiting for approval.", "warning")
            return redirect(url_for("auth.login"))

        login_user(user)
        flash(f"Welcome back, {user.name}!", "success")
        return redirect(url_for(dashboard_for(user.role)))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_for(current_user.role)))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "").strip().lower()
        department = request.form.get("department", "").strip()
        roll_no = request.form.get("roll_no", "").strip().upper()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password or not role:
            flash("Please fill in all required fields.", "danger")
            return render_template("auth/register.html"), 400

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid email address.", "danger")
            return render_template("auth/register.html"), 400

        if role not in ("examiner", "student"):
            flash("Choose Examiner or Student to register.", "danger")
            return render_template("auth/register.html"), 400

        if role == "examiner" and not department:
            flash("Department is required for examiner registration.", "danger")
            return render_template("auth/register.html"), 400

        if role == "student" and not roll_no:
            flash("Roll number is required for student registration.", "danger")
            return render_template("auth/register.html"), 400

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("auth/register.html"), 400

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html"), 400

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return render_template("auth/register.html"), 400

        if role == "student" and User.query.filter_by(roll_no=roll_no).first():
            flash("That roll number is already registered.", "danger")
            return render_template("auth/register.html"), 400

        user = User(
            name=name,
            email=email,
            role=role,
            phone=phone or None,
            department=department if role == "examiner" else None,
            roll_no=roll_no if role == "student" else None,
            status="pending" if role == "examiner" else "active",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        if role == "examiner":
            flash("Registration received. You can log in after admin approval.", "success")
        else:
            flash("Your account is ready. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

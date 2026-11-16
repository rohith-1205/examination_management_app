from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from models import Booking, Course, Exam, Slot, User, db
from utils import role_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    stats = {
        "courses": Course.query.count(),
        "exams": Exam.query.count(),
        "examiners": User.query.filter_by(role="examiner").count(),
        "students": User.query.filter_by(role="student").count(),
        "slots": Slot.query.count(),
        "bookings": Booking.query.count(),
        "pending_examiners": User.query.filter_by(
            role="examiner", status="pending"
        ).count(),
    }
    recent_bookings = Booking.query.order_by(Booking.booked_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_bookings=recent_bookings,
        active_tab="dashboard",
    )


@admin_bp.route("/courses")
@role_required("admin")
def courses():
    search = request.args.get("search", "").strip()
    query = Course.query
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(Course.name.ilike(pattern), Course.code.ilike(pattern))
        )

    course_list = query.order_by(Course.name.asc()).all()
    return render_template(
        "admin/courses.html",
        courses=course_list,
        search=search,
        active_tab="courses",
    )


@admin_bp.route("/courses/add", methods=["GET", "POST"])
@role_required("admin")
def add_course():
    if request.method == "POST":
        return save_course()

    return render_template(
        "admin/course_form.html",
        course=None,
        active_tab="courses",
        page_title="Add course",
    )


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_course(course_id):
    course = db.get_or_404(Course, course_id)
    if request.method == "POST":
        return save_course(course)

    return render_template(
        "admin/course_form.html",
        course=course,
        active_tab="courses",
        page_title="Edit course",
    )


def save_course(course=None):
    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "").strip()

    if not code or not name or not status:
        flash("Course code, name, and status are required.", "danger")
        return render_course_form(course, 400)

    if status not in ("Active", "Inactive"):
        flash("Choose a valid course status.", "danger")
        return render_course_form(course, 400)

    existing_course = Course.query.filter(
        func.lower(Course.code) == code.lower()
    ).first()
    if existing_course and (course is None or existing_course.id != course.id):
        flash("A course with that code already exists.", "danger")
        return render_course_form(course, 400)

    if course is None:
        course = Course(code=code, name=name)

    course.code = code
    course.name = name
    course.description = description or None
    course.status = status
    db.session.add(course)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("A course with that code already exists.", "danger")
        return render_course_form(course, 400)

    flash("Course saved successfully.", "success")
    return redirect(url_for("admin.courses"))


def render_course_form(course, status_code):
    return (
        render_template(
            "admin/course_form.html",
            course=course,
            active_tab="courses",
            page_title="Edit course" if course else "Add course",
            form_values=request.form,
        ),
        status_code,
    )


@admin_bp.route("/courses/<int:course_id>/delete/confirm")
@role_required("admin")
def confirm_delete_course(course_id):
    course = db.get_or_404(Course, course_id)
    return render_template(
        "admin/course_delete.html",
        course=course,
        active_tab="courses",
    )


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@role_required("admin")
def delete_course(course_id):
    course = db.get_or_404(Course, course_id)
    if course.exams:
        course.status = "Inactive"
        db.session.commit()
        flash(
            "This course has exams, so it was set to Inactive instead of deleted.",
            "warning",
        )
    else:
        db.session.delete(course)
        db.session.commit()
        flash("Course deleted successfully.", "success")

    return redirect(url_for("admin.courses"))

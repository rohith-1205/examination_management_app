from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from models import Booking, Course, Exam, User, db

api_bp = Blueprint("api", __name__)


def api_login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Login is required."}), 401
        return view_func(*args, **kwargs)

    return wrapped_view


def api_admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Login is required."}), 401
        if current_user.role != "admin":
            return jsonify({"error": "Admin access is required."}), 403
        return view_func(*args, **kwargs)

    return wrapped_view


@api_bp.route("/courses", methods=["GET"])
@api_login_required
def courses():
    course_list = Course.query.order_by(Course.code.asc()).all()
    return jsonify([course_data(course) for course in course_list]), 200


@api_bp.route("/courses/<int:course_id>", methods=["GET"])
@api_login_required
def course_detail(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        return jsonify({"error": "Course not found."}), 404

    data = course_data(course)
    data["exams"] = [
        {"id": exam.id, "name": exam.name, "status": exam.status}
        for exam in course.exams
    ]
    return jsonify(data), 200


@api_bp.route("/courses", methods=["POST"])
@api_admin_required
def create_course():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send course details as a JSON object."}), 400

    values, error = validate_course_data(payload)
    if error:
        return jsonify({"error": error}), 400

    course = Course(**values)
    db.session.add(course)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A course with that code already exists."}), 400

    return jsonify(course_data(course)), 201


@api_bp.route("/courses/<int:course_id>", methods=["PUT"])
@api_admin_required
def update_course(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        return jsonify({"error": "Course not found."}), 404

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send course details as a JSON object."}), 400

    values, error = validate_course_data(payload, course.id)
    if error:
        return jsonify({"error": error}), 400

    for field, value in values.items():
        setattr(course, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A course with that code already exists."}), 400

    return jsonify(course_data(course)), 200


@api_bp.route("/courses/<int:course_id>", methods=["DELETE"])
@api_admin_required
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        return jsonify({"error": "Course not found."}), 404

    if course.exams:
        course.status = "Inactive"
        db.session.commit()
        return jsonify({
            "message": "Course has exams and was set to Inactive instead of deleted.",
            "course": course_data(course),
        }), 200

    db.session.delete(course)
    db.session.commit()
    return jsonify({"message": "Course deleted successfully."}), 200


@api_bp.route("/exams", methods=["GET"])
@api_login_required
def exams():
    exam_list = Exam.query.order_by(Exam.created_at.desc()).all()
    return jsonify([exam_data(exam) for exam in exam_list]), 200


@api_bp.route("/exams/<int:exam_id>", methods=["GET"])
@api_login_required
def exam_detail(exam_id):
    exam = db.session.get(Exam, exam_id)
    if exam is None:
        return jsonify({"error": "Exam not found."}), 404

    data = exam_data(exam)
    data["rubrics"] = [
        {
            "id": rubric.id,
            "criterion_name": rubric.criterion_name,
            "max_marks": rubric.max_marks,
            "weightage": rubric.weightage,
            "description": rubric.description,
        }
        for rubric in exam.rubrics
    ]
    data["examiners"] = [
        {
            "id": assignment.examiner.id,
            "name": assignment.examiner.name,
        }
        for assignment in exam.examiner_assignments
    ]
    return jsonify(data), 200


@api_bp.route("/examiners", methods=["GET"])
@api_login_required
def examiners():
    examiner_list = User.query.filter_by(role="examiner").order_by(User.name.asc()).all()
    return jsonify([user_data(user) for user in examiner_list]), 200


@api_bp.route("/students", methods=["GET"])
@api_login_required
def students():
    student_list = User.query.filter_by(role="student").order_by(User.name.asc()).all()
    return jsonify([user_data(user) for user in student_list]), 200


@api_bp.route("/bookings", methods=["GET"])
@api_login_required
def bookings():
    booking_list = Booking.query.order_by(Booking.booked_at.desc()).all()
    return jsonify([booking_data(booking) for booking in booking_list]), 200


def validate_course_data(payload, course_id=None):
    code = payload.get("code")
    name = payload.get("name")
    status = payload.get("status", "Active")
    description = payload.get("description", "")

    if not isinstance(code, str) or not code.strip():
        return None, "Course code is required."
    if not isinstance(name, str) or not name.strip():
        return None, "Course name is required."
    if status not in ("Active", "Inactive"):
        return None, "Status must be Active or Inactive."
    if not isinstance(description, str):
        return None, "Description must be text."

    existing_course = Course.query.filter(
        func.lower(Course.code) == code.strip().lower()
    )
    if course_id is not None:
        existing_course = existing_course.filter(Course.id != course_id)
    if existing_course.first():
        return None, "A course with that code already exists."

    return {
        "code": code.strip().upper(),
        "name": name.strip(),
        "description": description.strip() or None,
        "status": status,
    }, None


def course_data(course):
    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "description": course.description,
        "status": course.status,
        "created_at": course.created_at.isoformat(),
    }


def exam_data(exam):
    return {
        "id": exam.id,
        "course_id": exam.course_id,
        "course_code": exam.course.code,
        "course_name": exam.course.name,
        "name": exam.name,
        "exam_type": exam.exam_type,
        "duration_minutes": exam.duration_minutes,
        "max_marks": exam.max_marks,
        "slot_creation_start": exam.slot_creation_start.isoformat(),
        "slot_creation_end": exam.slot_creation_end.isoformat(),
        "booking_start": exam.booking_start.isoformat(),
        "booking_end": exam.booking_end.isoformat(),
        "status": exam.status,
        "results_published": exam.results_published,
    }


def user_data(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "phone": user.phone,
        "department": user.department if user.role == "examiner" else None,
        "roll_no": user.roll_no if user.role == "student" else None,
    }


def booking_data(booking):
    return {
        "id": booking.id,
        "student_id": booking.student_id,
        "student_name": booking.student.name,
        "slot_id": booking.slot_id,
        "exam_id": booking.exam_id,
        "exam_name": booking.exam.name,
        "slot_date": booking.slot.date.isoformat(),
        "status": booking.status,
        "booked_at": booking.booked_at.isoformat(),
        "cancelled_at": booking.cancelled_at.isoformat() if booking.cancelled_at else None,
        "rescheduled": booking.rescheduled,
    }

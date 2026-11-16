from datetime import date
from math import isfinite
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from models import (
    Booking,
    Course,
    Exam,
    ExamExaminer,
    Rubric,
    Slot,
    User,
    db,
)
from utils import role_required, update_slot_status

admin_bp = Blueprint("admin", __name__)
EXAM_TYPES = ("Viva", "Practical", "Project Demo", "Assessment")
EXAM_STATUSES = ("Draft", "Slot Creation", "Booking Open", "Closed", "Completed")


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


@admin_bp.route("/stats")
@role_required("admin")
def stats():
    bookings_by_exam = (
        db.session.query(Exam.name, func.count(Booking.id))
        .outerjoin(Booking, Booking.exam_id == Exam.id)
        .group_by(Exam.id, Exam.name)
        .order_by(Exam.name.asc())
        .all()
    )
    slots_by_examiner = (
        db.session.query(User.name, func.count(Slot.id))
        .outerjoin(Slot, Slot.examiner_id == User.id)
        .filter(User.role == "examiner")
        .group_by(User.id, User.name)
        .order_by(User.name.asc())
        .all()
    )
    exam_statuses = dict(
        db.session.query(Exam.status, func.count(Exam.id))
        .group_by(Exam.status)
        .all()
    )
    status_labels = ("Draft", "Slot Creation", "Booking Open", "Closed", "Completed")

    return render_template(
        "admin/stats.html",
        booking_labels=[row[0] for row in bookings_by_exam],
        booking_counts=[row[1] for row in bookings_by_exam],
        examiner_labels=[row[0] for row in slots_by_examiner],
        examiner_slot_counts=[row[1] for row in slots_by_examiner],
        status_labels=list(status_labels),
        status_counts=[exam_statuses.get(status, 0) for status in status_labels],
        active_tab="stats",
    )


@admin_bp.route("/examiners")
@role_required("admin")
def examiners():
    selected_status = request.args.get("status", "pending").strip().lower()
    if selected_status not in ("pending", "active", "inactive"):
        selected_status = "pending"

    examiner_list = User.query.filter_by(
        role="examiner", status=selected_status
    ).order_by(User.name.asc()).all()
    return render_template(
        "admin/examiners.html",
        examiners=examiner_list,
        selected_status=selected_status,
        active_tab="examiners",
    )


@admin_bp.route("/examiners/add", methods=["GET", "POST"])
@role_required("admin")
def add_examiner():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()
        password = request.form.get("password", "")

        errors = []
        if not name or not email or not department or not password:
            errors.append("Name, email, department, and password are required.")
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if email and User.query.filter(func.lower(User.email) == email).first():
            errors.append("An account with that email already exists.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "admin/examiner_form.html",
                form_values=request.form,
                active_tab="examiners",
            ), 400

        examiner = User(
            name=name,
            email=email,
            phone=phone or None,
            department=department,
            role="examiner",
            status="active",
        )
        examiner.set_password(password)
        db.session.add(examiner)
        db.session.commit()
        flash("Examiner added and activated.", "success")
        return redirect(url_for("admin.examiners", status="active"))

    return render_template(
        "admin/examiner_form.html",
        active_tab="examiners",
    )


@admin_bp.route("/examiners/<int:examiner_id>/<action>", methods=["POST"])
@role_required("admin")
def update_examiner(examiner_id, action):
    examiner = db.get_or_404(User, examiner_id)
    if examiner.role != "examiner":
        flash("That account is not an examiner.", "danger")
        return redirect(url_for("admin.examiners"))

    transitions = {
        ("pending", "approve"): ("active", "Examiner approved."),
        ("active", "deactivate"): ("inactive", "Examiner deactivated."),
        ("inactive", "reactivate"): ("active", "Examiner reactivated."),
    }
    transition = transitions.get((examiner.status, action))
    if transition is None:
        flash("That examiner action is not available.", "warning")
    else:
        examiner.status, message = transition
        db.session.commit()
        flash(message, "success")
    return redirect(url_for("admin.examiners", status=examiner.status))


@admin_bp.route("/students")
@role_required("admin")
def students():
    search = request.args.get("search", "").strip()
    query = User.query.filter_by(role="student")
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
                User.roll_no.ilike(pattern),
            )
        )

    student_list = query.order_by(User.name.asc()).all()
    return render_template(
        "admin/students.html",
        students=student_list,
        search=search,
        active_tab="students",
    )


@admin_bp.route("/students/<int:student_id>")
@role_required("admin")
def student_detail(student_id):
    student = db.get_or_404(User, student_id)
    if student.role != "student":
        flash("That account is not a student.", "danger")
        return redirect(url_for("admin.students"))

    booking_history = Booking.query.filter_by(student_id=student.id).order_by(
        Booking.booked_at.desc()
    ).all()
    return render_template(
        "admin/student_detail.html",
        student=student,
        bookings=booking_history,
        active_tab="students",
    )


@admin_bp.route("/slots")
@role_required("admin")
def slots():
    exam_filter = request.args.get("exam_id", "").strip()
    examiner_filter = request.args.get("examiner_id", "").strip()
    date_filter = request.args.get("date", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Slot.query
    try:
        if exam_filter:
            query = query.filter_by(exam_id=int(exam_filter))
    except ValueError:
        exam_filter = ""

    try:
        if examiner_filter:
            query = query.filter_by(examiner_id=int(examiner_filter))
    except ValueError:
        examiner_filter = ""

    if date_filter:
        try:
            query = query.filter_by(date=date.fromisoformat(date_filter))
        except ValueError:
            flash("Enter a valid slot date.", "warning")
            date_filter = ""

    if status_filter in ("Available", "Full", "Cancelled", "Completed"):
        query = query.filter_by(status=status_filter)

    slot_list = query.order_by(Slot.date.asc(), Slot.start_time.asc()).all()
    return render_template(
        "admin/slots.html",
        slots=slot_list,
        exams=Exam.query.order_by(Exam.name.asc()).all(),
        examiners=User.query.filter_by(role="examiner").order_by(User.name.asc()).all(),
        exam_filter=exam_filter,
        examiner_filter=examiner_filter,
        date_filter=date_filter,
        status_filter=status_filter,
        slot_statuses=("Available", "Full", "Cancelled", "Completed"),
        active_tab="slots",
    )


@admin_bp.route("/slots/<int:slot_id>/change-examiner", methods=["GET", "POST"])
@role_required("admin")
def change_slot_examiner(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    if request.method == "POST":
        if any(booking.evaluation is not None for booking in slot.bookings):
            flash("The examiner cannot be changed after a booking is evaluated.", "danger")
            return redirect(url_for("admin.slots"))

        try:
            examiner_id = int(request.form.get("examiner_id", ""))
        except ValueError:
            examiner_id = None

        assignment = ExamExaminer.query.filter_by(
            exam_id=slot.exam_id, examiner_id=examiner_id
        ).first() if examiner_id else None
        if assignment is None:
            flash("Choose an examiner assigned to this exam.", "danger")
        else:
            slot.examiner_id = assignment.examiner_id
            db.session.commit()
            flash("Slot examiner changed successfully.", "success")
        return redirect(url_for("admin.slots"))

    if any(booking.evaluation is not None for booking in slot.bookings):
        flash("The examiner cannot be changed after a booking is evaluated.", "danger")
        return redirect(url_for("admin.slots"))

    assignments = ExamExaminer.query.filter_by(exam_id=slot.exam_id).all()
    return render_template(
        "admin/slot_examiner_form.html",
        slot=slot,
        assignments=assignments,
        active_tab="slots",
    )


@admin_bp.route("/bookings")
@role_required("admin")
def bookings():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    query = Booking.query.join(User, Booking.student_id == User.id)
    if search:
        pattern = f"%{search}%"
        search_terms = [
            User.name.ilike(pattern),
            User.roll_no.ilike(pattern),
        ]
        if search.isdigit():
            search_terms.append(Booking.id == int(search))
        query = query.filter(or_(*search_terms))

    if status_filter in ("Booked", "Cancelled", "Completed"):
        query = query.filter(Booking.status == status_filter)

    booking_list = query.order_by(Booking.booked_at.desc(), Booking.id.desc()).all()
    return render_template(
        "admin/bookings.html",
        bookings=booking_list,
        search=search,
        status_filter=status_filter,
        booking_statuses=("Booked", "Cancelled", "Completed"),
        active_tab="bookings",
    )


@admin_bp.route("/bookings/<int:booking_id>/reschedule", methods=["GET", "POST"])
@role_required("admin")
def reschedule_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.evaluation is not None:
        flash("This booking has been evaluated and cannot be rescheduled.", "danger")
        return redirect(url_for("admin.bookings"))
    if booking.status != "Booked":
        flash("Only active bookings can be rescheduled.", "warning")
        return redirect(url_for("admin.bookings"))

    available_slots = Slot.query.filter(
        Slot.exam_id == booking.exam_id,
        Slot.id != booking.slot_id,
        Slot.status == "Available",
        Slot.available_seats > 0,
    ).order_by(Slot.date.asc(), Slot.start_time.asc()).all()

    if request.method == "POST":
        try:
            new_slot_id = int(request.form.get("slot_id", ""))
        except ValueError:
            new_slot_id = None

        new_slot = db.session.get(Slot, new_slot_id) if new_slot_id else None
        if (
            new_slot is None
            or new_slot.exam_id != booking.exam_id
            or new_slot.id == booking.slot_id
        ):
            flash("Choose an available slot for the same exam.", "danger")
            return render_template(
                "admin/booking_reschedule.html",
                booking=booking,
                available_slots=available_slots,
                active_tab="bookings",
            ), 400

        old_slot = booking.slot
        update_slot_status(new_slot)
        if new_slot.status != "Available" or new_slot.available_seats <= 0:
            flash("That slot no longer has available seats.", "danger")
            return redirect(url_for("admin.reschedule_booking", booking_id=booking.id))

        booking.slot = new_slot
        booking.rescheduled = True
        update_slot_status(old_slot)
        update_slot_status(new_slot)
        db.session.commit()
        flash("Booking rescheduled successfully.", "success")
        return redirect(url_for("admin.bookings"))

    return render_template(
        "admin/booking_reschedule.html",
        booking=booking,
        available_slots=available_slots,
        active_tab="bookings",
    )


@admin_bp.route("/search")
@role_required("admin")
def search():
    term = request.args.get("q", "").strip()
    students = []
    examiners = []
    exams = []
    matching_bookings = []
    if term:
        pattern = f"%{term}%"
        student_filters = [
            User.name.ilike(pattern),
            User.email.ilike(pattern),
            User.roll_no.ilike(pattern),
        ]
        examiner_filters = [User.name.ilike(pattern), User.email.ilike(pattern)]
        exam_filters = [Exam.name.ilike(pattern)]
        if term.isdigit():
            record_id = int(term)
            student_filters.append(User.id == record_id)
            examiner_filters.append(User.id == record_id)
            exam_filters.append(Exam.id == record_id)

        students = User.query.filter(
            User.role == "student",
            or_(*student_filters),
        ).limit(10).all()
        examiners = User.query.filter(
            User.role == "examiner",
            or_(*examiner_filters),
        ).limit(10).all()
        exams = Exam.query.filter(or_(*exam_filters)).limit(10).all()

        booking_query = Booking.query.join(User, Booking.student_id == User.id)
        booking_filters = [
            User.name.ilike(pattern),
            User.roll_no.ilike(pattern),
        ]
        if term.isdigit():
            booking_filters.append(Booking.id == record_id)
        matching_bookings = (
            booking_query.filter(or_(*booking_filters))
            .order_by(Booking.booked_at.desc())
            .limit(10)
            .all()
        )

    return render_template(
        "admin/search.html",
        term=term,
        students=students,
        examiners=examiners,
        exams=exams,
        bookings=matching_bookings,
        active_tab="search",
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


@admin_bp.route("/exams")
@role_required("admin")
def exams():
    status_filter = request.args.get("status", "").strip()
    course_filter = request.args.get("course_id", "").strip()
    search = request.args.get("search", "").strip()

    query = Exam.query
    if status_filter in EXAM_STATUSES:
        query = query.filter_by(status=status_filter)

    selected_course_id = None
    if course_filter:
        try:
            selected_course_id = int(course_filter)
        except ValueError:
            selected_course_id = None
        if selected_course_id is not None:
            query = query.filter_by(course_id=selected_course_id)

    if search:
        query = query.filter(Exam.name.ilike(f"%{search}%"))

    exam_list = query.order_by(Exam.created_at.desc(), Exam.id.desc()).all()
    return render_template(
        "admin/exams.html",
        exams=exam_list,
        courses=Course.query.order_by(Course.code.asc()).all(),
        statuses=EXAM_STATUSES,
        status_filter=status_filter,
        course_filter=selected_course_id,
        search=search,
        active_tab="exams",
    )


@admin_bp.route("/exams/add", methods=["GET", "POST"])
@role_required("admin")
def add_exam():
    if request.method == "POST":
        return save_exam()

    return render_template(
        "admin/exam_form.html",
        exam=None,
        courses=Course.query.order_by(Course.code.asc()).all(),
        exam_types=EXAM_TYPES,
        date_values=get_exam_date_values(None),
        page_title="Add exam",
        active_tab="exams",
    )


@admin_bp.route("/exams/<int:exam_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if request.method == "POST":
        return save_exam(exam)

    return render_template(
        "admin/exam_form.html",
        exam=exam,
        courses=Course.query.order_by(Course.code.asc()).all(),
        exam_types=EXAM_TYPES,
        date_values=get_exam_date_values(exam),
        page_title="Edit exam",
        active_tab="exams",
    )


@admin_bp.route("/exams/<int:exam_id>")
@role_required("admin")
def exam_detail(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    assigned_ids = [
        assignment.examiner_id for assignment in exam.examiner_assignments
    ]
    active_examiners = User.query.filter_by(
        role="examiner", status="active"
    ).order_by(User.name.asc()).all()
    active_examiners = [
        examiner for examiner in active_examiners if examiner.id not in assigned_ids
    ]
    rubric_weightage_total = sum(rubric.weightage for rubric in exam.rubrics)
    rubric_marks_total = sum(rubric.max_marks for rubric in exam.rubrics)
    exam_bookings = [
        booking for booking in exam.bookings if booking.status != "Cancelled"
    ]
    evaluations = [
        booking.evaluation for booking in exam_bookings
        if booking.evaluation is not None
    ]
    average_marks = (
        sum(evaluation.total_marks for evaluation in evaluations) / len(evaluations)
        if evaluations else 0
    )
    if exam.status == "Draft":
        timeline_stage = 0
    elif exam.status == "Slot Creation":
        timeline_stage = 1
    elif exam.status == "Booking Open":
        timeline_stage = 3
    elif exam.status == "Completed" or date.today() > exam.booking_end:
        timeline_stage = 4
    else:
        timeline_stage = 2

    return render_template(
        "admin/exam_detail.html",
        exam=exam,
        active_examiners=active_examiners,
        rubric_weightage_total=rubric_weightage_total,
        rubric_marks_total=rubric_marks_total,
        weightage_progress=min(round(rubric_weightage_total, 1), 100),
        marks_progress=min(round(rubric_marks_total / exam.max_marks * 100), 100),
        evaluated_count=len(evaluations),
        total_bookings=len(exam_bookings),
        average_marks=average_marks,
        today=date.today(),
        timeline_stage=timeline_stage,
        active_tab="exams",
    )


@admin_bp.route("/exams/<int:exam_id>/delete/confirm")
@role_required("admin")
def confirm_delete_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    return render_template(
        "admin/exam_delete.html",
        exam=exam,
        active_tab="exams",
    )


@admin_bp.route("/exams/<int:exam_id>/delete", methods=["POST"])
@role_required("admin")
def delete_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam.bookings:
        flash("This exam has bookings and cannot be deleted.", "danger")
        return redirect(url_for("admin.exam_detail", exam_id=exam.id))

    db.session.delete(exam)
    db.session.commit()
    flash("Exam deleted successfully.", "success")
    return redirect(url_for("admin.exams"))


def save_exam(exam=None):
    form_values = request.form
    name = form_values.get("name", "").strip()
    exam_type = form_values.get("exam_type", "").strip()
    duration_text = form_values.get("duration_minutes", "").strip()
    max_marks_text = form_values.get("max_marks", "").strip()
    course_text = form_values.get("course_id", "").strip()
    date_fields = (
        "slot_creation_start",
        "slot_creation_end",
        "booking_start",
        "booking_end",
    )

    errors = []
    course = None
    try:
        course_id = int(course_text)
        course = db.session.get(Course, course_id)
    except ValueError:
        course_id = None
    if course is None:
        errors.append("Choose a valid course.")

    if not name:
        errors.append("Exam name is required.")
    if exam_type not in EXAM_TYPES:
        errors.append("Choose a valid exam type.")

    try:
        duration_minutes = int(duration_text)
        if duration_minutes <= 0:
            errors.append("Duration must be greater than zero.")
    except ValueError:
        duration_minutes = 0
        errors.append("Enter a valid exam duration.")

    try:
        max_marks = int(max_marks_text)
        if max_marks <= 0:
            errors.append("Maximum marks must be greater than zero.")
    except ValueError:
        max_marks = 0
        errors.append("Enter a valid maximum marks value.")

    exam_dates = {}
    for field in date_fields:
        try:
            exam_dates[field] = date.fromisoformat(form_values.get(field, ""))
        except ValueError:
            errors.append("Enter valid dates for all exam stages.")
            break

    if len(exam_dates) == len(date_fields):
        if exam_dates["slot_creation_end"] <= exam_dates["slot_creation_start"]:
            errors.append("Slot creation end date must be after its start date.")
        if exam_dates["booking_end"] <= exam_dates["booking_start"]:
            errors.append("Booking end date must be after its start date.")
        if exam_dates["booking_start"] < exam_dates["slot_creation_end"]:
            errors.append("Booking must start on or after slot creation ends.")

    if exam is not None and max_marks > 0:
        rubric_marks = sum(rubric.max_marks for rubric in exam.rubrics)
        if rubric_marks > max_marks:
            errors.append("Exam maximum marks cannot be less than the existing rubric marks.")

    if errors:
        for error in errors:
            flash(error, "danger")
        return render_exam_form(exam, 400, form_values)

    if exam is None:
        exam = Exam()

    exam.course = course
    exam.name = name
    exam.exam_type = exam_type
    exam.duration_minutes = duration_minutes
    exam.max_marks = max_marks
    for field, value in exam_dates.items():
        setattr(exam, field, value)
    db.session.add(exam)
    db.session.commit()

    flash("Exam saved successfully.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


def render_exam_form(exam, status_code, form_values):
    return (
        render_template(
            "admin/exam_form.html",
            exam=exam,
            courses=Course.query.order_by(Course.code.asc()).all(),
            exam_types=EXAM_TYPES,
            date_values=get_exam_date_values(exam),
            page_title="Edit exam" if exam else "Add exam",
            active_tab="exams",
            form_values=form_values,
        ),
        status_code,
    )


def get_exam_date_values(exam):
    fields = (
        "slot_creation_start",
        "slot_creation_end",
        "booking_start",
        "booking_end",
    )
    if exam is None:
        return {field: "" for field in fields}
    return {field: getattr(exam, field).isoformat() for field in fields}


def transition_exam_status(exam, action):
    if action == "open_slot_creation" and exam.status == "Draft":
        exam.status = "Slot Creation"
        return True, "Slot creation is now open."

    if action == "close_slot_creation" and exam.status == "Slot Creation":
        exam.status = "Closed"
        return True, "Slot creation is now closed."

    if action == "open_booking" and exam.status == "Closed":
        today = date.today()
        if exam.booking_start <= today <= exam.booking_end:
            exam.status = "Booking Open"
            return True, "Booking is now open."
        return False, "Booking can only be opened during its scheduled booking dates."

    if action == "close_booking" and exam.status == "Booking Open":
        exam.status = "Closed"
        return True, "Booking is now closed."

    if action == "mark_completed" and exam.status == "Closed":
        if date.today() > exam.booking_end:
            exam.status = "Completed"
            return True, "Exam marked as completed."
        return False, "The exam can only be completed after the booking period ends."

    if (
        action == "publish_results"
        and exam.status == "Completed"
        and not exam.results_published
    ):
        exam.results_published = True
        return True, "Exam results have been published."

    return False, "That status change is not allowed at this stage."


@admin_bp.route("/exams/<int:exam_id>/status", methods=["POST"])
@role_required("admin")
def update_exam_status(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    allowed, message = transition_exam_status(exam, request.form.get("action", ""))
    if allowed:
        db.session.commit()
        flash(message, "success")
    else:
        flash(message, "warning")

    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


@admin_bp.route("/exams/<int:exam_id>/examiners", methods=["POST"])
@role_required("admin")
def assign_examiner(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    try:
        examiner_id = int(request.form.get("examiner_id", ""))
    except ValueError:
        examiner_id = None

    examiner = db.session.get(User, examiner_id) if examiner_id else None
    if examiner is None or examiner.role != "examiner" or examiner.status != "active":
        flash("Choose an active examiner.", "danger")
        return redirect(url_for("admin.exam_detail", exam_id=exam.id))

    assignment = ExamExaminer(exam=exam, examiner=examiner)
    db.session.add(assignment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("That examiner is already assigned to this exam.", "warning")
    else:
        flash("Examiner assigned successfully.", "success")

    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


@admin_bp.route(
    "/exams/<int:exam_id>/examiners/<int:assignment_id>/remove", methods=["POST"]
)
@role_required("admin")
def remove_examiner(exam_id, assignment_id):
    exam = db.get_or_404(Exam, exam_id)
    assignment = db.get_or_404(ExamExaminer, assignment_id)
    if assignment.exam_id != exam.id:
        flash("That examiner assignment does not belong to this exam.", "danger")
    else:
        db.session.delete(assignment)
        db.session.commit()
        flash("Examiner removed from this exam.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


@admin_bp.route("/exams/<int:exam_id>/rubrics/add", methods=["GET", "POST"])
@role_required("admin")
def add_rubric(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if request.method == "POST":
        return save_rubric(exam)

    return render_template(
        "admin/rubric_form.html",
        exam=exam,
        rubric=None,
        page_title="Add rubric criterion",
        active_tab="exams",
    )


@admin_bp.route(
    "/exams/<int:exam_id>/rubrics/<int:rubric_id>/edit", methods=["GET", "POST"]
)
@role_required("admin")
def edit_rubric(exam_id, rubric_id):
    exam = db.get_or_404(Exam, exam_id)
    rubric = db.get_or_404(Rubric, rubric_id)
    if rubric.exam_id != exam.id:
        return redirect(url_for("admin.exam_detail", exam_id=exam.id))
    if request.method == "POST":
        return save_rubric(exam, rubric)

    return render_template(
        "admin/rubric_form.html",
        exam=exam,
        rubric=rubric,
        page_title="Edit rubric criterion",
        active_tab="exams",
    )


def save_rubric(exam, rubric=None):
    criterion_name = request.form.get("criterion_name", "").strip()
    description = request.form.get("description", "").strip()
    max_marks_text = request.form.get("max_marks", "").strip()
    weightage_text = request.form.get("weightage", "").strip()
    errors = []

    if not criterion_name:
        errors.append("Criterion name is required.")

    try:
        max_marks = int(max_marks_text)
        if max_marks <= 0:
            errors.append("Criterion marks must be greater than zero.")
    except ValueError:
        max_marks = 0
        errors.append("Enter a valid criterion marks value.")

    try:
        weightage = float(weightage_text)
        if not isfinite(weightage) or weightage <= 0:
            errors.append("Weightage must be greater than zero.")
    except ValueError:
        weightage = 0
        errors.append("Enter a valid weightage.")

    other_rubrics = [item for item in exam.rubrics if rubric is None or item.id != rubric.id]
    if not errors and sum(item.weightage for item in other_rubrics) + weightage > 100:
        errors.append("Total rubric weightage cannot exceed 100%.")
    if not errors and sum(item.max_marks for item in other_rubrics) + max_marks > exam.max_marks:
        errors.append("Total rubric marks cannot exceed the exam maximum marks.")

    if errors:
        for error in errors:
            flash(error, "danger")
        return (
            render_template(
                "admin/rubric_form.html",
                exam=exam,
                rubric=rubric,
                page_title="Edit rubric criterion" if rubric else "Add rubric criterion",
                active_tab="exams",
                form_values=request.form,
            ),
            400,
        )

    if rubric is None:
        rubric = Rubric(exam=exam)
    rubric.criterion_name = criterion_name
    rubric.description = description or None
    rubric.max_marks = max_marks
    rubric.weightage = weightage
    db.session.add(rubric)
    db.session.commit()
    flash("Rubric criterion saved.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


@admin_bp.route(
    "/exams/<int:exam_id>/rubrics/<int:rubric_id>/delete", methods=["POST"]
)
@role_required("admin")
def delete_rubric(exam_id, rubric_id):
    exam = db.get_or_404(Exam, exam_id)
    rubric = db.get_or_404(Rubric, rubric_id)
    if rubric.exam_id != exam.id:
        flash("That rubric does not belong to this exam.", "danger")
    elif rubric.scores:
        flash("This rubric has evaluation scores and cannot be deleted.", "danger")
    else:
        db.session.delete(rubric)
        db.session.commit()
        flash("Rubric criterion deleted.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


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

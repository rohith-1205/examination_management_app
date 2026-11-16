import csv
from datetime import date, datetime
from io import StringIO

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError

from models import Booking, Course, Exam, Slot, User, db
from utils import role_required, update_slot_status

student_bp = Blueprint("student", __name__)
EXAM_TYPES = ("Viva", "Practical", "Project Demo", "Assessment")
EXAM_STATUSES = ("Slot Creation", "Booking Open", "Closed", "Completed")


@student_bp.route("/dashboard")
@role_required("student")
def dashboard():
    today = date.today()
    available_exams = Exam.query.filter(
        Exam.status == "Booking Open",
        Exam.booking_start <= today,
        Exam.booking_end >= today,
    ).order_by(Exam.booking_end.asc()).all()

    active_bookings = Booking.query.filter_by(
        student_id=current_user.id, status="Booked"
    ).order_by(Booking.booked_at.desc()).all()
    upcoming_bookings = [
        booking for booking in active_bookings if booking.slot.date >= today
    ]
    published_results = (
        Booking.query.join(Exam, Booking.exam_id == Exam.id)
        .filter(
            Booking.student_id == current_user.id,
            Exam.results_published.is_(True),
            Booking.evaluation.has(),
        )
        .order_by(Booking.booked_at.desc())
        .all()
    )

    return render_template(
        "student/dashboard.html",
        available_exams=available_exams,
        upcoming_bookings=upcoming_bookings[:5],
        my_bookings=active_bookings[:5],
        published_results=published_results[:5],
        stats={
            "available_exams": len(available_exams),
            "upcoming_bookings": len(upcoming_bookings),
            "my_bookings": len(active_bookings),
            "published_results": len(published_results),
        },
        today=today,
        active_page="dashboard",
    )


@student_bp.route("/exams")
@role_required("student")
def exams():
    search = request.args.get("search", "").strip()
    exam_type = request.args.get("type", "").strip()
    course_filter = request.args.get("course_id", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Exam.query.filter(Exam.status != "Draft")
    if search:
        pattern = f"%{search}%"
        query = query.join(Course).filter(
            or_(Exam.name.ilike(pattern), Course.name.ilike(pattern), Course.code.ilike(pattern))
        )
    if exam_type in EXAM_TYPES:
        query = query.filter_by(exam_type=exam_type)
    if status_filter in EXAM_STATUSES:
        query = query.filter_by(status=status_filter)

    selected_course_id = None
    if course_filter:
        try:
            selected_course_id = int(course_filter)
        except ValueError:
            selected_course_id = None
    if selected_course_id:
        query = query.filter_by(course_id=selected_course_id)

    exam_list = query.order_by(Exam.slot_creation_start.desc()).all()
    return render_template(
        "student/exams.html",
        exams=exam_list,
        courses=Course.query.filter_by(status="Active").order_by(Course.code.asc()).all(),
        exam_types=EXAM_TYPES,
        exam_statuses=EXAM_STATUSES,
        search=search,
        selected_type=exam_type,
        course_filter=selected_course_id,
        status_filter=status_filter,
        active_page="exams",
    )


@student_bp.route("/exams/<int:exam_id>")
@role_required("student")
def exam_detail(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam.status == "Draft":
        abort(404)

    active_booking = Booking.query.filter_by(
        student_id=current_user.id, exam_id=exam.id, status="Booked"
    ).first()
    available_slots = Slot.query.filter(
        Slot.exam_id == exam.id,
        Slot.status == "Available",
        Slot.available_seats > 0,
    ).order_by(Slot.date.asc(), Slot.start_time.asc()).all()
    can_book = (
        exam.status == "Booking Open"
        and exam.booking_start <= date.today() <= exam.booking_end
        and active_booking is None
    )

    return render_template(
        "student/exam_detail.html",
        exam=exam,
        available_slots=available_slots,
        active_booking=active_booking,
        can_book=can_book,
        today=date.today(),
        active_page="exams",
    )


@student_bp.route("/exams/<int:exam_id>/book", methods=["POST"])
@role_required("student")
def book_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    try:
        slot_id = int(request.form.get("slot_id", ""))
    except ValueError:
        slot_id = None
    slot = db.session.get(Slot, slot_id) if slot_id else None

    success, message = book_slot(current_user, exam, slot)
    flash(message, "success" if success else "danger")
    return redirect(url_for("student.exam_detail", exam_id=exam.id))


def book_slot(student, exam, slot):
    if exam.status != "Booking Open":
        return False, "This exam is not currently open for booking."
    today = date.today()
    if not exam.booking_start <= today <= exam.booking_end:
        return False, "Booking is only available during the exam booking period."
    if slot is None or slot.exam_id != exam.id:
        return False, "Choose an available slot for this exam."
    if slot.status != "Available" or slot.available_seats <= 0:
        return False, "That slot is full or no longer available."

    existing_booking = Booking.query.filter_by(
        student_id=student.id, exam_id=exam.id, status="Booked"
    ).first()
    if existing_booking:
        return False, "You already have an active booking for this exam."

    reservation = db.session.execute(
        update(Slot)
        .where(
            Slot.id == slot.id,
            Slot.status == "Available",
            Slot.available_seats > 0,
        )
        .values(available_seats=Slot.available_seats - 1)
    )
    if reservation.rowcount != 1:
        db.session.rollback()
        return False, "That slot just filled up. Please choose another slot."

    booking = Booking(student=student, exam=exam, slot=slot, status="Booked")
    db.session.add(booking)
    try:
        db.session.flush()
        db.session.refresh(slot, attribute_names=["available_seats", "status"])
        update_slot_status(slot)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return False, "You already have an active booking for this exam."

    return True, "Your exam slot has been booked."


@student_bp.route("/bookings")
@role_required("student")
def bookings():
    booking_history = Booking.query.filter_by(
        student_id=current_user.id
    ).order_by(Booking.booked_at.desc()).all()
    return render_template(
        "student/bookings.html",
        bookings=booking_history,
        today=date.today(),
        active_page="bookings",
    )


@student_bp.route("/results")
@role_required("student")
def results():
    published_results = (
        Booking.query.join(Exam, Booking.exam_id == Exam.id)
        .filter(
            Booking.student_id == current_user.id,
            Exam.results_published.is_(True),
            Booking.evaluation.has(),
        )
        .order_by(Booking.booked_at.desc())
        .all()
    )
    return render_template(
        "student/results.html",
        bookings=published_results,
        active_page="results",
    )


@student_bp.route("/results/<int:booking_id>/scorecard")
@role_required("student")
def scorecard(booking_id):
    booking = get_published_booking(booking_id)
    if booking is None:
        abort(404)
    scores = sorted(
        booking.evaluation.rubric_scores, key=lambda score: score.rubric.id
    )
    return render_template(
        "student/scorecard.html",
        booking=booking,
        scores=scores,
        percentage=booking.evaluation.total_marks / booking.exam.max_marks * 100,
        active_page="results",
    )


@student_bp.route("/results/<int:booking_id>/download")
@role_required("student")
def download_scorecard(booking_id):
    booking = get_published_booking(booking_id)
    if booking is None:
        abort(404)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Examination Management Portal - Scorecard"])
    writer.writerow(["Student", booking.student.name])
    writer.writerow(["Email", booking.student.email])
    writer.writerow(["Roll number", booking.student.roll_no or ""])
    writer.writerow(
        ["Course", f"{booking.exam.course.code} - {booking.exam.course.name}"]
    )
    writer.writerow(["Exam", booking.exam.name])
    writer.writerow(["Examiner", booking.evaluation.examiner.name])
    writer.writerow(["Exam date", booking.slot.date.isoformat()])
    writer.writerow([])
    writer.writerow(["Criterion", "Marks", "Maximum marks"])
    for score in sorted(
        booking.evaluation.rubric_scores, key=lambda row: row.rubric.id
    ):
        writer.writerow([score.rubric.criterion_name, score.marks, score.rubric.max_marks])
    writer.writerow([])
    writer.writerow(["Total marks", booking.evaluation.total_marks, booking.exam.max_marks])
    writer.writerow(
        [
            "Percentage",
            f"{booking.evaluation.total_marks / booking.exam.max_marks * 100:.2f}%",
        ]
    )
    writer.writerow(["Remarks", booking.evaluation.remarks or ""])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = (
        f"attachment; filename=scorecard_{booking.id}.csv"
    )
    return response


def get_published_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if (
        booking is None
        or booking.student_id != current_user.id
        or not booking.exam.results_published
        or booking.evaluation is None
    ):
        return None
    return booking


@student_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@role_required("student")
def cancel_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.student_id != current_user.id:
        abort(403)
    if booking.status != "Booked":
        flash("Only active bookings can be cancelled.", "warning")
        return redirect(url_for("student.bookings"))
    if booking.evaluation is not None:
        flash("This booking has already been evaluated and cannot be cancelled.", "danger")
        return redirect(url_for("student.bookings"))
    if date.today() >= booking.exam.booking_end:
        flash("A booking can only be cancelled before the booking end date.", "danger")
        return redirect(url_for("student.bookings"))

    slot = booking.slot
    booking.status = "Cancelled"
    booking.cancelled_at = datetime.utcnow()
    db.session.flush()
    update_slot_status(slot)
    db.session.commit()
    flash("Booking cancelled. The slot is available again.", "success")
    return redirect(url_for("student.bookings"))


@student_bp.route("/schedule")
@role_required("student")
def schedule():
    today = date.today()
    upcoming_bookings = Booking.query.join(Slot).filter(
        Booking.student_id == current_user.id,
        Booking.status == "Booked",
        Slot.date >= today,
    ).order_by(Slot.date.asc(), Slot.start_time.asc()).all()
    return render_template(
        "student/schedule.html",
        bookings=upcoming_bookings,
        active_page="schedule",
    )


@student_bp.route("/profile", methods=["GET", "POST"])
@role_required("student")
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not name:
            errors.append("Name is required.")

        if old_password or new_password or confirm_password:
            if not old_password or not current_user.check_password(old_password):
                errors.append("Enter your current password correctly.")
            if len(new_password) < 6:
                errors.append("New password must be at least 6 characters long.")
            if new_password != confirm_password:
                errors.append("New password and confirmation do not match.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "student/profile.html",
                form_values=request.form,
                active_page="profile",
            ), 400

        current_user.name = name
        current_user.phone = phone or None
        if new_password:
            current_user.set_password(new_password)
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("student.profile"))

    return render_template(
        "student/profile.html",
        active_page="profile",
    )

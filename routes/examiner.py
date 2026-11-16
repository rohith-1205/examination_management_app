from datetime import date, datetime, time
from math import isfinite

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from models import (
    Booking,
    Evaluation,
    Exam,
    ExamExaminer,
    Rubric,
    RubricScore,
    Slot,
    db,
)
from utils import role_required, update_slot_status

examiner_bp = Blueprint("examiner", __name__)


@examiner_bp.route("/dashboard")
@role_required("examiner")
def dashboard():
    exam_ids = db.session.query(ExamExaminer.exam_id).filter_by(
        examiner_id=current_user.id
    )
    assigned_exams = Exam.query.filter(Exam.id.in_(exam_ids)).order_by(
        Exam.slot_creation_start.asc()
    ).all()
    slots_created = Slot.query.filter_by(examiner_id=current_user.id).count()
    students_booked = (
        db.session.query(func.count(func.distinct(Booking.student_id)))
        .join(Slot, Booking.slot_id == Slot.id)
        .filter(
            Slot.examiner_id == current_user.id,
            Booking.status.in_(("Booked", "Completed")),
        )
        .scalar()
        or 0
    )
    pending_evaluations = (
        Booking.query.join(Slot, Booking.slot_id == Slot.id)
        .filter(
            Slot.examiner_id == current_user.id,
            Slot.date <= date.today(),
            Booking.status == "Booked",
            ~Booking.evaluation.has(),
        )
        .count()
    )
    upcoming_slots = Slot.query.filter(
        Slot.examiner_id == current_user.id,
        Slot.date >= date.today(),
        Slot.status.notin_(("Cancelled", "Completed")),
    ).order_by(Slot.date.asc(), Slot.start_time.asc()).limit(8).all()

    return render_template(
        "examiner/dashboard.html",
        assigned_exams=assigned_exams,
        upcoming_slots=upcoming_slots,
        stats={
            "assigned_exams": len(assigned_exams),
            "slots_created": slots_created,
            "students_booked": students_booked,
            "pending_evaluations": pending_evaluations,
        },
        active_page="dashboard",
    )


@examiner_bp.route("/exams/<int:exam_id>/slots", methods=["GET", "POST"])
@role_required("examiner")
def exam_slots(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if not is_assigned(exam):
        abort(403)

    slots = Slot.query.filter_by(
        exam_id=exam.id, examiner_id=current_user.id
    ).order_by(Slot.date.asc(), Slot.start_time.asc()).all()
    can_create, disabled_message = slot_creation_access(exam)

    if request.method == "POST":
        if not can_create:
            flash(disabled_message, "warning")
            return redirect(url_for("examiner.exam_slots", exam_id=exam.id))

        values, errors = validate_slot_form(exam)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "examiner/exam_slots.html",
                exam=exam,
                slots=slots,
                can_create=can_create,
                disabled_message=disabled_message,
                form_values=request.form,
                active_page="exams",
            ), 400

        slot = Slot(
            exam=exam,
            examiner_id=current_user.id,
            date=values["date"],
            start_time=values["start_time"],
            end_time=values["end_time"],
            capacity=values["capacity"],
            available_seats=values["capacity"],
            status="Available",
        )
        db.session.add(slot)
        update_slot_status(slot)
        db.session.commit()
        flash("Slot created successfully.", "success")
        return redirect(url_for("examiner.exam_slots", exam_id=exam.id))

    return render_template(
        "examiner/exam_slots.html",
        exam=exam,
        slots=slots,
        can_create=can_create,
        disabled_message=disabled_message,
        active_page="exams",
    )


@examiner_bp.route("/slots/<int:slot_id>/edit", methods=["GET", "POST"])
@role_required("examiner")
def edit_slot(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    if slot.examiner_id != current_user.id:
        abort(403)

    allowed, message = slot_edit_access(slot)
    if not allowed:
        flash(message, "warning")
        return redirect(url_for("examiner.exam_slots", exam_id=slot.exam_id))

    if request.method == "POST":
        values, errors = validate_slot_form(slot.exam, slot)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "examiner/slot_form.html",
                slot=slot,
                exam=slot.exam,
                form_values=request.form,
                active_page="exams",
            ), 400

        slot.date = values["date"]
        slot.start_time = values["start_time"]
        slot.end_time = values["end_time"]
        slot.capacity = values["capacity"]
        update_slot_status(slot)
        db.session.commit()
        flash("Slot updated successfully.", "success")
        return redirect(url_for("examiner.exam_slots", exam_id=slot.exam_id))

    return render_template(
        "examiner/slot_form.html",
        slot=slot,
        exam=slot.exam,
        active_page="exams",
    )


@examiner_bp.route("/slots/<int:slot_id>/delete", methods=["POST"])
@role_required("examiner")
def delete_slot(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    if slot.examiner_id != current_user.id:
        abort(403)

    allowed, message = slot_edit_access(slot)
    if not allowed:
        flash(message, "warning")
    elif slot.bookings:
        flash("A slot with bookings cannot be deleted.", "danger")
    else:
        exam_id = slot.exam_id
        db.session.delete(slot)
        db.session.commit()
        flash("Slot deleted successfully.", "success")
        return redirect(url_for("examiner.exam_slots", exam_id=exam_id))

    return redirect(url_for("examiner.exam_slots", exam_id=slot.exam_id))


@examiner_bp.route("/slots/<int:slot_id>/students")
@role_required("examiner")
def slot_students(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    if slot.examiner_id != current_user.id:
        abort(403)

    bookings = Booking.query.filter(
        Booking.slot_id == slot.id,
        Booking.status.in_(("Booked", "Completed")),
    ).order_by(Booking.booked_at.asc()).all()
    return render_template(
        "examiner/slot_students.html",
        slot=slot,
        bookings=bookings,
        active_page="exams",
    )


@examiner_bp.route("/evaluations")
@role_required("examiner")
def evaluations():
    pending = (
        Booking.query.join(Slot, Booking.slot_id == Slot.id)
        .filter(
            Slot.examiner_id == current_user.id,
            Slot.date <= date.today(),
            Booking.status == "Booked",
            ~Booking.evaluation.has(),
        )
        .order_by(Slot.date.asc(), Slot.start_time.asc())
        .all()
    )
    evaluated = (
        Booking.query.join(Slot, Booking.slot_id == Slot.id)
        .join(Evaluation, Evaluation.booking_id == Booking.id)
        .filter(
            Slot.examiner_id == current_user.id,
        )
        .order_by(Evaluation.evaluated_at.desc())
        .all()
    )
    return render_template(
        "examiner/evaluations.html",
        pending=pending,
        evaluated=evaluated,
        active_page="evaluations",
    )


@examiner_bp.route("/evaluate/<int:booking_id>", methods=["GET", "POST"])
@role_required("examiner")
def evaluate(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.slot.examiner_id != current_user.id:
        abort(403)

    evaluation = booking.evaluation
    if evaluation and booking.exam.results_published:
        flash("Published results can no longer be changed.", "warning")
        return redirect(url_for("examiner.evaluations"))
    if evaluation is None and booking.status != "Booked":
        flash("Only active bookings can be evaluated.", "warning")
        return redirect(url_for("examiner.evaluations"))
    if evaluation is None and booking.slot.date > date.today():
        flash("This booking can only be evaluated on or after its slot date.", "warning")
        return redirect(url_for("examiner.evaluations"))

    rubrics = Rubric.query.filter_by(exam_id=booking.exam_id).order_by(Rubric.id.asc()).all()
    existing_scores = {}
    if evaluation:
        existing_scores = {
            score.rubric_id: score.marks for score in evaluation.rubric_scores
        }
    form_values = {
        f"rubric_{rubric.id}": existing_scores.get(rubric.id, "")
        for rubric in rubrics
    }

    if request.method == "POST":
        errors = []
        scores = []
        for rubric in rubrics:
            value = request.form.get(f"rubric_{rubric.id}", "").strip()
            try:
                marks = float(value)
            except ValueError:
                errors.append(f"Enter valid marks for {rubric.criterion_name}.")
                continue
            if not isfinite(marks) or marks < 0 or marks > rubric.max_marks:
                errors.append(
                    f"Marks for {rubric.criterion_name} must be between 0 and {rubric.max_marks}."
                )
                continue
            scores.append((rubric, marks))

        if not rubrics:
            errors.append("Add rubric criteria to this exam before evaluating students.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "examiner/evaluate.html",
                booking=booking,
                rubrics=rubrics,
                evaluation=evaluation,
                form_values=request.form,
                active_page="evaluations",
            ), 400

        if evaluation is None:
            evaluation = Evaluation(
                booking=booking,
                examiner_id=current_user.id,
                total_marks=sum(marks for _, marks in scores),
            )
            db.session.add(evaluation)
        else:
            evaluation.rubric_scores.clear()

        evaluation.examiner_id = current_user.id
        evaluation.total_marks = sum(marks for _, marks in scores)
        evaluation.remarks = request.form.get("remarks", "").strip() or None
        evaluation.evaluated_at = datetime.utcnow()
        evaluation.rubric_scores.extend(
            RubricScore(rubric=rubric, marks=marks)
            for rubric, marks in scores
        )
        booking.status = "Completed"

        slot = booking.slot
        active_bookings = [
            item for item in slot.bookings
            if item.status in ("Booked", "Completed")
        ]
        if active_bookings and all(
            item.status == "Completed" for item in active_bookings
        ):
            slot.status = "Completed"

        db.session.commit()
        flash("Evaluation saved successfully.", "success")
        return redirect(url_for("examiner.evaluations"))

    return render_template(
        "examiner/evaluate.html",
        booking=booking,
        rubrics=rubrics,
        evaluation=evaluation,
        form_values=form_values,
        active_page="evaluations",
    )


def is_assigned(exam):
    return ExamExaminer.query.filter_by(
        exam_id=exam.id, examiner_id=current_user.id
    ).first() is not None


def slot_creation_access(exam):
    today = date.today()
    if exam.status != "Slot Creation":
        return False, "Slots can only be created while this exam is in Slot Creation status."
    if not exam.slot_creation_start <= today <= exam.slot_creation_end:
        return False, (
            "Slots can only be created between "
            f"{exam.slot_creation_start:%b %d, %Y} and "
            f"{exam.slot_creation_end:%b %d, %Y}."
        )
    return True, ""


def slot_edit_access(slot):
    if slot.exam.status in ("Booking Open", "Closed", "Completed"):
        return False, "Slots cannot be edited or deleted after booking starts."
    if slot.bookings:
        return False, "Slots with bookings cannot be edited or deleted."
    return True, ""


def validate_slot_form(exam, slot=None):
    form = request.form
    errors = []
    try:
        slot_date = date.fromisoformat(form.get("date", ""))
    except ValueError:
        slot_date = None
        errors.append("Enter a valid slot date.")

    try:
        start_time = time.fromisoformat(form.get("start_time", ""))
    except ValueError:
        start_time = None
        errors.append("Enter a valid start time.")

    try:
        end_time = time.fromisoformat(form.get("end_time", ""))
    except ValueError:
        end_time = None
        errors.append("Enter a valid end time.")

    try:
        capacity = int(form.get("capacity", ""))
        if capacity < 1:
            errors.append("Capacity must be at least one.")
    except ValueError:
        capacity = 0
        errors.append("Enter a valid slot capacity.")

    if slot_date is not None and slot_date <= exam.booking_start:
        errors.append("Slot date must be after the booking start date.")
    if start_time is not None and end_time is not None and end_time <= start_time:
        errors.append("End time must be after start time.")

    if slot_date is not None and start_time is not None and end_time is not None:
        overlapping_slot = Slot.query.filter(
            Slot.examiner_id == current_user.id,
            Slot.date == slot_date,
            Slot.start_time < end_time,
            Slot.end_time > start_time,
        )
        if slot is not None:
            overlapping_slot = overlapping_slot.filter(Slot.id != slot.id)
        if overlapping_slot.first():
            errors.append("This time overlaps another slot on your schedule.")

    return {
        "date": slot_date,
        "start_time": start_time,
        "end_time": end_time,
        "capacity": capacity,
    }, errors

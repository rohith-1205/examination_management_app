from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('admin', 'examiner', 'student')", name="ck_user_role"
        ),
        db.CheckConstraint(
            "status IN ('pending', 'active', 'inactive')", name="ck_user_status"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    roll_no = db.Column(db.String(30), unique=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    assigned_exams = db.relationship(
        "ExamExaminer", back_populates="examiner", cascade="all, delete-orphan"
    )
    slots = db.relationship("Slot", back_populates="examiner")
    bookings = db.relationship(
        "Booking", back_populates="student", foreign_keys="Booking.student_id"
    )
    evaluations = db.relationship("Evaluation", back_populates="examiner")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Course(db.Model):
    __table_args__ = (
        db.CheckConstraint("status IN ('Active', 'Inactive')", name="ck_course_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="Active")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    exams = db.relationship("Exam", back_populates="course", cascade="all, delete-orphan")


class Exam(db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "exam_type IN ('Viva', 'Practical', 'Project Demo', 'Assessment')",
            name="ck_exam_type",
        ),
        db.CheckConstraint(
            "status IN ('Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed')",
            name="ck_exam_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    exam_type = db.Column(db.String(30), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    slot_creation_start = db.Column(db.Date, nullable=False)
    slot_creation_end = db.Column(db.Date, nullable=False)
    booking_start = db.Column(db.Date, nullable=False)
    booking_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Draft")
    results_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    course = db.relationship("Course", back_populates="exams")
    examiner_assignments = db.relationship(
        "ExamExaminer", back_populates="exam", cascade="all, delete-orphan"
    )
    rubrics = db.relationship("Rubric", back_populates="exam", cascade="all, delete-orphan")
    slots = db.relationship("Slot", back_populates="exam", cascade="all, delete-orphan")
    bookings = db.relationship("Booking", back_populates="exam")


class ExamExaminer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("exam_id", "examiner_id", name="uq_exam_examiner"),
    )

    exam = db.relationship("Exam", back_populates="examiner_assignments")
    examiner = db.relationship("User", back_populates="assigned_exams")


class Rubric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    criterion_name = db.Column(db.String(100), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    weightage = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)

    exam = db.relationship("Exam", back_populates="rubrics")
    scores = db.relationship("RubricScore", back_populates="rubric")


class Slot(db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('Available', 'Full', 'Cancelled', 'Completed')",
            name="ck_slot_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Available")

    exam = db.relationship("Exam", back_populates="slots")
    examiner = db.relationship("User", back_populates="slots")
    bookings = db.relationship("Booking", back_populates="slot")


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("slot.id"), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    booked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="Booked")
    cancelled_at = db.Column(db.DateTime)
    rescheduled = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('Booked', 'Cancelled', 'Completed')", name="ck_booking_status"
        ),
        db.Index(
            "uq_active_booking_student_exam",
            "student_id",
            "exam_id",
            unique=True,
            sqlite_where=db.text("status = 'Booked'"),
        ),
    )

    student = db.relationship(
        "User", back_populates="bookings", foreign_keys=[student_id]
    )
    slot = db.relationship("Slot", back_populates="bookings")
    exam = db.relationship("Exam", back_populates="bookings")
    evaluation = db.relationship(
        "Evaluation", back_populates="booking", uselist=False, cascade="all, delete-orphan"
    )


class Evaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(
        db.Integer, db.ForeignKey("booking.id"), unique=True, nullable=False
    )
    examiner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total_marks = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text)
    evaluated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    booking = db.relationship("Booking", back_populates="evaluation")
    examiner = db.relationship("User", back_populates="evaluations")
    rubric_scores = db.relationship(
        "RubricScore", back_populates="evaluation", cascade="all, delete-orphan"
    )


class RubricScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey("evaluation.id"), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubric.id"), nullable=False)
    marks = db.Column(db.Float, nullable=False)

    evaluation = db.relationship("Evaluation", back_populates="rubric_scores")
    rubric = db.relationship("Rubric", back_populates="scores")

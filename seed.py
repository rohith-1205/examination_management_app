from datetime import date, datetime, time, timedelta

from models import (
    Booking,
    Course,
    Evaluation,
    Exam,
    ExamExaminer,
    Rubric,
    RubricScore,
    Slot,
    User,
    db,
)


def seed_data():
    if User.query.filter_by(role="admin").first():
        return

    today = date.today()

    admin = User(
        name="EMP Administrator",
        email="admin@emp.com",
        role="admin",
        phone="9876543210",
        status="active",
    )
    admin.set_password("admin123")

    examiners = [
        User(
            name="Dr. Ananya Rao",
            email="ananya.rao@emp.com",
            role="examiner",
            phone="9876543211",
            department="Computer Science",
            status="active",
        ),
        User(
            name="Prof. Karthik Iyer",
            email="karthik.iyer@emp.com",
            role="examiner",
            phone="9876543212",
            department="Computer Science",
            status="active",
        ),
        User(
            name="Dr. Meera Nair",
            email="meera.nair@emp.com",
            role="examiner",
            phone="9876543213",
            department="Information Technology",
            status="pending",
        ),
    ]
    for examiner in examiners:
        examiner.set_password("examiner123")

    students = [
        User(
            name="Aarav Sharma",
            email="aarav.sharma@emp.com",
            role="student",
            phone="9876543214",
            roll_no="24F2001001",
            status="active",
        ),
        User(
            name="Diya Patel",
            email="diya.patel@emp.com",
            role="student",
            phone="9876543215",
            roll_no="24F2001002",
            status="active",
        ),
        User(
            name="Ishaan Kumar",
            email="ishaan.kumar@emp.com",
            role="student",
            phone="9876543216",
            roll_no="24F2001003",
            status="active",
        ),
        User(
            name="Sana Thomas",
            email="sana.thomas@emp.com",
            role="student",
            phone="9876543217",
            roll_no="24F2001004",
            status="active",
        ),
    ]
    for student in students:
        student.set_password("student123")

    mad = Course(
        code="MAD-1",
        name="Modern Application Development I",
        description="Flask, web application development, and application design.",
    )
    dbms = Course(
        code="DBMS",
        name="Database Management Systems",
        description="Relational data, SQL, and database design.",
    )
    python = Course(
        code="PYTHON",
        name="Programming with Python",
        description="Python programming fundamentals and problem solving.",
    )

    slot_creation_exam = Exam(
        course=mad,
        name="MAD-1 Viva Examination",
        exam_type="Viva",
        duration_minutes=20,
        max_marks=100,
        slot_creation_start=today - timedelta(days=2),
        slot_creation_end=today + timedelta(days=10),
        booking_start=today + timedelta(days=11),
        booking_end=today + timedelta(days=20),
        status="Slot Creation",
    )
    booking_open_exam = Exam(
        course=dbms,
        name="DBMS Practical Assessment",
        exam_type="Practical",
        duration_minutes=60,
        max_marks=100,
        slot_creation_start=today - timedelta(days=14),
        slot_creation_end=today - timedelta(days=8),
        booking_start=today - timedelta(days=2),
        booking_end=today + timedelta(days=5),
        status="Booking Open",
    )
    completed_exam = Exam(
        course=python,
        name="Python Programming Assessment",
        exam_type="Assessment",
        duration_minutes=45,
        max_marks=100,
        slot_creation_start=today - timedelta(days=50),
        slot_creation_end=today - timedelta(days=45),
        booking_start=today - timedelta(days=44),
        booking_end=today - timedelta(days=40),
        status="Completed",
        results_published=True,
    )
    draft_exam = Exam(
        course=mad,
        name="MAD-1 Project Demonstration",
        exam_type="Project Demo",
        duration_minutes=30,
        max_marks=100,
        slot_creation_start=today + timedelta(days=20),
        slot_creation_end=today + timedelta(days=27),
        booking_start=today + timedelta(days=28),
        booking_end=today + timedelta(days=35),
        status="Draft",
    )
    exams = [slot_creation_exam, booking_open_exam, completed_exam, draft_exam]

    rubric_names = [
        ("Technical understanding", "Explains the key concepts and design decisions."),
        ("Implementation quality", "Demonstrates a correct and organized implementation."),
        ("Communication", "Presents the work clearly and answers questions."),
    ]
    for exam in exams:
        for criterion_name, description in rubric_names:
            exam.rubrics.append(
                Rubric(
                    criterion_name=criterion_name,
                    max_marks=35 if criterion_name != "Communication" else 30,
                    weightage=35.0 if criterion_name != "Communication" else 30.0,
                    description=description,
                )
            )

    assignments = [
        ExamExaminer(exam=slot_creation_exam, examiner=examiners[0]),
        ExamExaminer(exam=slot_creation_exam, examiner=examiners[1]),
        ExamExaminer(exam=booking_open_exam, examiner=examiners[0]),
        ExamExaminer(exam=completed_exam, examiner=examiners[1]),
        ExamExaminer(exam=draft_exam, examiner=examiners[0]),
    ]

    slots = [
        Slot(
            exam=slot_creation_exam,
            examiner=examiners[0],
            date=today + timedelta(days=22),
            start_time=time(9, 0),
            end_time=time(9, 20),
            capacity=4,
            available_seats=4,
            status="Available",
        ),
        Slot(
            exam=slot_creation_exam,
            examiner=examiners[1],
            date=today + timedelta(days=22),
            start_time=time(10, 0),
            end_time=time(10, 20),
            capacity=4,
            available_seats=4,
            status="Available",
        ),
        Slot(
            exam=booking_open_exam,
            examiner=examiners[0],
            date=today + timedelta(days=8),
            start_time=time(9, 0),
            end_time=time(10, 0),
            capacity=3,
            available_seats=1,
            status="Available",
        ),
        Slot(
            exam=completed_exam,
            examiner=examiners[1],
            date=today - timedelta(days=30),
            start_time=time(13, 0),
            end_time=time(13, 45),
            capacity=1,
            available_seats=0,
            status="Completed",
        ),
    ]

    bookings = [
        Booking(student=students[0], slot=slots[2], exam=booking_open_exam),
        Booking(student=students[1], slot=slots[2], exam=booking_open_exam),
        Booking(
            student=students[2],
            slot=slots[3],
            exam=completed_exam,
            status="Completed",
            booked_at=datetime.combine(today - timedelta(days=42), time(10, 0)),
        ),
    ]

    completed_evaluation = Evaluation(
        booking=bookings[2],
        examiner=examiners[1],
        total_marks=84,
        remarks="Strong understanding and a clear, well-structured solution.",
        evaluated_at=datetime.combine(today - timedelta(days=30), time(14, 0)),
    )
    completed_evaluation.rubric_scores = [
        RubricScore(rubric=completed_exam.rubrics[0], marks=30),
        RubricScore(rubric=completed_exam.rubrics[1], marks=29),
        RubricScore(rubric=completed_exam.rubrics[2], marks=25),
    ]

    db.session.add_all(
        [admin, *examiners, *students, mad, dbms, python, *assignments, *slots, *bookings]
    )
    db.session.add(completed_evaluation)
    db.session.commit()

    print("Default EMP login credentials:")
    print("Admin: admin@emp.com / admin123")
    print("Examiner: ananya.rao@emp.com / examiner123")
    print("Student: aarav.sharma@emp.com / student123")

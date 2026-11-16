# Examination Management Portal

A Flask application for managing examination courses, exam schedules, examiner assignments, student bookings, evaluations, and published results. It uses Flask-SQLAlchemy with SQLite, Flask-Login for role-based access, and Jinja templates with Bootstrap 5.

## Run the application

From the project root, create and activate a virtual environment in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The application starts in debug mode at `http://127.0.0.1:5000`. On startup, `app.py` creates the `instance` directory, runs `db.create_all()`, and seeds sample data only when an admin account does not already exist. The SQLite database is stored at `instance/emp.db`.

### Default seed logins

| Role | Email | Password |
|---|---|---|
| Admin | `admin@emp.com` | `admin123` |
| Examiner | `ananya.rao@emp.com` | `examiner123` |
| Student | `aarav.sharma@emp.com` | `student123` |

Seeded credentials are printed in the console on the first seed run. The admin account is pre-created and cannot be registered through the public registration page.

## Folder structure

```text
app.py                  Flask app setup, blueprints, database initialization, and error pages
config.py               Flask and SQLite configuration
models.py               SQLAlchemy models and relationships
seed.py                 Relative-date sample data
utils.py                Role access decorator and slot seat/status helper
routes/
  __init__.py
  auth.py               Login, registration, and logout
  admin.py              Admin dashboards and management routes
  examiner.py           Examiner slots and evaluation routes
  student.py            Student booking, profile, and results routes
  api.py                Login-protected JSON API
templates/
  admin/                Admin pages, including statistics charts
  auth/                 Login, registration, and pending-approval pages
  errors/               Themed 403 and 404 pages
  examiner/             Examiner schedule and evaluation pages
  student/              Student exams, bookings, results, and scorecards
  base.html             Shared navigation, flash messages, and footer
  index.html            Public landing page
static/css/style.css    Shared theme and responsive page styles
requirements.txt        Python dependencies
instance/emp.db         Automatically-created SQLite database (not committed)
```

## JSON API

All API routes require an authenticated session. Course write operations require the admin role. Send and receive JSON for course create/update operations. API errors use a JSON `error` field.

| Method | Endpoint | Access | Success |
|---|---|---|---|
| GET | `/api/courses` | Login required | `200`, course list |
| GET | `/api/courses/<id>` | Login required | `200`, course details; `404` if missing |
| POST | `/api/courses` | Admin | `201`, created course; `400` for invalid or duplicate data |
| PUT | `/api/courses/<id>` | Admin | `200`, updated course; `400` for invalid or duplicate data; `404` if missing |
| DELETE | `/api/courses/<id>` | Admin | `200`, deleted course or deactivated course if exams exist; `404` if missing |
| GET | `/api/exams` | Login required | `200`, exam list |
| GET | `/api/exams/<id>` | Login required | `200`, exam with rubrics and assigned examiners; `404` if missing |
| GET | `/api/examiners` | Login required | `200`, examiner list |
| GET | `/api/students` | Login required | `200`, student list |
| GET | `/api/bookings` | Login required | `200`, booking history |

Course POST and PUT accept `code`, `name`, optional `description`, and `status` (`Active` or `Inactive`). PUT expects the same course fields as POST.

## Feature and requirement map

| Requirement | Route or file |
|---|---|
| Flask setup, debug run, configuration, blueprint registration, automatic database creation, and seeding | `app.py`, `config.py`, `seed.py` |
| User roles and password hashing; courses, exams, examiner assignments, rubrics, slots, bookings, evaluations, and rubric scores | `models.py` |
| Shared role protection and slot seat/status updates | `utils.py` |
| Gradient shared navigation, role links, flash alerts, footer, landing page, and theme | `templates/base.html`, `templates/index.html`, `static/css/style.css` |
| Login by role, examiner approval status, student/examiner registration, and logout | `routes/auth.py`, `templates/auth/` |
| Admin counts, recent bookings, and shortcuts | `/admin/dashboard` in `routes/admin.py`, `templates/admin/dashboard.html` |
| Course list/search/create/edit/delete or deactivate-if-used | `/admin/courses*` in `routes/admin.py`, `templates/admin/courses.html`, `templates/admin/course_form.html`, `templates/admin/course_delete.html` |
| Exam list/filter/search, create/edit validation, guarded deletion, dates/timeline, status transitions, examiner assignment, and rubric management | `/admin/exams*` in `routes/admin.py`, `templates/admin/exams.html`, `templates/admin/exam_form.html`, `templates/admin/exam_detail.html`, `templates/admin/rubric_form.html` |
| Examiner approval, deactivation/reactivation, and direct examiner creation | `/admin/examiners*` in `routes/admin.py`, `templates/admin/examiners.html`, `templates/admin/examiner_form.html` |
| Student search and full booking history | `/admin/students*` in `routes/admin.py`, `templates/admin/students.html`, `templates/admin/student_detail.html` |
| Slot filters, seat progress, and assigned-examiner changes guarded against evaluated bookings | `/admin/slots*` in `routes/admin.py`, `templates/admin/slots.html`, `templates/admin/slot_examiner_form.html` |
| Booking search/history and same-exam rescheduling with seat updates | `/admin/bookings*` in `routes/admin.py`, `templates/admin/bookings.html`, `templates/admin/booking_reschedule.html` |
| Global student/examiner/exam/booking search | `/admin/search` in `routes/admin.py`, `templates/admin/search.html` |
| Examiner overview, assigned exam slots, slot creation/edit/delete validation, and booked student list | `/examiner/dashboard`, `/examiner/exams/<id>/slots`, `/examiner/slots/<id>/students` in `routes/examiner.py`, `templates/examiner/` |
| Pending/evaluated lists, rubric score validation, total calculation, evaluation editing until publication, and slot completion | `/examiner/evaluations`, `/examiner/evaluate/<booking_id>` in `routes/examiner.py`, `templates/examiner/evaluations.html`, `templates/examiner/evaluate.html` |
| Student dashboard/exam catalogue/detail, booking/cancellation/history, schedule, and profile/password update | `/student/*` in `routes/student.py`, corresponding templates in `templates/student/` |
| Published results, criterion progress, printable scorecard, and CSV download | `/student/results*` in `routes/student.py`, `templates/student/results.html`, `templates/student/scorecard.html` |
| Evaluation progress, average marks, and publication only after exam completion | `/admin/exams/<id>` and `/admin/exams/<id>/status` in `routes/admin.py`, `templates/admin/exam_detail.html` |
| Login-protected JSON reads and admin-only course writes | `/api/*` in `routes/api.py` |
| Bookings-per-exam, examiner workload, and exam-status charts; Chart.js is limited to this optional feature | `/admin/stats` in `routes/admin.py`, `templates/admin/stats.html` |
| Themed access-denied and missing-page responses | `app.py`, `templates/errors/403.html`, `templates/errors/404.html` |
| Responsive tables, empty states, badges, cards, and shared visual styling | `templates/`, `static/css/style.css` |

Core portal actions use regular HTML form submissions and Flask route validation. JavaScript is only used for Bootstrap's optional navigation/alert behavior and the optional Chart.js statistics page.

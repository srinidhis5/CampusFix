# CampusFix: Campus Complaint and Maintenance Management System

CampusFix is a Flask-based college Software Engineering project for reporting and managing campus maintenance complaints.

## Problem Statement

Students and staff need a clear way to report maintenance issues and track whether they are assigned, repaired, resolved and closed. Manual reporting makes it hard to prioritize urgent issues, measure workload, and keep a reliable history.

## Objectives

- Allow reporters to submit and track complaints.
- Allow administrators to assign, monitor, report and audit work.
- Allow maintenance staff to update progress and resolve assigned tasks.
- Enforce secure role-based permissions in backend routes.
- Provide feedback, notifications, reports, CSV export and automated tests.

## Main Features

- Reporter registration, login and dashboards.
- Complaint submission with image upload, due date calculation, duplicate warnings and AI suggestions.
- Complaint search and filters by status, category, priority, location and assignee.
- Administrator assignment, reassignment, priority updates, ML correction review, user management and audit log.
- Maintenance dashboard, assigned work list, progress notes and completion proof upload.
- Valid workflow transitions: Submitted, Assigned, In Progress, Resolved, Closed and Reopened.
- In-app notifications, feedback ratings, charts and CSV export.

## User Roles

- Reporter: submits complaints, views own complaints, adds feedback and can reopen once.
- Administrator: manages all complaints, users, reports, assignments and audit records.
- Maintenance Staff: sees only assigned complaints and updates work progress.

## Technology Used

Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Werkzeug password hashing, SQLite, Jinja2, HTML5, CSS3, Bootstrap 5, vanilla JavaScript, Chart.js and Pytest.

## Architecture

The app uses a simple Flask application factory with blueprints:

- `auth`: login, logout and reporter registration.
- `reporter`: reporter dashboard, complaints, feedback and notifications.
- `admin`: administrator dashboard, reports, assignment, users and audit log.
- `maintenance`: assigned complaints and progress updates.
- `services`: complaint workflow, notification and reporting helpers.

## Database Models

- `User`: account, password hash, role, department, phone and active status.
- `Complaint`: reference number, details, priority, status, reporter, assignee, dates and upload names.
- `ComplaintUpdate`: status and progress history.
- `Feedback`: one reporter rating/comment per complaint.
- `Notification`: in-application notifications.
- `AuditLog`: important actions performed in the system.
- `PredictionLog`: AI suggestion, final submitted labels, confidence values and correction status.

## ML Module

CampusFix exposes `POST /predict` for authenticated users. It accepts JSON with `title` and `description`, then returns suggested category, priority, confidence values and confidence labels:

- `>= 80`: High confidence
- `60-80`: Please verify
- `< 60`: Low confidence, select manually

The submit form calls this route after a 600 ms debounce once the text has at least 15 characters. Suggestions fill editable dropdowns only when confidence is at least 60%; low-confidence fields are left blank for manual choice. Submitted complaints store both the AI suggestion and the final user-selected labels in `predictions_log`.

Model files can be saved as:

```text
models/category_model.pkl
models/priority_model.pkl
models/metrics.json
```

Until trained sklearn models are present, the app uses a deterministic keyword fallback so the website remains usable. This fallback is not a production ML model.

Admin users can open **ML Insights** to view model metrics, confusion matrix images from `reports/`, correction rate, and the review queue of corrected labels. Corrected rows can be exported to `data/review_queue.csv` for manual verification before future retraining.

Important limitation: synthetic or small datasets can inflate scores. Use a stratified unseen test set, inspect Emergency recall separately, and do not auto-retrain from user corrections without review.

## Complaint Workflow

Valid transitions are enforced in `app/services/complaint_service.py`:

- Submitted to Assigned: administrator only.
- Assigned to In Progress: assigned maintenance staff or administrator.
- In Progress to Resolved: assigned maintenance staff or administrator.
- Resolved to Closed: reporter or administrator.
- Resolved to Reopened: reporter or administrator.
- Reopened to Assigned: administrator only.

Every status change creates a `ComplaintUpdate` and an `AuditLog` entry.

## Agile Model

The project follows the Agile model. Every sprint follows:

Requirements -> Planning -> Design -> Coding -> Testing -> Review -> Updated backlog

| Sprint | Work completed |
| --- | --- |
| Sprint 1 | Requirements, project setup, database design, authentication and roles |
| Sprint 2 | Complaint submission, complaint listing, search, filters and complaint details |
| Sprint 3 | Assignment, status workflow, progress history and notifications |
| Sprint 4 | Dashboards, reports, feedback and CSV export |
| Sprint 5 | Attachments, duplicate warnings, security checks, testing, documentation and final corrections |

## Folder Structure

```text
campusfix/
  app/
    __init__.py
    models.py
    decorators.py
    extensions.py
    auth/
    reporter/
    admin/
    maintenance/
    services/
    templates/
    static/
      css/
      js/
      uploads/
  src/
    preprocess.py
    predict.py
    train.py
    evaluate.py
    data_validation.py
  data/
  models/
  reports/
  tests/
  instance/
  config.py
  run.py
  seed.py
  requirements.txt
  README.md
```

## Installation

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed.py
python run.py
```

Open:

```text
http://127.0.0.1:5000
```

## Initialize the Database

The database tables are created automatically by the Flask app factory. To create a clean demo database with sample data:

```powershell
python seed.py
```

## Run Tests

```powershell
pytest -v
```

Tests use a separate temporary in-memory database.

## Security Notes

- Passwords are hashed with Werkzeug.
- CSRF protection is enabled for forms.
- Deactivated users cannot log in.
- SQLAlchemy is used for database access.
- Uploads use secure randomized filenames, image extension checks, MIME sniffing and a 5 MB limit.
- Backend route checks enforce role permissions.
- SQLite databases, environment files, cache files and uploaded files are excluded from Git.

## Current Limitations

- Email delivery is intentionally not implemented; notifications are stored in the app.
- The UI is intentionally simple for a college project.
- Uploaded files are local to the app instance.

## Future Scope

- Email or SMS notification delivery.
- Password reset workflow.
- More advanced analytics.
- Department-level admin accounts.
- Production deployment configuration.

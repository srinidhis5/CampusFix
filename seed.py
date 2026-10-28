from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import Complaint, ComplaintUpdate, Feedback, Notification, User
from app.services.complaint_service import assign_complaint, create_complaint

app = create_app()


def user(name, email, role, password, dept):
    item = User(full_name=name, email=email, role=role, department=dept, is_active=True)
    item.set_password(password)
    db.session.add(item)
    return item


with app.app_context():
    db.drop_all()
    db.create_all()

    admin = user("Campus Administrator", "admin@campusfix.local", "admin", "Admin@123", "Administration")
    staff = [
        user("Electrical Staff", "electrical@campusfix.local", "maintenance", "Staff@123", "Electrical"),
        user("Plumbing Staff", "plumbing@campusfix.local", "maintenance", "Staff@123", "Plumbing"),
        user("Network Staff", "network@campusfix.local", "maintenance", "Staff@123", "Network"),
        user("General Maintenance", "general@campusfix.local", "maintenance", "Staff@123", "Facilities"),
    ]
    reporters = [user("Student Reporter", "student@campusfix.local", "reporter", "Student@123", "CSE")]
    for i in range(2, 11):
        reporters.append(user(f"Student {i}", f"student{i}@campusfix.local", "reporter", "Student@123", "Engineering"))
    db.session.commit()

    categories = ["Electrical", "Plumbing", "Network", "Furniture", "Sanitation", "Laboratory Equipment", "Other"]
    priorities = ["Low", "Medium", "High", "Emergency"]
    statuses = ["Submitted", "Assigned", "In Progress", "Resolved", "Closed", "Reopened"]
    for i in range(30):
        reporter = reporters[i % len(reporters)]
        data = {
            "title": f"{categories[i % len(categories)]} issue in block {chr(65 + i % 5)}",
            "description": "A realistic campus maintenance issue requiring attention.",
            "category": categories[i % len(categories)],
            "building": f"Block {chr(65 + i % 5)}",
            "room_location": f"Room {100 + i}",
            "priority": priorities[i % len(priorities)],
        }
        complaint = create_complaint(reporter, data)
        target = statuses[i % len(statuses)]
        if target != "Submitted":
            assign_complaint(admin, complaint, staff[i % len(staff)].id, "Seed assignment.")
        if target in ("In Progress", "Resolved", "Closed"):
            from app.services.complaint_service import change_status

            change_status(staff[i % len(staff)], complaint, "In Progress", "Work started.")
        if target in ("Resolved", "Closed"):
            from app.services.complaint_service import change_status

            change_status(staff[i % len(staff)], complaint, "Resolved", "Issue fixed.")
            db.session.add(Feedback(complaint_id=complaint.id, reporter_id=reporter.id, rating=(i % 5) + 1, comment="Good service."))
            db.session.commit()
        if target == "Closed":
            from app.services.complaint_service import change_status

            change_status(admin, complaint, "Closed", "Closed after verification.")
        if target == "Reopened":
            complaint.status = "Reopened"
            complaint.reopen_count = 1
            db.session.add(ComplaintUpdate(complaint_id=complaint.id, actor_id=reporter.id, old_status="Resolved", new_status="Reopened", note="Problem returned."))
            db.session.commit()
        if i < 3:
            complaint.due_at = datetime.utcnow() - timedelta(hours=2)
            db.session.commit()

    db.session.add(Notification(user_id=admin.id, title="Seed data ready", message="CampusFix sample data was created."))
    db.session.commit()
    print("Seed data created.")

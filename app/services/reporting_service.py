from sqlalchemy import func

from app.models import Complaint, Feedback, User


def apply_complaint_filters(query, args):
    for field in ("status", "category", "priority", "building"):
        value = args.get(field)
        if value:
            query = query.filter(getattr(Complaint, field) == value)
    assignee = args.get("assignee_id")
    if assignee:
        query = query.filter(Complaint.assignee_id == int(assignee))
    start = args.get("start")
    end = args.get("end")
    if start:
        query = query.filter(func.date(Complaint.created_at) >= start)
    if end:
        query = query.filter(func.date(Complaint.created_at) <= end)
    return query


def breakdown(column):
    return dict(Complaint.query.with_entities(column, func.count(Complaint.id)).group_by(column).all())


def average_rating():
    value = Feedback.query.with_entities(func.avg(Feedback.rating)).scalar()
    return round(value or 0, 2)


def staff_workload():
    return (
        User.query.filter_by(role="maintenance")
        .outerjoin(Complaint, Complaint.assignee_id == User.id)
        .with_entities(User.id, User.full_name, User.email, func.count(Complaint.id))
        .group_by(User.id)
        .all()
    )

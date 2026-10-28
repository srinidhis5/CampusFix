from app.extensions import db
from app.models import Notification


def notify(user, title, message, complaint=None):
    if not user:
        return
    db.session.add(
        Notification(
            user_id=user.id,
            title=title,
            message=message,
            related_complaint_id=complaint.id if complaint else None,
        )
    )


def notify_admins(title, message, complaint=None):
    from app.models import User

    for admin in User.query.filter_by(role="admin", is_active=True).all():
        notify(admin, title, message, complaint)

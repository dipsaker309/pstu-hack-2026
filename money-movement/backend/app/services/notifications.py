# pyright: reportMissingImports=false, reportMissingModuleSource=false
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType


def queue_notification(
    db: Session,
    user_id: int,
    notification_type: NotificationType,
    message: str,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        message=message,
    )
    db.add(notification)
    return notification

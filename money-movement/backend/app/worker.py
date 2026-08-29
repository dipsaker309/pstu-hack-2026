# pyright: reportMissingImports=false, reportMissingModuleSource=false
import os
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models.notification import Notification, NotificationStatus


BATCH_SIZE = int(os.getenv("NOTIFICATION_BATCH_SIZE", "50"))
INTERVAL_SECONDS = int(os.getenv("NOTIFICATION_WORKER_INTERVAL_SECONDS", "5"))


def process_pending_notifications() -> int:
    with SessionLocal() as db:
        notifications = list(
            db.scalars(
                select(Notification)
                .where(Notification.status == NotificationStatus.PENDING)
                .order_by(Notification.created_at)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True),
            ).all(),
        )

        for notification in notifications:
            print(
                f"Notification {notification.id}: user={notification.user_id} "
                f"type={notification.notification_type} message={notification.message}",
            )
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)

        db.commit()
        return len(notifications)


def main() -> None:
    print("Cresco notification worker started.")

    while True:
        processed = process_pending_notifications()

        if processed == 0:
            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

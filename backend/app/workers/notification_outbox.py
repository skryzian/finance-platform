import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import and_, or_

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.integrations import NotificationDelivery
from app.services.notifications import dispatch_delivery


def pending_delivery_ids(limit: int = 100) -> list[int]:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        rows = (
            db.query(NotificationDelivery.id)
            .filter(
                NotificationDelivery.attempts < settings.notification_max_attempts,
                or_(
                    NotificationDelivery.status == "PENDING",
                    and_(
                        NotificationDelivery.status == "FAILED",
                        or_(
                            NotificationDelivery.next_attempt_at.is_(None),
                            NotificationDelivery.next_attempt_at <= now,
                        ),
                    ),
                ),
            )
            .order_by(NotificationDelivery.created_at, NotificationDelivery.id)
            .limit(limit)
            .all()
        )
        return [row.id for row in rows]


async def drain_once() -> int:
    delivery_ids = pending_delivery_ids()
    for delivery_id in delivery_ids:
        await dispatch_delivery(delivery_id)
    return len(delivery_ids)


async def run_worker() -> None:
    while True:
        processed = await drain_once()
        await asyncio.sleep(5 if processed else 30)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch queued Finance Platform notifications.")
    parser.add_argument("--once", action="store_true", help="Process the current outbox batch and exit.")
    args = parser.parse_args()
    if args.once:
        print(f"Processed {asyncio.run(drain_once())} notification delivery records.")
    else:
        asyncio.run(run_worker())


if __name__ == "__main__":
    main()

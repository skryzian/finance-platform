from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.sync import SyncEvent, UserSyncState


def record_sync_event(
    db: Session,
    user_id: int,
    entity_type: str,
    entity_id: int | str,
    payload: dict[str, Any],
    operation: str = "UPSERT",
) -> int:
    state = db.query(UserSyncState).filter(
        UserSyncState.user_id == user_id
    ).with_for_update().one()
    state.version += 1
    db.add(SyncEvent(
        user_id=user_id,
        version=state.version,
        entity_type=entity_type,
        entity_id=str(entity_id),
        operation=operation,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()
    return state.version

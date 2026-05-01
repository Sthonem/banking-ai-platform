from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from banking_common.models import ProcessedEvent


def mark_event_processed(db: Session, event_id, consumer_name: str, event_type: str) -> bool:
    db.add(ProcessedEvent(event_id=event_id, consumer_name=consumer_name, event_type=event_type))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    return True

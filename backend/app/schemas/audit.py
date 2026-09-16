from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    actor_id: int | None
    timestamp: datetime
    entity_type: str
    entity_id: int
    action: str
    before: dict | None
    after: dict | None
    correlation_id: str | None

    model_config = {"from_attributes": True}

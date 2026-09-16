"""Document completeness, duplicate-detection, and renewal/expiry logic.

Pure functions only — no DB access — so they're directly unit testable.
"""

import hashlib
from datetime import date
from enum import Enum

REMINDER_THRESHOLDS_DAYS = (7, 30, 60, 90)


class RenewalUrgency(str, Enum):
    OK = "ok"
    DUE_90 = "due_90"
    DUE_60 = "due_60"
    DUE_30 = "due_30"
    DUE_7 = "due_7"
    EXPIRED = "expired"
    NOT_APPLICABLE = "not_applicable"


def days_to_expiry(expiry_date: date | None, as_of: date) -> int | None:
    if expiry_date is None:
        return None
    return (expiry_date - as_of).days


def renewal_urgency(expiry_date: date | None, as_of: date) -> RenewalUrgency:
    remaining = days_to_expiry(expiry_date, as_of)
    if remaining is None:
        return RenewalUrgency.NOT_APPLICABLE
    if remaining < 0:
        return RenewalUrgency.EXPIRED
    for threshold in REMINDER_THRESHOLDS_DAYS:
        if remaining <= threshold:
            return RenewalUrgency(f"due_{threshold}")
    return RenewalUrgency.OK


def compute_completeness(required_fields: list[str], provided: dict) -> tuple[int, list[str]]:
    """Returns (completeness_score 0-100, missing_field_names)."""
    if not required_fields:
        return 100, []
    missing = [f for f in required_fields if not provided.get(f)]
    score = round((len(required_fields) - len(missing)) / len(required_fields) * 100)
    return score, missing


def compute_checksum(*, entity_id: int, document_type_key: str, issue_date: date | None) -> str:
    """Deterministic content fingerprint used for duplicate detection.

    Two documents of the same type, for the same entity, issued the same day
    are treated as duplicates — a simplified stand-in for real file hashing
    since only metadata (no real files) is stored in this demo.
    """
    raw = f"{entity_id}:{document_type_key}:{issue_date.isoformat() if issue_date else 'none'}"
    return hashlib.sha256(raw.encode()).hexdigest()

from datetime import date, timedelta

from app.services import renewal


def test_days_to_expiry_none_when_no_expiry():
    assert renewal.days_to_expiry(None, date(2026, 1, 1)) is None


def test_days_to_expiry_computes_delta():
    assert renewal.days_to_expiry(date(2026, 1, 10), date(2026, 1, 1)) == 9


def test_renewal_urgency_not_applicable_without_expiry():
    assert renewal.renewal_urgency(None, date(2026, 1, 1)) == renewal.RenewalUrgency.NOT_APPLICABLE


def test_renewal_urgency_expired():
    today = date(2026, 1, 10)
    assert renewal.renewal_urgency(date(2026, 1, 1), today) == renewal.RenewalUrgency.EXPIRED


def test_renewal_urgency_buckets():
    today = date(2026, 1, 1)
    assert renewal.renewal_urgency(today + timedelta(days=5), today) == renewal.RenewalUrgency.DUE_7
    assert (
        renewal.renewal_urgency(today + timedelta(days=20), today) == renewal.RenewalUrgency.DUE_30
    )
    assert (
        renewal.renewal_urgency(today + timedelta(days=45), today) == renewal.RenewalUrgency.DUE_60
    )
    assert (
        renewal.renewal_urgency(today + timedelta(days=75), today) == renewal.RenewalUrgency.DUE_90
    )
    assert renewal.renewal_urgency(today + timedelta(days=200), today) == renewal.RenewalUrgency.OK


def test_renewal_urgency_boundary_is_inclusive():
    today = date(2026, 1, 1)
    assert renewal.renewal_urgency(today + timedelta(days=7), today) == renewal.RenewalUrgency.DUE_7
    assert renewal.renewal_urgency(today, today) == renewal.RenewalUrgency.DUE_7


def test_compute_completeness_no_required_fields_is_always_complete():
    score, missing = renewal.compute_completeness([], {})
    assert score == 100
    assert missing == []


def test_compute_completeness_all_present():
    score, missing = renewal.compute_completeness(["a", "b"], {"a": True, "b": "yes"})
    assert score == 100
    assert missing == []


def test_compute_completeness_partial():
    score, missing = renewal.compute_completeness(["a", "b", "c", "d"], {"a": True, "b": True})
    assert score == 50
    assert set(missing) == {"c", "d"}


def test_compute_completeness_falsy_values_count_as_missing():
    score, missing = renewal.compute_completeness(["a"], {"a": ""})
    assert score == 0
    assert missing == ["a"]


def test_compute_checksum_deterministic():
    c1 = renewal.compute_checksum(entity_id=1, document_type_key="w9", issue_date=date(2026, 1, 1))
    c2 = renewal.compute_checksum(entity_id=1, document_type_key="w9", issue_date=date(2026, 1, 1))
    assert c1 == c2


def test_compute_checksum_differs_by_entity():
    c1 = renewal.compute_checksum(entity_id=1, document_type_key="w9", issue_date=date(2026, 1, 1))
    c2 = renewal.compute_checksum(entity_id=2, document_type_key="w9", issue_date=date(2026, 1, 1))
    assert c1 != c2


def test_compute_checksum_differs_by_type_and_date():
    base = renewal.compute_checksum(
        entity_id=1, document_type_key="w9", issue_date=date(2026, 1, 1)
    )
    other_type = renewal.compute_checksum(
        entity_id=1, document_type_key="w8ben", issue_date=date(2026, 1, 1)
    )
    other_date = renewal.compute_checksum(
        entity_id=1, document_type_key="w9", issue_date=date(2026, 1, 2)
    )
    assert base != other_type
    assert base != other_date

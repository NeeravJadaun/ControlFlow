from datetime import date, timedelta

from app.models.enums import ClassificationStatus, RegimeType
from app.services import classification


def test_classify_fatca_us_person():
    assert classification.classify_fatca({"us_person": True}) == "U.S. Person"


def test_classify_fatca_financial_institution():
    assert (
        classification.classify_fatca({"us_person": False, "entity_type": "financial_institution"})
        == "Participating FFI"
    )


def test_classify_fatca_active_business():
    assert (
        classification.classify_fatca({"us_person": False, "entity_type": "active_business"})
        == "Active NFFE"
    )


def test_classify_fatca_default_individual_is_passive_nffe():
    assert (
        classification.classify_fatca({"us_person": False, "entity_type": "individual"})
        == "Passive NFFE"
    )


def test_classify_crs_us_residency_not_reportable():
    result = classification.classify_crs(
        {"tax_residency_country": "US", "entity_type": "individual"}
    )
    assert result == "Not CRS Reportable (US-only)"


def test_classify_crs_non_us_individual_is_reportable():
    result = classification.classify_crs(
        {"tax_residency_country": "GB", "entity_type": "individual"}
    )
    assert result == "Reportable Person"


def test_classify_crs_financial_institution_is_non_reporting():
    result = classification.classify_crs(
        {"tax_residency_country": "GB", "entity_type": "financial_institution"}
    )
    assert result == "Non-Reporting Financial Institution"


def test_classify_qi_requires_agreement_on_file():
    with_agreement = classification.classify_qi(
        {"entity_type": "financial_institution", "qi_agreement_on_file": True}
    )
    without_agreement = classification.classify_qi(
        {"entity_type": "financial_institution", "qi_agreement_on_file": False}
    )
    assert with_agreement == "Qualified Intermediary"
    assert without_agreement == "Non-Qualified Intermediary"


def test_classify_qi_not_applicable_for_non_fi():
    assert classification.classify_qi({"entity_type": "individual"}) == "Not Applicable"


def test_classify_dispatches_by_regime():
    attrs = {"us_person": True}
    assert classification.classify(RegimeType.FATCA, attrs) == classification.classify_fatca(attrs)


def test_documentation_status_pending_without_docs():
    status = classification.documentation_status("Active NFFE", False, None, date(2026, 1, 1))
    assert status == ClassificationStatus.PENDING_DOCUMENTATION


def test_documentation_status_documented_with_no_review_date():
    status = classification.documentation_status("Active NFFE", True, None, date(2026, 1, 1))
    assert status == ClassificationStatus.DOCUMENTED


def test_documentation_status_expired_when_review_date_passed():
    today = date(2026, 6, 1)
    status = classification.documentation_status(
        "Active NFFE", True, today - timedelta(days=1), today
    )
    assert status == ClassificationStatus.EXPIRED


def test_documentation_status_review_due_within_window():
    today = date(2026, 6, 1)
    status = classification.documentation_status(
        "Active NFFE", True, today + timedelta(days=30), today
    )
    assert status == ClassificationStatus.REVIEW_DUE


def test_documentation_status_documented_when_review_far_away():
    today = date(2026, 6, 1)
    status = classification.documentation_status(
        "Active NFFE", True, today + timedelta(days=200), today
    )
    assert status == ClassificationStatus.DOCUMENTED

"""Simplified FATCA / CRS / QI classification rules for the financial-ops demo.

IMPORTANT: These rules are deliberately simplified for demonstration purposes.
They are NOT legal, tax, or regulatory advice and must never be used to make
real classification decisions. See docs/security-and-limitations.md.
"""

from datetime import date

from app.models.enums import ClassificationStatus, RegimeType

REVIEW_WINDOW_DAYS = 60


def classify_fatca(attributes: dict) -> str:
    """Very simplified FATCA bucket based on synthetic entity attributes."""
    if attributes.get("us_person"):
        return "U.S. Person"
    entity_type = attributes.get("entity_type", "individual")
    if entity_type == "financial_institution":
        return "Participating FFI"
    if entity_type in ("active_business", "dealer"):
        return "Active NFFE"
    return "Passive NFFE"


def classify_crs(attributes: dict) -> str:
    country = attributes.get("tax_residency_country", "US")
    entity_type = attributes.get("entity_type", "individual")
    if entity_type == "financial_institution":
        return "Non-Reporting Financial Institution"
    if country in ("US",):
        return "Not CRS Reportable (US-only)"
    if entity_type in ("active_business", "dealer"):
        return "Active Non-Financial Entity"
    return "Reportable Person"


def classify_qi(attributes: dict) -> str:
    if attributes.get("entity_type") == "financial_institution" and attributes.get(
        "qi_agreement_on_file"
    ):
        return "Qualified Intermediary"
    if attributes.get("entity_type") == "financial_institution":
        return "Non-Qualified Intermediary"
    return "Not Applicable"


CLASSIFIERS = {
    RegimeType.FATCA: classify_fatca,
    RegimeType.CRS: classify_crs,
    RegimeType.QI: classify_qi,
}


def classify(regime: RegimeType, attributes: dict) -> str:
    return CLASSIFIERS[regime](attributes)


def documentation_status(
    classification_value: str, has_documentation: bool, review_due_date: date | None, as_of: date
) -> ClassificationStatus:
    """Roll documentation completeness + review date into an overall status."""
    if not has_documentation:
        return ClassificationStatus.PENDING_DOCUMENTATION
    if review_due_date is not None:
        if review_due_date < as_of:
            return ClassificationStatus.EXPIRED
        if (review_due_date - as_of).days <= REVIEW_WINDOW_DAYS:
            return ClassificationStatus.REVIEW_DUE
    return ClassificationStatus.DOCUMENTED

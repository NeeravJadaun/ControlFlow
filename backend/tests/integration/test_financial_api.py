from datetime import date, timedelta


def make_classification(db, sample_entity, status, regime="FATCA"):
    from app.models.enums import RegimeType
    from app.models.financial import Classification

    cl = Classification(
        entity_id=sample_entity.id,
        regime=RegimeType(regime),
        status=status,
        classification_value="U.S. Person",
        review_due_date=date.today() + timedelta(days=10),
    )
    db.add(cl)
    db.flush()
    return cl


def test_list_classifications_filtered_by_regime(client, analyst_headers, db, sample_entity):
    from app.models.enums import ClassificationStatus

    make_classification(db, sample_entity, ClassificationStatus.DOCUMENTED, regime="FATCA")
    make_classification(db, sample_entity, ClassificationStatus.REVIEW_DUE, regime="CRS")

    resp = client.get(
        "/api/financial/classifications", headers=analyst_headers, params={"regime": "CRS"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["regime"] == "CRS"


def test_list_classifications_filtered_by_status(client, analyst_headers, db, sample_entity):
    from app.models.enums import ClassificationStatus

    make_classification(db, sample_entity, ClassificationStatus.REVIEW_DUE)
    resp = client.get(
        "/api/financial/classifications", headers=analyst_headers, params={"status": "review_due"}
    )
    assert resp.json()["total"] == 1


def test_distribution_mark_sent_and_acknowledge(client, analyst_headers, db, sample_entity):
    from app.models.enums import DistributionKind, DistributionStatus
    from app.models.financial import Distribution

    dist = Distribution(
        kind=DistributionKind.FUND_FACT_SHEET,
        entity_id=sample_entity.id,
        reference_name="Global Balanced Fund",
        effective_date=date.today(),
        status=DistributionStatus.PENDING,
    )
    db.add(dist)
    db.flush()

    sent = client.post(f"/api/financial/distributions/{dist.id}/mark-sent", headers=analyst_headers)
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["sent_at"] is not None

    ack = client.post(
        f"/api/financial/distributions/{dist.id}/acknowledge", headers=analyst_headers
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"


def test_cannot_acknowledge_distribution_that_was_never_sent(
    client, analyst_headers, db, sample_entity
):
    from app.models.enums import DistributionKind, DistributionStatus
    from app.models.financial import Distribution

    dist = Distribution(
        kind=DistributionKind.MATURITY_NOTICE,
        entity_id=sample_entity.id,
        reference_name="Note maturing",
        effective_date=date.today(),
        status=DistributionStatus.PENDING,
    )
    db.add(dist)
    db.flush()

    resp = client.post(
        f"/api/financial/distributions/{dist.id}/acknowledge", headers=analyst_headers
    )
    assert resp.status_code == 400

from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_date_range_defaults_to_30_days():
    start, end = main.date_range(None, None)
    assert end == date.today()
    assert (end - start).days == 29


def test_date_range_rejects_reversed_range():
    with pytest.raises(HTTPException) as error:
        main.date_range(date(2026, 2, 2), date(2026, 2, 1))
    assert error.value.status_code == 422


def test_filter_values_are_parameters_not_sql():
    where, params = main.filters(4, 9, date(2026, 1, 1), date(2026, 1, 7))
    assert "p.id = %s" in where and "v.machine_id = %s" in where
    assert params == (date(2026, 1, 1), date(2026, 1, 7), 4, 9)


def test_alert_filter_validation():
    with pytest.raises(HTTPException) as error:
        main.alerts(status="pending", severity=None, plant_id=None)
    assert error.value.status_code == 422


def test_machine_detail_returns_404_for_unknown_machine(monkeypatch):
    monkeypatch.setattr(main, "query", lambda *_: [])
    with pytest.raises(HTTPException) as error:
        main.machine_detail(9999, None, None)
    assert error.value.status_code == 404


def test_summary_endpoint_serializes_database_metrics(monkeypatch):
    from decimal import Decimal

    monkeypatch.setattr(main, "query", lambda *_: [{
        "produced": 100, "defects": 2, "target": 120, "downtime": 40,
        "planned": 480, "cost": Decimal("2500.50"), "machines": 1, "days": 1,
        "availability_pct": Decimal("91.67"), "defect_rate_pct": Decimal("2.00"),
        "target_achievement_pct": Decimal("83.33"),
    }])
    response = client.get("/api/v1/summary?date_from=2026-01-01&date_to=2026-01-01")
    assert response.status_code == 200
    assert response.json()["kpis"]["cost"] == 2500.5
    assert response.json()["period"] == {"from": "2026-01-01", "to": "2026-01-01"}

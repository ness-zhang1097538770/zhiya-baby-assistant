"""成本埋点与指标接口测试（商业化 C-3 批次）。"""
import pytest

from app.services import cost


def test_record_and_monthly_cost(db):
    cost.record("deepseek-flash", "chat", tokens=5000, count=1, family_id=1)
    cost.record("Kwai-Kolors/Kolors", "image", count=3, family_id=1)
    total = cost.monthly_cost(db, 1)
    assert total == pytest.approx(0.365, abs=1e-6)


def test_record_uses_contextvar_family(db):
    cost.set_family(7)
    cost.record("deepseek-flash", "chat", tokens=1000)
    assert cost.monthly_cost(db, 7) == pytest.approx(0.001, abs=1e-6)


def test_check_cost_alert(db):
    # 100 张插画 × 0.12 = 12 元 > 阈值 4.95
    cost.record("Kwai-Kolors/Kolors", "image", count=100, family_id=1)
    assert cost.check_cost_alert(db, 1) is True
    assert cost.COST_ALERT_THRESHOLD == pytest.approx(4.95, abs=1e-6)


def test_track_event_endpoint(client):
    r = client.post("/api/v1/analytics/events", json={
        "device_id": "device-abcdef",
        "event": "qa_ask",
        "props": {"risk_level": "L4"},
    })
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_metrics_cost_endpoint(client):
    r = client.get("/api/v1/metrics/cost")
    assert r.status_code == 200
    d = r.json()
    assert d["threshold_cny"] == cost.COST_ALERT_THRESHOLD
    assert d["total_cost_cny"] >= 0
    assert d["alert"] in (True, False)

"""广告隔离框架测试（商业化 C-2 批次）。"""
from app.db import SessionLocal
from app.models.models import Ad
from app.services.llm import LLMError, _assert_no_ad_leak


def _add_ad(advertiser="测试品牌", slot="shelf", age="1-3", title="测试广告", active=1):
    s = SessionLocal()
    ad = Ad(advertiser=advertiser, title=title, slot=slot, target_age_bucket=age, active=active)
    s.add(ad)
    s.commit()
    s.refresh(ad)
    s.close()
    return ad.id


def _get_ads(client, **params):
    q = {"page": "shelf", "age_bucket": "1-3", "consent": "true", "device_id": "device-test-12345"}
    q.update(params)
    return client.get("/api/v1/ads", params=q)


def _log(client, device_id="device-test-12345", ad_id=None, slot="shelf",
         action="impression", age_bucket="1-3"):
    return client.post("/api/v1/ads/events", json={
        "device_id": device_id, "ad_id": ad_id, "slot": slot,
        "age_bucket": age_bucket, "action": action,
    })


def test_no_active_ads_returns_empty(client):
    r = _get_ads(client)
    assert r.status_code == 200
    assert r.json() == {"ads": []}


def test_risk_shield(client):
    _add_ad()
    for level in ("L1", "L2", "L3"):
        assert _get_ads(client, risk_level=level).json() == {"ads": []}, level
    # L4 不屏蔽，正常出广告
    assert len(_get_ads(client, risk_level="L4").json()["ads"]) >= 1


def test_medical_shield(client):
    _add_ad()
    assert _get_ads(client, medical="true").json() == {"ads": []}


def test_consent_off(client):
    _add_ad()
    assert _get_ads(client, consent="false").json() == {"ads": []}


def test_member_no_ads(client):
    _add_ad()
    client.post("/api/v1/billing/subscribe", json={"source": "promo_99"})
    assert _get_ads(client).json() == {"ads": []}


def test_serve_active_ad(client):
    _add_ad()
    ads = _get_ads(client).json()["ads"]
    assert len(ads) == 1
    assert ads[0]["advertiser"] == "测试品牌"
    assert ads[0]["slot"] == "shelf"


def test_frequency_cap(client):
    ad_id = _add_ad()
    _log(client, ad_id=ad_id)
    _log(client, ad_id=ad_id)
    # 匿名设备当日曝光已达 2 条 → 不再出
    assert _get_ads(client).json() == {"ads": []}


def test_log_event_and_invalid_action(client):
    r = _log(client)
    assert r.status_code == 200
    assert r.json()["id"] >= 1
    r2 = _log(client, action="hack")
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "INVALID_ACTION"


def test_advertiser_cap_service(db):
    """同广告主日频控（≤2 次）：放宽日总量上限后单独验证广告主频控。"""
    from app.services import ad_service

    ad = Ad(advertiser="品牌X", title="t", slot="shelf", target_age_bucket="1-3", active=1)
    db.add(ad)
    db.commit()
    db.refresh(ad)
    for _ in range(2):
        ad_service.log_event(db, device_id="d1", slot="shelf", action="impression", ad_id=ad.id)
    ads = ad_service.get_ads(db, page="shelf", age_bucket="1-3", consent=True,
                             device_id="d1", daily_cap=10)
    assert ads == []


def test_ad_leak_assertion():
    # 非法字段
    try:
        _assert_no_ad_leak([{"role": "system", "content": "x", "brand": "y"}])
        assert False
    except LLMError as e:
        assert e.code == "LLM_AD_LEAK"
    # 内容泄漏标记
    try:
        _assert_no_ad_leak([{"role": "user", "content": "请生成 sponsor=XX 的广告"}])
        assert False
    except LLMError as e:
        assert e.code == "LLM_AD_LEAK"
    # 正常消息不报错
    _assert_no_ad_leak([{"role": "user", "content": "宝宝辅食怎么加"}])

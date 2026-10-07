"""会员订阅与绘本额度测试（商业化 C-1 批次）。"""
from app.db import SessionLocal
from app.models.models import RedeemCode
from app.services import billing


def _entitlements(client):
    return client.get("/api/v1/billing/entitlements").json()


def _fake_char(messages, max_retries=2):
    return (
        {
            "hero": {"name": "小糯米", "look": "圆脸", "personality": "勇敢"},
            "companions": [],
            "art_style": "温暖水彩童趣风",
        },
        None,
    )


def _make_child(client):
    return client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2026-01-16"}).json()["id"]


def _make_story(client, monkeypatch, child_id):
    monkeypatch.setattr("app.services.llm.chat_json", _fake_char)
    return client.post(
        f"/api/v1/children/{child_id}/stories",
        json={"character_name": "小糯米", "theme": "刷牙", "age_range": "1-2岁"},
    )


def test_free_entitlements(client):
    e = _entitlements(client)
    assert e["plan"] == "free"
    assert e["story_books_available"] == 4  # 3 赠本 + 1 月额度
    assert e["entitlements"]["story_monthly_grant"] == 1
    assert e["entitlements"]["ads"] is True


def test_story_consumes_quota(client, monkeypatch):
    child_id = _make_child(client)
    assert _entitlements(client)["story_books_available"] == 4
    r = _make_story(client, monkeypatch, child_id)
    assert r.status_code == 201
    assert _entitlements(client)["story_books_available"] == 3


def test_story_quota_exhausted(client, monkeypatch):
    child_id = _make_child(client)
    for _ in range(4):
        assert _make_story(client, monkeypatch, child_id).status_code == 201
    r = _make_story(client, monkeypatch, child_id)
    assert r.status_code == 402
    assert r.json()["error"]["code"] == "STORY_QUOTA_EXCEEDED"


def test_subscribe_opens_yearly(client):
    r = client.post("/api/v1/billing/subscribe", json={"source": "promo_99"})
    assert r.status_code == 200
    assert r.json()["plan"] == "yearly"
    e = _entitlements(client)
    assert e["plan"] == "yearly"
    assert e["story_books_available"] == 30


def test_upgrade_tops_up_monthly_grant(client):
    """免费时已发当月额度（1 本），升级后补足到 30 本（只增不减）。"""
    assert _entitlements(client)["story_books_available"] == 4  # 先作为免费用户发放
    client.post("/api/v1/billing/subscribe", json={"source": "promo_99"})
    e = _entitlements(client)
    assert e["plan"] == "yearly"
    assert e["story_books_available"] == 3 + 30  # 3 赠本 + 补足后的 30 月额度


def test_redeem_opens_and_used_once(client):
    s = SessionLocal()
    s.add(RedeemCode(code="TESTCODE99", source="promo_99"))
    s.commit()
    s.close()
    r = client.post("/api/v1/billing/redeem", json={"code": "testcode99"})
    assert r.status_code == 200
    assert r.json()["plan"] == "yearly"
    # 二次使用失败
    r2 = client.post("/api/v1/billing/redeem", json={"code": "testcode99"})
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "CODE_USED"


def test_redeem_invalid_code(client):
    r = client.post("/api/v1/billing/redeem", json={"code": "NOPE"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CODE"


def test_purchase_addon_pack(client):
    r = client.post("/api/v1/billing/purchase", json={"sku": "pack_5"})
    assert r.status_code == 200
    assert r.json()["kind"] == "addon_pack"
    assert r.json()["total"] == 5
    e = _entitlements(client)
    assert e["story_books_available"] == 4 + 5  # 免费额度 + 加购


def test_purchase_report_not_ready(client):
    r = client.post("/api/v1/billing/purchase", json={"sku": "report_1"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "SKU_NOT_READY"


def test_cancel_renew(client):
    client.post("/api/v1/billing/subscribe", json={"source": "monthly_28"})
    r = client.post("/api/v1/billing/cancel-renew")
    assert r.status_code == 200
    assert r.json()["auto_renew"] is False


def test_generate_redeem_codes(db):
    codes = billing.generate_redeem_codes(db, 3, "promo_99")
    assert len(codes) == 3
    assert len(set(codes)) == 3

"""邀请码登录 + 家庭数据隔离测试。"""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.models import Family, InviteCode, Session


def test_login_valid_code(client):
    db = SessionLocal()
    code = db.query(InviteCode).first().code
    db.close()
    r = client.post("/api/v1/auth/login", json={"invite_code": code})
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_invalid_code(client):
    r = client.post("/api/v1/auth/login", json={"invite_code": "BADCODE"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CODE"


def test_unauthenticated_rejected():
    with TestClient(app) as c:
        r = c.get("/api/v1/children")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_family_isolation(client):
    # 家庭 A（client 内置 token）建一个孩子
    r = client.post("/api/v1/children", json={"nickname": "A娃", "birth_date": "2025-01-01"})
    assert r.status_code == 201
    child_a = r.json()["id"]

    # 家庭 B + token + 孩子
    db = SessionLocal()
    fam_b = Family(name="B家")
    db.add(fam_b)
    db.commit()
    db.refresh(fam_b)
    token_b = "token-b"
    db.add(Session(token=token_b, family_id=fam_b.id))
    db.commit()
    db.close()

    client_b = TestClient(app, headers={"Authorization": f"Bearer {token_b}"})
    r = client_b.post("/api/v1/children", json={"nickname": "B娃", "birth_date": "2025-02-02"})
    assert r.status_code == 201
    child_b = r.json()["id"]

    # 各自列表只能看到自己家庭的孩子
    a_ids = [c["id"] for c in client.get("/api/v1/children").json()["items"]]
    b_ids = [c["id"] for c in client_b.get("/api/v1/children").json()["items"]]
    assert child_a in a_ids and child_b not in a_ids
    assert child_b in b_ids and child_a not in b_ids

    # 跨家庭访问他人孩子 → 404
    assert client.get(f"/api/v1/children/{child_b}/events").status_code == 404
    assert client_b.get(f"/api/v1/children/{child_a}/events").status_code == 404
    client_b.close()

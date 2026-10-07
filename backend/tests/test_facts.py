"""记忆/事实管理接口：查看、编辑、删除（对应 Q1「可改可删」）。"""
import pytest


def _make_child(client):
    return client.post(
        "/api/v1/children", json={"nickname": "小糯米", "birth_date": "2026-01-16"}
    ).json()["id"]


def _save_fact(client, monkeypatch, child_id, category, key, value):
    monkeypatch.setattr(
        "app.services.llm.chat_json",
        lambda messages: (
            {
                "intent": "action",
                "reply": "",
                "params": {},
                "actions": [
                    {"tool": "save_fact", "params": {"category": category, "key": key, "value": value}}
                ],
            },
            None,
        ),
    )
    r = client.post("/api/v1/agent/run", json={"child_id": child_id, "text": f"{key} {value}"})
    assert r.status_code == 200
    assert r.json()["executed"][0]["tool"] == "save_fact"


def _first_fact_id(client, child_id):
    items = client.get(f"/api/v1/children/{child_id}/facts").json()["items"]
    return items[0]["id"]


def test_list_facts_empty(client):
    child_id = _make_child(client)
    r = client.get(f"/api/v1/children/{child_id}/facts")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_facts_after_agent_save(client, monkeypatch):
    child_id = _make_child(client)
    _save_fact(client, monkeypatch, child_id, "allergy", "鸡蛋", "过敏")
    r = client.get(f"/api/v1/children/{child_id}/facts")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["category"] == "allergy"
    assert items[0]["category_label"] == "过敏"
    assert items[0]["key"] == "鸡蛋"
    assert items[0]["value"] == "过敏"
    assert items[0]["source"] == "ai_extract"


def test_update_fact(client, monkeypatch):
    child_id = _make_child(client)
    _save_fact(client, monkeypatch, child_id, "allergy", "鸡蛋", "过敏")
    fid = _first_fact_id(client, child_id)
    r = client.put(f"/api/v1/facts/{fid}", json={"value": "严重过敏"})
    assert r.status_code == 200
    assert r.json()["value"] == "严重过敏"
    assert client.get(f"/api/v1/children/{child_id}/facts").json()["items"][0]["value"] == "严重过敏"


def test_update_fact_invalid_category(client, monkeypatch):
    child_id = _make_child(client)
    _save_fact(client, monkeypatch, child_id, "allergy", "鸡蛋", "过敏")
    fid = _first_fact_id(client, child_id)
    r = client.put(f"/api/v1/facts/{fid}", json={"category": "心情"})
    assert r.status_code == 422


def test_update_fact_blank_value_rejected(client, monkeypatch):
    child_id = _make_child(client)
    _save_fact(client, monkeypatch, child_id, "allergy", "鸡蛋", "过敏")
    fid = _first_fact_id(client, child_id)
    assert client.put(f"/api/v1/facts/{fid}", json={"value": "   "}).status_code == 422


def test_delete_fact_soft(client, monkeypatch):
    child_id = _make_child(client)
    _save_fact(client, monkeypatch, child_id, "allergy", "鸡蛋", "过敏")
    fid = _first_fact_id(client, child_id)
    assert client.delete(f"/api/v1/facts/{fid}").status_code == 204
    assert client.get(f"/api/v1/children/{child_id}/facts").json()["items"] == []


def test_foreign_child_and_fact_not_found(client):
    assert client.get("/api/v1/children/99999/facts").status_code == 404
    assert client.put("/api/v1/facts/99999", json={"value": "x"}).status_code == 404
    assert client.delete("/api/v1/facts/99999").status_code == 404

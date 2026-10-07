def _make_child(client):
    r = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2026-01-16"})
    return r.json()["id"]


def test_create_and_list_reminder(client):
    child_id = _make_child(client)
    r = client.post(
        f"/api/v1/children/{child_id}/reminders",
        json={"type": "vaccine", "title": "打疫苗", "remind_at": "2026-09-20T10:00:00"},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "vaccine"
    assert r.json()["enabled"] is True

    r2 = client.get(f"/api/v1/children/{child_id}/reminders")
    assert len(r2.json()["items"]) == 1


def test_update_enabled_and_delete(client):
    child_id = _make_child(client)
    rid = client.post(
        f"/api/v1/children/{child_id}/reminders",
        json={"type": "routine", "title": "午睡", "remind_at": "2026-09-20T12:00:00"},
    ).json()["id"]
    r = client.put(f"/api/v1/reminders/{rid}", json={"enabled": False})
    assert r.json()["enabled"] is False

    d = client.delete(f"/api/v1/reminders/{rid}")
    assert d.status_code == 204
    assert len(client.get(f"/api/v1/children/{child_id}/reminders").json()["items"]) == 0


def test_upcoming_filter(client):
    child_id = _make_child(client)
    client.post(
        f"/api/v1/children/{child_id}/reminders",
        json={"type": "vaccine", "title": "三天后", "remind_at": "2026-09-19T10:00:00"},
    )
    client.post(
        f"/api/v1/children/{child_id}/reminders",
        json={"type": "routine", "title": "三十天后", "remind_at": "2026-10-20T10:00:00"},
    )
    # 用相对未来时间构造，避免依赖固定日期
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    client.post(
        f"/api/v1/children/{child_id}/reminders",
        json={"type": "custom", "title": "明天", "remind_at": (now + timedelta(days=1)).isoformat()},
    )
    r = client.get(f"/api/v1/children/{child_id}/reminders/upcoming?days=7")
    titles = [x["title"] for x in r.json()["items"]]
    assert "明天" in titles


def test_invalid_type(client):
    child_id = _make_child(client)
    r = client.post(f"/api/v1/children/{child_id}/reminders", json={"type": "bad", "title": "x", "remind_at": "2026-09-20T10:00:00"})
    assert r.status_code == 422

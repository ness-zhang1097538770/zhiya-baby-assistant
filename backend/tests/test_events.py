def _make_child(client):
    r = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2026-01-16"})
    return r.json()["id"]


def test_create_and_list_event(client):
    child_id = _make_child(client)
    r = client.post(
        f"/api/v1/children/{child_id}/events",
        json={"type": "feeding", "title": "母乳", "occurred_at": "2026-09-16T08:00:00", "data": {"amount": "120ml"}},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "feeding"
    assert r.json()["data"] == {"amount": "120ml"}

    r2 = client.get(f"/api/v1/children/{child_id}/events")
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1


def test_list_filter_by_type(client):
    child_id = _make_child(client)
    client.post(f"/api/v1/children/{child_id}/events", json={"type": "feeding", "occurred_at": "2026-09-16T08:00:00"})
    client.post(f"/api/v1/children/{child_id}/events", json={"type": "sleep", "occurred_at": "2026-09-16T09:00:00"})
    r = client.get(f"/api/v1/children/{child_id}/events?type=sleep")
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["type"] == "sleep"


def test_update_and_delete_event(client):
    child_id = _make_child(client)
    eid = client.post(f"/api/v1/children/{child_id}/events", json={"type": "feeding", "occurred_at": "2026-09-16T08:00:00"}).json()["id"]
    r = client.put(f"/api/v1/events/{eid}", json={"note": "吃得很香"})
    assert r.json()["note"] == "吃得很香"

    d = client.delete(f"/api/v1/events/{eid}")
    assert d.status_code == 204
    assert len(client.get(f"/api/v1/children/{child_id}/events").json()["items"]) == 0


def test_timeline_grouping(client):
    child_id = _make_child(client)
    client.post(f"/api/v1/children/{child_id}/events", json={"type": "feeding", "occurred_at": "2026-09-16T08:00:00"})
    client.post(f"/api/v1/children/{child_id}/events", json={"type": "sleep", "occurred_at": "2026-09-16T21:00:00"})
    client.post(f"/api/v1/children/{child_id}/events", json={"type": "feeding", "occurred_at": "2026-09-15T08:00:00"})
    r = client.get(f"/api/v1/children/{child_id}/timeline")
    groups = r.json()["groups"]
    assert len(groups) == 2
    assert groups[0]["date"] == "2026-09-16"
    assert len(groups[0]["items"]) == 2


def test_invalid_type_and_child(client):
    child_id = _make_child(client)
    r = client.post(f"/api/v1/children/{child_id}/events", json={"type": "bad", "occurred_at": "2026-09-16T08:00:00"})
    assert r.status_code == 422
    r2 = client.post("/api/v1/children/9999/events", json={"type": "feeding", "occurred_at": "2026-09-16T08:00:00"})
    assert r2.status_code == 404

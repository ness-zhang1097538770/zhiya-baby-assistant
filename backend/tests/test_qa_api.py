import pytest

from app.services.llm import LLMError
from tests.conftest import parse_sse


def _make_child(client):
    r = client.post(
        "/api/v1/children",
        json={"nickname": "小糯米", "birth_date": "2025-01-15", "feeding_method": "已添加辅食"},
    )
    return r.json()["id"]


def test_qa_l1_no_llm(monkeypatch, client):
    child_id = _make_child(client)

    def _must_not_call(*a, **k):
        raise AssertionError("L1 不应调用模型")

    monkeypatch.setattr("app.services.llm.chat_json", _must_not_call)
    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "宝宝突然抽搐怎么办"}
    ) as resp:
        assert resp.status_code == 200
        events = parse_sse(resp)

    done = [e for e in events if e[0] == "done"]
    assert len(done) == 1
    data = done[0][1]
    assert data["risk_level"] == "L1"
    assert "120" in data["answer"]
    assert data["sources"] == []


def test_qa_l4_stream(monkeypatch, client):
    child_id = _make_child(client)

    def fake_chat_json(messages, max_retries=2):
        return (
            {
                "risk_level": "L4",
                "conclusion": "可以从强化铁米粉开始逐步添加辅食",
                "actions": ["由少到多、由稀到稠", "一次只加一种新食物"],
                "evidence": ["来自《辅食添加原则》"],
                "red_flags": ["出现皮疹或腹泻时暂停并观察"],
                "disclaimer": "本建议不能替代医生，请按需咨询。",
                "followup_question": None,
                "source_ids": [1],
            },
            None,
        )

    monkeypatch.setattr("app.services.llm.chat_json", fake_chat_json)
    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "8 个月辅食加什么"}
    ) as resp:
        events = parse_sse(resp)

    chunks = [e for e in events if e[0] == "chunk"]
    done = [e for e in events if e[0] == "done"]
    assert len(chunks) > 0
    assert len(done) == 1
    data = done[0][1]
    assert data["risk_level"] == "L4"
    assert data["conclusion"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["id"] == 1


def test_qa_followup(monkeypatch, client):
    child_id = _make_child(client)

    def fake_chat_json(messages, max_retries=2):
        return (
            {
                "risk_level": "NEED_MORE_INFO",
                "conclusion": "",
                "actions": [],
                "evidence": [],
                "red_flags": [],
                "disclaimer": "",
                "followup_question": "宝宝现在多大月龄？",
                "source_ids": [],
            },
            None,
        )

    monkeypatch.setattr("app.services.llm.chat_json", fake_chat_json)
    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "宝宝发烧了怎么办"}
    ) as resp:
        events = parse_sse(resp)

    done = [e for e in events if e[0] == "done"][0][1]
    assert done["risk_level"] == "NEED_MORE_INFO"
    assert done["followup_question"]


def test_qa_llm_error(monkeypatch, client):
    child_id = _make_child(client)

    def fake_chat_json(messages, max_retries=2):
        raise LLMError("LLM_NO_KEY", "缺少 DeepSeek API Key")

    monkeypatch.setattr("app.services.llm.chat_json", fake_chat_json)
    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "8 个月辅食加什么"}
    ) as resp:
        events = parse_sse(resp)

    errs = [e for e in events if e[0] == "error"]
    assert len(errs) == 1
    assert errs[0][1]["error"]["code"] == "LLM_NO_KEY"


def test_conversation_history(monkeypatch, client):
    child_id = _make_child(client)

    def fake_chat_json(messages, max_retries=2):
        return (
            {
                "risk_level": "L4",
                "conclusion": "可以逐步添加辅食",
                "actions": ["从强化铁米粉开始"],
                "evidence": [],
                "red_flags": [],
                "disclaimer": "请咨询医生。",
                "followup_question": None,
                "source_ids": [],
            },
            None,
        )

    monkeypatch.setattr("app.services.llm.chat_json", fake_chat_json)
    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "8 个月辅食加什么"}
    ) as resp:
        events = parse_sse(resp)
    conv_id = [e for e in events if e[0] == "done"][0][1]["conversation_id"]

    r = client.get(f"/api/v1/qa/conversations/{conv_id}")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["risk_level"] == "L4"


def test_list_conversations(monkeypatch, client):
    child_id = _make_child(client)

    def fake_chat_json(messages, max_retries=2):
        return (
            {
                "risk_level": "L4",
                "conclusion": "可以逐步添加辅食",
                "actions": ["从强化铁米粉开始"],
                "evidence": [],
                "red_flags": [],
                "disclaimer": "请咨询医生。",
                "followup_question": None,
                "source_ids": [],
            },
            None,
        )

    monkeypatch.setattr("app.services.llm.chat_json", fake_chat_json)
    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "8 个月辅食加什么"}
    ) as resp:
        parse_sse(resp)

    r = client.get("/api/v1/qa/conversations", params={"child_id": child_id})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["child_id"] == child_id
    assert items[0]["title"] == "8 个月辅食加什么"


def test_list_conversations_missing_child(client):
    r = client.get("/api/v1/qa/conversations", params={"child_id": 9999})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CHILD_NOT_FOUND"


def _ask_once(monkeypatch, client, child_id):
    def fake_chat_json(messages, max_retries=2):
        return (
            {
                "risk_level": "L4",
                "conclusion": "可以逐步添加辅食",
                "actions": ["从强化铁米粉开始"],
                "evidence": [],
                "red_flags": [],
                "disclaimer": "请咨询医生。",
                "followup_question": None,
                "source_ids": [],
            },
            None,
        )

    monkeypatch.setattr("app.services.llm.chat_json", fake_chat_json)
    with client.stream("POST", "/api/v1/qa", json={"child_id": child_id, "question": "8 个月辅食加什么"}) as resp:
        parse_sse(resp)


def test_delete_conversation(monkeypatch, client):
    child_id = _make_child(client)
    _ask_once(monkeypatch, client, child_id)
    conv_id = client.get("/api/v1/qa/conversations", params={"child_id": child_id}).json()["items"][0]["id"]

    d = client.delete(f"/api/v1/qa/conversations/{conv_id}")
    assert d.status_code == 204
    assert client.get("/api/v1/qa/conversations", params={"child_id": child_id}).json()["items"] == []


def test_delete_all_conversations(monkeypatch, client):
    child_id = _make_child(client)
    _ask_once(monkeypatch, client, child_id)
    _ask_once(monkeypatch, client, child_id)

    d = client.delete("/api/v1/qa/conversations", params={"child_id": child_id})
    assert d.status_code == 204
    assert client.get("/api/v1/qa/conversations", params={"child_id": child_id}).json()["items"] == []

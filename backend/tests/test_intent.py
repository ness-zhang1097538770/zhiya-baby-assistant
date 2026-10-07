"""入口意图识别：归一化降级 + 失败兜底 unknown 的单元测试。"""
import pytest

from app.schemas.schemas import IntentResult
from app.services import intent_service
from app.services.llm import LLMError


def _norm(data: dict) -> IntentResult:
    return intent_service._normalize(data)


def test_normalize_ask():
    r = _norm({"intent": "ask", "params": {"question": "8个月该打什么疫苗"}})
    assert r.intent == "ask"
    assert r.params["question"] == "8个月该打什么疫苗"


def test_normalize_unknown_on_bad_intent():
    r = _norm({"intent": "唱歌", "params": {}})
    assert r.intent == "unknown"
    assert r.params == {}


def test_normalize_record_type_fallback():
    r = _norm({"intent": "record", "params": {"type": "洗澡", "note": "洗了个澡"}})
    assert r.intent == "record"
    assert r.params["type"] == "custom"
    assert r.params["note"] == "洗了个澡"


def test_normalize_reminder_time():
    r = _norm(
        {
            "intent": "reminder",
            "params": {"title": "喝奶", "type": "feeding", "time": "15:00"},
        }
    )
    assert r.intent == "reminder"
    assert r.params["time"] == "15:00"
    assert r.params["type"] == "feeding"


def test_normalize_reminder_bad_time_to_none():
    r = _norm(
        {"intent": "reminder", "params": {"title": "喝奶", "time": "下午三点"}}
    )
    assert r.params["time"] is None
    assert r.params["type"] == "custom"  # 非法提醒类型兜底 custom


def test_classify_llm_failure_falls_back_to_unknown(monkeypatch):
    def _boom(messages, max_retries=2):
        raise LLMError("LLM_FAILED", "模型不可用")

    monkeypatch.setattr("app.services.llm.chat_json", _boom)
    r = intent_service.classify_intent("宝宝三点喝奶")
    assert r.intent == "unknown"
    assert r.params == {}


def test_intent_api_returns_structure(monkeypatch, client):
    child_id = client.post(
        "/api/v1/children",
        json={"nickname": "小糯米", "birth_date": "2025-01-15"},
    ).json()["id"]

    def _fake(messages, max_retries=2):
        return (
            {"intent": "reminder", "params": {"title": "喝奶", "time": "15:00", "type": "feeding"}},
            None,
        )

    monkeypatch.setattr("app.services.llm.chat_json", _fake)
    r = client.post(
        "/api/v1/intent/classify",
        json={"child_id": child_id, "text": "宝宝下午三点要喝奶"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "reminder"
    assert body["params"]["time"] == "15:00"


def test_intent_api_rejects_foreign_child(monkeypatch, client):
    # 另一个家庭的孩子 id 不存在或不属于当前家庭，应被拒绝
    r = client.post(
        "/api/v1/intent/classify",
        json={"child_id": 99999, "text": "宝宝喝奶"},
    )
    assert r.status_code in (403, 404)

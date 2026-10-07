"""Agent Loop（s01）：追问（need_info）+ 复查补全的受控循环。"""
import pytest

from app.models.models import Child, Event, Family, Reminder
from app.services import agent_service
from app.services.llm import LLMError


def _mk_child(db) -> Child:
    fam = Family(name="测试家庭")
    db.add(fam)
    db.commit()
    db.refresh(fam)
    c = Child(family_id=fam.id, nickname="小糯米", birth_date="2025-01-15")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_need_info_returns_followup_no_execution(monkeypatch, db):
    child = _mk_child(db)
    monkeypatch.setattr(
        "app.services.llm.chat_json",
        lambda messages: (
            {
                "intent": "need_info",
                "reply": "好的",
                "followup_question": "要记什么内容呢？",
                "params": {},
                "actions": [],
                "done": False,
            },
            None,
        ),
    )
    r = agent_service.run_agent(db, child, "记一下")
    assert r["intent"] == "need_info"
    assert r["followup_question"] == "要记什么内容呢？"
    assert r["executed"] == [] and r["pending"] == []
    assert db.query(Event).count() == 0


def test_recheck_supplements_missing_action(monkeypatch, db):
    child = _mk_child(db)
    plans = [
        # 首轮：只规划了 record_event（漏了 reminder）
        {
            "intent": "action", "reply": "好", "followup_question": None, "params": {},
            "done": False,
            "actions": [{"tool": "record_event", "params": {"type": "feeding", "note": "喝了150ml奶"}}],
        },
        # 复查轮：补上 reminder
        {
            "intent": "action", "reply": "", "followup_question": None, "params": {},
            "done": False,
            "actions": [{"tool": "create_reminder", "params": {"type": "feeding", "title": "喂奶", "in_minutes": 120}}],
        },
    ]
    monkeypatch.setattr("app.services.llm.chat_json", lambda messages: (plans.pop(0), None))
    r = agent_service.run_agent(db, child, "记下喝了150ml奶，再定个2小时后喂奶提醒")
    assert [e["tool"] for e in r["executed"]] == ["record_event", "create_reminder"]
    assert db.query(Event).count() == 1
    assert db.query(Reminder).count() == 1


def test_recheck_done_stops(monkeypatch, db):
    child = _mk_child(db)
    plans = [
        {
            "intent": "action", "reply": "好", "followup_question": None, "params": {},
            "done": False,
            "actions": [{"tool": "record_event", "params": {"type": "feeding", "note": "喝了奶"}}],
        },
        {
            "intent": "action", "reply": "", "followup_question": None, "params": {},
            "done": True, "actions": [],
        },
    ]
    monkeypatch.setattr("app.services.llm.chat_json", lambda messages: (plans.pop(0), None))
    r = agent_service.run_agent(db, child, "记下喝了奶")
    assert [e["tool"] for e in r["executed"]] == ["record_event"]
    assert db.query(Event).count() == 1


def test_recheck_duplicate_action_dedup(monkeypatch, db):
    child = _mk_child(db)
    # 复查轮返回与首轮相同的动作 → 去重，不重复执行
    same = {
        "intent": "action", "reply": "好", "followup_question": None, "params": {},
        "done": False,
        "actions": [{"tool": "record_event", "params": {"type": "feeding", "note": "喝了奶"}}],
    }
    monkeypatch.setattr("app.services.llm.chat_json", lambda messages: (dict(same), None))
    r = agent_service.run_agent(db, child, "记下喝了奶")
    assert len(r["executed"]) == 1
    assert db.query(Event).count() == 1


def test_recheck_llm_failure_keeps_first_round(monkeypatch, db):
    child = _mk_child(db)
    calls = {"n": 0}

    def _fake(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                {
                    "intent": "action", "reply": "好", "followup_question": None, "params": {},
                    "done": False,
                    "actions": [{"tool": "record_event", "params": {"type": "feeding", "note": "喝了奶"}}],
                },
                None,
            )
        raise LLMError("LLM_FAILED", "复查挂了")

    monkeypatch.setattr("app.services.llm.chat_json", _fake)
    r = agent_service.run_agent(db, child, "记下喝了奶")
    assert [e["tool"] for e in r["executed"]] == ["record_event"]
    assert db.query(Event).count() == 1


def test_agent_api_returns_followup(client, monkeypatch):
    child_id = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2025-01-15"}).json()["id"]
    monkeypatch.setattr(
        "app.services.llm.chat_json",
        lambda messages: (
            {"intent": "need_info", "reply": "好的", "followup_question": "提醒定在几点？", "params": {}, "actions": [], "done": False},
            None,
        ),
    )
    r = client.post("/api/v1/agent/run", json={"child_id": child_id, "text": "设个提醒"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "need_info"
    assert body["followup_question"] == "提醒定在几点？"

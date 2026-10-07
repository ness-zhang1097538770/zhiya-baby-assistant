"""育儿管家（agent）：计划归一化 + 确定性执行 + 权限 + 记忆抽取 + 失败兜底。"""
import pytest

from app.models.models import Child, ChildFact, Event, Family, Reminder
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


def _fake_llm(monkeypatch, plan: dict):
    monkeypatch.setattr("app.services.llm.chat_json", lambda messages: (plan, None))


# ---- 计划归一化（s02 白名单 + 结构校验） ----

def test_normalize_plan_intent_fallback_to_unknown():
    plan = agent_service._normalize_plan({"intent": "唱歌", "reply": "x", "actions": []})
    assert plan["intent"] == "unknown"


def test_normalize_plan_drops_unknown_tool():
    plan = agent_service._normalize_plan(
        {
            "intent": "action",
            "actions": [
                {"tool": "delete_everything", "params": {}},
                {"tool": "record_event", "params": {"type": "feeding", "note": "喝了奶"}},
            ],
        }
    )
    assert [a["tool"] for a in plan["actions"]] == ["record_event"]


def test_normalize_plan_ignores_non_dict_actions():
    plan = agent_service._normalize_plan({"intent": "action", "actions": ["oops", None, 3]})
    assert plan["actions"] == []


def test_normalize_plan_params_not_dict_dropped():
    plan = agent_service._normalize_plan(
        {"intent": "action", "actions": [{"tool": "record_event", "params": "bad"}]}
    )
    assert plan["actions"][0]["params"] == {}


# ---- 直接执行（auto） ----

def test_record_event_executes(monkeypatch, db):
    child = _mk_child(db)
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "好",
            "params": {},
            "actions": [
                {"tool": "record_event", "params": {"type": "feeding", "note": "喝了150ml奶", "data": {"amount_ml": 150}}}
            ],
        },
    )
    r = agent_service.run_agent(db, child, "宝宝喝了150ml奶")
    assert r["intent"] == "action"
    assert r["executed"][0]["tool"] == "record_event"
    assert "喂养" in r["executed"][0]["summary"]
    evs = db.query(Event).filter(Event.child_id == child.id).all()
    assert len(evs) == 1
    assert evs[0].type == "feeding"
    assert "150ml" in evs[0].note


def test_create_reminder_executes_with_in_minutes(monkeypatch, db):
    child = _mk_child(db)
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "",
            "params": {},
            "actions": [
                {"tool": "create_reminder", "params": {"type": "feeding", "title": "喂奶", "in_minutes": 120}}
            ],
        },
    )
    r = agent_service.run_agent(db, child, "两小时后喂奶")
    assert r["executed"][0]["tool"] == "create_reminder"
    rems = db.query(Reminder).filter(Reminder.child_id == child.id).all()
    assert len(rems) == 1
    assert "喂奶" in rems[0].title
    assert rems[0].remind_at is not None


def test_reminder_without_time_skipped(monkeypatch, db):
    child = _mk_child(db)
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "",
            "params": {},
            "actions": [{"tool": "create_reminder", "params": {"type": "feeding", "title": "喂奶"}}],
        },
    )
    r = agent_service.run_agent(db, child, "提醒喂奶")
    assert r["executed"] == []
    assert db.query(Reminder).count() == 0


def test_save_fact_executes_with_ai_extract_marker(monkeypatch, db):
    child = _mk_child(db)
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "",
            "params": {},
            "actions": [{"tool": "save_fact", "params": {"category": "allergy", "key": "鸡蛋", "value": "过敏"}}],
        },
    )
    r = agent_service.run_agent(db, child, "宝宝对鸡蛋过敏")
    assert r["executed"][0]["tool"] == "save_fact"
    facts = db.query(ChildFact).filter(ChildFact.child_id == child.id).all()
    assert len(facts) == 1
    assert facts[0].source == "ai_extract"
    assert facts[0].key == "鸡蛋"
    assert facts[0].category == "allergy"


def test_save_fact_bad_category_skipped(monkeypatch, db):
    child = _mk_child(db)
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "",
            "params": {},
            "actions": [{"tool": "save_fact", "params": {"category": "心情", "key": "x", "value": "y"}}],
        },
    )
    r = agent_service.run_agent(db, child, "随便记")
    assert r["executed"] == []
    assert db.query(ChildFact).count() == 0


def test_multiple_actions_in_one_sentence(monkeypatch, db):
    child = _mk_child(db)
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "好",
            "params": {},
            "actions": [
                {"tool": "record_event", "params": {"type": "feeding", "note": "喝了奶"}},
                {"tool": "save_fact", "params": {"category": "preference", "key": "苹果泥", "value": "喜欢吃"}},
            ],
        },
    )
    r = agent_service.run_agent(db, child, "记下喝了奶，宝宝喜欢苹果泥")
    assert [e["tool"] for e in r["executed"]] == ["record_event", "save_fact"]
    assert db.query(Event).count() == 1
    assert db.query(ChildFact).count() == 1


# ---- 权限（s03 confirm） ----

def test_create_story_goes_pending_not_executed(monkeypatch, db):
    child = _mk_child(db)
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "",
            "params": {},
            "actions": [{"tool": "create_story", "params": {"theme": "恐龙"}}],
        },
    )
    r = agent_service.run_agent(db, child, "讲个恐龙故事")
    assert r["executed"] == []
    assert r["pending"][0]["tool"] == "create_story"
    assert "恐龙" in r["pending"][0]["summary"]


# ---- 失败兜底 ----

def test_run_agent_llm_failure_falls_back_to_unknown(monkeypatch, db):
    child = _mk_child(db)

    def _boom(messages):
        raise LLMError("LLM_FAILED", "模型不可用")

    monkeypatch.setattr("app.services.llm.chat_json", _boom)
    r = agent_service.run_agent(db, child, "随便一句话")
    assert r["intent"] == "unknown"
    assert r["executed"] == []
    assert r["pending"] == []


# ---- 接口 ----

def test_agent_api_returns_structure(monkeypatch, client):
    child_id = client.post(
        "/api/v1/children",
        json={"nickname": "小糯米", "birth_date": "2025-01-15"},
    ).json()["id"]
    _fake_llm(
        monkeypatch,
        {
            "intent": "action",
            "reply": "好",
            "params": {},
            "actions": [{"tool": "record_event", "params": {"type": "feeding", "note": "喝了奶"}}],
        },
    )
    r = client.post("/api/v1/agent/run", json={"child_id": child_id, "text": "记一下喝了奶"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "action"
    assert body["executed"][0]["tool"] == "record_event"


def test_agent_api_rejects_foreign_child(client):
    r = client.post("/api/v1/agent/run", json={"child_id": 99999, "text": "记一笔"})
    assert r.status_code in (403, 404)

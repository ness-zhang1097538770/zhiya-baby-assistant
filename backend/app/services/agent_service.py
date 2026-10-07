"""育儿管家：一句话 → 规划（LLM）→ 确定性执行（工具分发表 + 权限 + 记忆抽取）。

参考 learn-claude-code：
- s02 Tool Use：TOOL_HANDLERS 分发表，每个工具一个 handler + 参数校验
- s03 Permission：每个工具标注 auto / confirm，确认类动作不执行、返回 pending
- s09 Memory：save_fact 从对话抽取结构化事实写入 ChildFact
"""
import json
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.models import Child, ChildFact, Event, Reminder
from app.schemas.schemas import EVENT_TYPES, REMINDER_TYPES
from app.services import llm, memory
from app.services.memory import FACT_LABELS, VALID_FACT_CATEGORIES
from app.services.prompts.agent_prompt import build_agent_messages, build_recheck_messages

VALID_INTENTS = {"ask", "action", "need_info", "unknown"}
MAX_AGENT_ROUNDS = 2  # 首轮规划 + 最多一轮复查补全（s01 受控循环，硬上限防烧钱/死循环）

EVENT_LABELS = {
    "feeding": "喂养", "sleep": "睡眠", "diaper": "排便",
    "growth": "成长", "milestone": "里程碑", "custom": "记录",
}
REMINDER_LABELS = {
    "vaccine": "疫苗提醒", "feeding": "喂奶提醒", "routine": "作息提醒", "custom": "提醒",
}


def _now() -> datetime:
    # 本地 naive 时间，与前端 datetime-local 的存取约定一致（不引入时区偏移）
    return datetime.now()


def _clean(value) -> str:
    return (value or "").strip()


# ---- 工具 handler：参数校验 + 执行，返回给用户的简短摘要；无效参数返回 None（跳过） ----

def _do_record_event(db: Session, child_id: int, params: dict) -> str | None:
    t = _clean(params.get("type"))
    if t not in EVENT_TYPES:
        return None
    note = _clean(params.get("note")) or None
    data = params.get("data") if isinstance(params.get("data"), dict) else None
    e = Event(
        child_id=child_id,
        type=t,
        note=note,
        occurred_at=_now(),
        data_json=json.dumps(data, ensure_ascii=False) if data else None,
    )
    db.add(e)
    db.commit()
    label = EVENT_LABELS.get(t, t)
    return f"已记录{label}" + (f"：{note}" if note else "")


def _resolve_remind_at(params: dict) -> datetime | None:
    in_minutes = params.get("in_minutes")
    if isinstance(in_minutes, (int, float)) and 0 < in_minutes <= 10080:
        return _now() + timedelta(minutes=int(in_minutes))
    t = _clean(params.get("time"))
    if len(t) == 5 and t[2] == ":" and t[:2].isdigit() and t[3:].isdigit():
        hh, mm = int(t[:2]), int(t[3:])
        if 0 <= hh < 24 and 0 <= mm < 60:
            dt = datetime.combine(_now().date(), time(hh, mm))
            if dt <= _now():
                dt += timedelta(days=1)
            return dt
    return None


def _do_create_reminder(db: Session, child_id: int, params: dict) -> str | None:
    t = _clean(params.get("type"))
    if t not in REMINDER_TYPES:
        return None
    remind_at = _resolve_remind_at(params)
    if remind_at is None:
        return None  # 未说明时间，跳过，避免创建无时间提醒
    title = _clean(params.get("title")) or REMINDER_LABELS.get(t, "提醒")
    note = _clean(params.get("note")) or None
    r = Reminder(
        child_id=child_id,
        type=t,
        title=title[:100],
        note=note,
        remind_at=remind_at,
        repeat="one",
    )
    db.add(r)
    db.commit()
    when = remind_at.strftime("%m-%d %H:%M")
    return f"已创建提醒：{title}（{when}）"


def _do_save_fact(db: Session, child_id: int, params: dict) -> str | None:
    category = _clean(params.get("category"))
    if category not in VALID_FACT_CATEGORIES:
        return None
    key = _clean(params.get("key"))
    value = _clean(params.get("value"))
    if not key or not value:
        return None
    label = FACT_LABELS.get(category, category)
    key_trimmed = key[:100]
    value_trimmed = value[:500]

    # 去重（对应 S09 should_store_memory）：同 category+key 已有活跃事实时更新而非重复插入
    existing = (
        db.query(ChildFact)
        .filter(
            ChildFact.child_id == child_id,
            ChildFact.category == category,
            ChildFact.key == key_trimmed,
            ChildFact.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        if existing.value == value_trimmed:
            return f"已记住[{label}] {key}：{value}（之前已记过，未重复添加）"
        existing.value = value_trimmed
        existing.source = "ai_extract"
        db.commit()
        return f"已更新[{label}] {key}：{value}"

    f = ChildFact(
        child_id=child_id,
        category=category,
        key=key_trimmed,
        value=value_trimmed,
        source="ai_extract",
    )
    db.add(f)
    db.commit()
    return f"已记住[{label}] {key}：{value}"


def _pending_summary(tool: str, params: dict) -> str:
    if tool == "create_story":
        theme = _clean(params.get("theme"))
        return f"生成绘本故事" + (f"：{theme}" if theme else "")
    return tool


# 工具分发表（s02）：permission=auto 直接执行；confirm 返回 pending 交前端确认
TOOL_HANDLERS = {
    "record_event": {"permission": "auto", "handler": _do_record_event},
    "create_reminder": {"permission": "auto", "handler": _do_create_reminder},
    "save_fact": {"permission": "auto", "handler": _do_save_fact},
    "create_story": {"permission": "confirm", "handler": None},
}


def _normalize_plan(data: dict) -> dict:
    """把模型输出归一化为安全计划；未知工具/非法结构一律丢弃，绝不执行。"""
    intent = _clean(data.get("intent"))
    if intent not in VALID_INTENTS:
        intent = "unknown"
    reply = _clean(data.get("reply"))
    followup = _clean(data.get("followup_question")) or None
    done = bool(data.get("done"))
    params = data.get("params") if isinstance(data.get("params"), dict) else {}
    actions = []
    raw = data.get("actions")
    if isinstance(raw, list):
        for a in raw:
            if not isinstance(a, dict):
                continue
            tool = _clean(a.get("tool"))
            if tool not in TOOL_HANDLERS:
                continue
            ap = a.get("params") if isinstance(a.get("params"), dict) else {}
            actions.append({"tool": tool, "params": ap})
    return {
        "intent": intent,
        "reply": reply,
        "followup_question": followup,
        "done": done,
        "params": params,
        "actions": actions,
    }


def _action_key(tool: str, params: dict) -> str:
    return f"{tool}:{json.dumps(params, ensure_ascii=False, sort_keys=True)}"


def _execute_actions(db: Session, child_id: int, actions: list[dict], seen: set) -> tuple[list, list]:
    """执行一批动作（去重）；返回 (executed, pending)。confirm 类不执行、记 pending。"""
    executed, pending = [], []
    for action in actions:
        tool, params = action["tool"], action["params"]
        key = _action_key(tool, params)
        if key in seen:
            continue
        seen.add(key)
        meta = TOOL_HANDLERS[tool]
        if meta["permission"] == "confirm":
            pending.append({"tool": tool, "summary": _pending_summary(tool, params), "params": params})
            continue
        try:
            summary = meta["handler"](db, child_id, params)
        except Exception:  # noqa: BLE001 —— 单动作失败不影响其他动作
            summary = None
        if summary:
            executed.append({"tool": tool, "summary": summary})
    return executed, pending


def run_agent(db: Session, child: Child, text: str) -> dict:
    """一句话 → 规划 → 执行 → 复查补全（Agent Loop，受控轮次）。

    LLM 失败兜底 unknown，不抛错、不阻塞入口。
    """
    # 召回已知事实（S09 读侧），帮助模型理解语境；事实只作背景，不重复抽取
    facts_text = memory.format_facts(memory.recall_facts(db, child.id, text))
    try:
        data, _usage = llm.chat_json(build_agent_messages(text, facts_text))
        plan = _normalize_plan(data)
    except llm.LLMError:
        plan = {"intent": "unknown", "reply": "", "followup_question": None, "done": False, "params": {}, "actions": []}

    # 追问：信息不足，交前端追问（不做无限多轮，前端拿到后一次性补齐再回来）
    if plan["intent"] == "need_info":
        return {
            "intent": "need_info",
            "reply": plan["reply"] or "我还需要确认一下。",
            "followup_question": plan["followup_question"] or "你具体想让我做什么呢？",
            "params": {},
            "executed": [],
            "pending": [],
        }

    # 问育儿 / 无法理解：直接返回，不执行
    if plan["intent"] != "action":
        return {
            "intent": plan["intent"],
            "reply": plan["reply"],
            "followup_question": None,
            "params": plan["params"],
            "executed": [],
            "pending": [],
        }

    # action：执行 + 复查补全循环（s01：工具结果喂回，模型再决策是否补办）
    executed, pending = [], []
    seen: set = set()
    actions = plan["actions"]
    for _round in range(MAX_AGENT_ROUNDS):
        e, p = _execute_actions(db, child.id, actions, seen)
        executed.extend(e)
        pending.extend(p)

        if _round == MAX_AGENT_ROUNDS - 1:
            break  # 达到轮次上限，不再复查

        try:
            data2, _usage = llm.chat_json(build_recheck_messages(text, facts_text, executed, pending))
            plan2 = _normalize_plan(data2)
        except llm.LLMError:
            break
        if plan2["done"] or not plan2["actions"]:
            break
        actions = plan2["actions"]

    return {
        "intent": "action",
        "reply": plan["reply"],
        "followup_question": None,
        "params": plan["params"],
        "executed": executed,
        "pending": pending,
    }

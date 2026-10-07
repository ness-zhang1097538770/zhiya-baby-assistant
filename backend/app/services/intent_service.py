"""入口意图识别服务：LLM 分类 + 槽位抽取，失败时兜底 unknown，绝不阻塞前端路由。"""
import re
from typing import Any, Dict

from app.schemas.schemas import IntentResult
from app.services import llm
from app.services.prompts.intent_prompt import build_intent_messages

VALID_INTENTS = {"ask", "record", "reminder", "story", "unknown"}
VALID_EVENT_TYPES = {"feeding", "sleep", "diaper", "growth", "milestone", "custom"}
VALID_REMINDER_TYPES = {"vaccine", "feeding", "routine", "custom"}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _clean(text: str) -> str:
    return (text or "").strip()


def _as_str(value: Any) -> str:
    return _clean(str(value)) if value is not None else ""


def _as_optional_str(value: Any) -> str | None:
    s = _clean(str(value)) if value is not None else ""
    return s or None


def _as_time(value: Any) -> str | None:
    s = _as_str(value)
    return s if _TIME_RE.match(s) else None


def _normalize(data: Dict[str, Any]) -> IntentResult:
    """把模型输出归一化为合法 IntentResult；任何非法值都安全降级。"""
    intent = _as_str(data.get("intent"))
    if intent not in VALID_INTENTS:
        intent = "unknown"

    params_raw = data.get("params")
    if not isinstance(params_raw, dict):
        params_raw = {}

    params: Dict[str, Any] = {}
    if intent == "ask":
        q = _as_str(params_raw.get("question"))
        params["question"] = q if q else _as_str(data.get("text", ""))
    elif intent == "record":
        t = _as_str(params_raw.get("type"))
        params["type"] = t if t in VALID_EVENT_TYPES else "custom"
        params["note"] = _as_optional_str(params_raw.get("note"))
    elif intent == "reminder":
        t = _as_str(params_raw.get("type"))
        params["type"] = t if t in VALID_REMINDER_TYPES else "custom"
        title = _as_str(params_raw.get("title"))
        params["title"] = title or "提醒"
        params["note"] = _as_optional_str(params_raw.get("note"))
        params["time"] = _as_time(params_raw.get("time"))
    elif intent == "story":
        theme = _as_str(params_raw.get("theme"))
        params["theme"] = theme or None
    # unknown：params 留空

    return IntentResult(intent=intent, params=params)


def classify_intent(text: str) -> IntentResult:
    """识别意图。模型失败/超时一律兜底 unknown，保证入口永远可用。"""
    messages = build_intent_messages(text)
    try:
        data, _usage = llm.chat_json(messages)
        return _normalize(data)
    except llm.LLMError:
        # 分类失败不影响用户手动选择入口
        return IntentResult(intent="unknown", params={})

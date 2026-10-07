"""DeepSeek 客户端：统一处理 SDK 初始化失败、超时、有限重试。"""
import json
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from app.core.config import settings
from app.services import cost
from app.services.guard import AD_FIELD_MARKERS


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def get_client() -> OpenAI:
    """构造客户端。无 Key 等初始化失败在这里抛出，供最外层兜底为 error 事件。"""
    if not settings.deepseek_api_key:
        raise LLMError("LLM_NO_KEY", "缺少 DeepSeek API Key，请在 .env 配置后重试")
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.deepseek_timeout,
        max_retries=0,
    )


# 广告字段泄漏标记（铁律三 / E1）：这些字段/标记不得进入任何模型调用
_ALLOWED_MESSAGE_KEYS = {"role", "content"}


def _assert_no_ad_leak(messages: List[Dict[str, str]]) -> None:
    """广告字段白名单断言：消息结构仅允许 role/content，内容不得含广告字段标记。"""
    for m in messages:
        if not isinstance(m, dict):
            raise LLMError("LLM_BAD_MESSAGE", "消息结构非法")
        extra = set(m.keys()) - _ALLOWED_MESSAGE_KEYS
        if extra:
            raise LLMError("LLM_AD_LEAK", f"消息包含非法字段：{','.join(sorted(extra))}")
        content = str(m.get("content") or "")
        low = content.lower()
        for marker in AD_FIELD_MARKERS:
            if marker in low:
                raise LLMError("LLM_AD_LEAK", f"检测到广告字段泄漏：{marker}")


def chat_json(messages: List[Dict[str, str]], max_retries: int = 2) -> Tuple[Dict[str, Any], Any]:
    """调用模型并要求 JSON 输出；解析失败有限重试，仍失败抛 LLMError。"""
    _assert_no_ad_leak(messages)
    client = get_client()
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.deepseek_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            content = resp.choices[0].message.content or ""
            data = json.loads(content)
            cost.record(settings.deepseek_model, "chat",
                        tokens=getattr(resp.usage, "total_tokens", None))
            return data, resp.usage
        except LLMError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise LLMError("LLM_FAILED", f"模型调用失败：{type(last_err).__name__}")

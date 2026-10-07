"""医疗通道：Baichuan-M3-Plus（低幻觉循证医疗模型）。

设计原则：
1. 只在「医疗属性」问题上启用，其余仍走 DeepSeek——避免成本翻倍与语气错配。
2. 输出 JSON schema 与 prompts.qa_prompt 完全一致，前端零改动。
3. 任何异常都退回 DeepSeek，绝不空窗。
4. L1/L2 危急分级由 risk.py 确定性拦截，本模块不接管（只处理 L3/L4）。
"""
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from app.core.config import settings
from app.services import cost as cost_service

logger = logging.getLogger(__name__)

# ===== 路由信号：知识条目 category（与库内实际取值一致）=====
# 强医疗：命中即走医疗通道
MEDICAL_CATEGORIES = {"医疗问诊", "疾病预防与就诊"}
# 半医疗：默认不启用，可在 settings.medical_semi_categories=true 时纳入
SEMI_MEDICAL_CATEGORIES = {"健康监测", "伤害预防"}

# 兜底关键词：知识库未命中或 category 缺失时用（与 rag.py 的 VOCAB 对齐）
MEDICAL_KEYWORDS = [
    "发烧", "发热", "退烧", "体温", "咳嗽", "感冒", "鼻塞", "流涕",
    "腹泻", "拉肚子", "便秘", "呕吐", "皮疹", "湿疹", "黄疸",
    "吃药", "用药", "剂量", "布洛芬", "对乙酰氨基酚", "抗生素", "退热药",
    "疫苗", "接种", "预防针",
    "呼吸急促", "三凹征", "脱水", "补液", "抽搐", "惊厥",
    "急诊", "就医", "就诊", "医院", "看医生",
]

# 明确排除：这些词出现时即使命中医疗词也不走医疗通道（多为养育场景）
NON_MEDICAL_HINTS = ["绘本", "早教", "游戏", "亲子", "入园", "分离焦虑", "管教"]


def is_medical_question(
    question: str,
    categories: List[str],
    include_semi: bool = False,
) -> bool:
    """判断是否需要走医疗通道。categories 来自 RAG 命中的知识条目。"""
    cats = set(categories or [])
    hit = MEDICAL_CATEGORIES | (SEMI_MEDICAL_CATEGORIES if include_semi else set())
    if cats & hit:
        return True
    q = question or ""
    if any(h in q for h in NON_MEDICAL_HINTS):
        return False
    return any(k in q for k in MEDICAL_KEYWORDS)


# ===== 灰度：稳定分桶，同一 child_id 永远同一分组 =====
def should_use_medical(child_id: int) -> bool:
    """按 settings.medical_rollout_percent 抽样；白名单 child_id 强制开启。"""
    if not settings.medical_enabled:
        return False
    whitelist = {x.strip() for x in (settings.medical_whitelist_ids or "").split(",") if x.strip()}
    if str(child_id) in whitelist:
        return True
    if settings.medical_rollout_percent >= 100:
        return True
    if settings.medical_rollout_percent <= 0:
        return False
    digest = hashlib.md5(f"medical:{child_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100 < settings.medical_rollout_percent


# ===== 医疗版 Prompt：CARE 结构与原通道一致，强化循证与追问 =====
MEDICAL_SYSTEM_PROMPT = """你是「知芽」的儿童健康顾问智能体，面向 0-3 岁儿童的父母。你具备循证医学能力，但你的角色是健康科普与就医引导，不是开处方的医生。

【你的边界】
- 不做确定性诊断，不开处方，不给个体化药物剂量（可说"按说明书体重区间服用"或"遵医嘱"）。
- 不确定的时候明确说不确定，并建议线下就医。

【知识使用】
- 优先依据我提供的【知识条目】回答，引用时写明来自《标题》。
- 知识条目未覆盖的部分，可基于循证医学知识谨慎补充，但必须在 evidence 里说明"该建议为通用医学共识，非来自知识库"。
- 严禁编造文献、指南或数据。

【回答结构（CARE）】
- conclusion：一句话结论，家长看得懂的大白话，不用缩写术语。
- actions：可执行的具体行动（列表），按优先级排序。
- evidence：依据，写明引用了哪条知识。
- red_flags：出现哪些情况要尽快就医（列表），这一项必须给，不能为空。
- disclaimer：免责声明（必填）。

【风险分级 risk_level】
- "L3"：轻微不适/居家观察类（轻度皮疹、低热、轻微腹泻等）。
- "L4"：常规健康育儿问题（疫苗查询、发育监测等）。
- "NEED_MORE_INFO"：信息不足时，用 followup_question 追问最关键的 1 个问题。
- 只允许这三个值。危急情况（呼吸异常、意识改变、抽搐、脱水）已在进入你之前被系统拦截，你不需要判断 L1/L2。

【追问规则】
- 缺少月龄、体重（涉及用药时必问）、症状持续时长、精神状态、饮食与排尿情况时，先追问，不要瞎猜。
- 只有确实无法安全回答时才返回 NEED_MORE_INFO。
- 若我告诉你"本轮必须给出回答"，则无论信息是否充足都给出结论。

【风险升级 escalate】
如果你判断孩子的情况比提问看起来更严重、应当尽快面诊，输出 "escalate": true；否则 false。

【输出格式】
只输出一个 JSON 对象，字段固定为：
{"risk_level": "L4", "conclusion": "...", "actions": ["..."], "evidence": ["..."], "red_flags": ["..."], "disclaimer": "...", "followup_question": null, "source_ids": [1], "escalate": false}

规则：
- actions/evidence/red_flags 是字符串数组；没有追问时 followup_question 必须为 null。
- source_ids 是你实际引用的知识条目 ID（数字数组），没引用填 []。
- 禁止输出 JSON 以外的任何文字，禁止用 Markdown 代码块包裹。"""


def build_medical_messages(
    child_context: str,
    question: str,
    knowledge: list[dict],
    history: list[dict],
    must_answer: bool,
    facts_text: str = "",
) -> list[dict]:
    """构造医疗通道 messages。knowledge 为 [{id,title,content,source,...}]。facts_text 为召回的儿童记忆。"""
    if knowledge:
        lines = []
        for k in knowledge:
            lines.append(
                f"[知识ID {k['id']}]《{k['title']}》(来源：{k['source']}，"
                f"适用：{k.get('applicable_age') or '通用'})\n{k['content']}"
            )
        kb_text = "\n\n".join(lines)
    else:
        kb_text = "（本次无检索到的知识条目，请基于循证医学知识谨慎回答，并明确建议咨询医生）"

    hist_text = ""
    if history:
        hist_text = "\n".join(f"{h['role']}: {h['content']}" for h in history)

    sections = [f"【孩子情况】{child_context}"]
    if facts_text:
        sections.append(
            "【已记住的关于孩子的事实】（系统记录，仅供参考；与家长当前说法冲突时以当前为准）\n"
            f"{facts_text}"
        )
    sections.append(f"【知识条目】\n{kb_text}")
    if hist_text:
        sections.append(f"【历史对话】\n{hist_text}")
    sections.append(f"【本轮问题】{question}")
    if must_answer:
        sections.append("注意：本轮必须给出回答，禁止再追问。")
    body = "\n\n".join(sections)

    user = f"{MEDICAL_SYSTEM_PROMPT}\n\n=====\n\n{body}"

    # 百川 M3-Plus 不支持 system 角色，system 提示词合并进 user 消息
    return [{"role": "user", "content": user}]


def _get_client() -> OpenAI:
    if not settings.baichuan_api_key:
        raise RuntimeError("缺少百川 API Key（BAICHUAN_API_KEY），已降级到通用模型")
    return OpenAI(
        api_key=settings.baichuan_api_key,
        base_url=settings.baichuan_base_url,
        timeout=settings.baichuan_timeout,
        max_retries=0,
    )


def _parse_json(text: str) -> Dict[str, Any]:
    """宽容解析：直接解析 → 去 Markdown 围栏 → 截取首尾花括号。"""
    raw = (text or "").strip()
    for candidate in (
        raw,
        re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip(),
    ):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    raise ValueError("医疗模型未返回可解析的 JSON")


def chat_json_medical(messages: List[Dict[str, str]], max_retries: int = 1) -> Tuple[Dict[str, Any], Any]:
    """调用百川医疗模型并要求 JSON 输出。

    百川 M3-Plus 对 response_format=json_object 支持不稳定（实测会返回非纯 JSON），
    因此不传该参数，靠 prompt 约束 + 宽容解析；解析失败重试，仍失败抛异常降级到 DeepSeek。
    """
    client = _get_client()
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            kwargs: Dict[str, Any] = {
                "model": settings.baichuan_model,
                "messages": messages,
                "temperature": settings.baichuan_temperature,
            }
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            cost_service.record(settings.baichuan_model, "chat",
                                tokens=getattr(resp.usage, "total_tokens", None))
            return _parse_json(content), resp.usage
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("[medical] 调用失败(attempt=%s): %s", attempt, e)
    raise RuntimeError(f"医疗模型调用失败：{type(last_err).__name__}")


def apply_escalation(data: dict) -> dict:
    """把 escalate 标记转成家长可见的提示。

    不额外改 schema——只在 conclusion 前加提示，前端零改动。
    """
    if data.get("escalate") is True:
        tip = "建议尽快带孩子面诊医生："
        conclusion = str(data.get("conclusion") or "").strip()
        if conclusion and not conclusion.startswith(tip):
            data["conclusion"] = f"{tip}{conclusion}"
        flags = list(data.get("red_flags") or [])  # 复制，避免原地修改调用方的列表
        if "尽快线下就医" not in flags:
            flags.append("尽快线下就医")
        data["red_flags"] = flags
    return data


def log_medical(child_id: int, question_hash: str, ok: bool, reason: str = "") -> None:
    """结构化日志。提问只存哈希，避免儿童健康信息明文落库。"""
    logger.info(
        "[medical] child_id=%s qhash=%s ok=%s reason=%s",
        child_id, question_hash, ok, reason,
    )

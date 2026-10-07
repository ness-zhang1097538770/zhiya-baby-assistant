"""育儿问答编排：风险分级 → RAG → 模型 → 结构化校验 → 结果。"""
import hashlib
import logging
import re
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import Child, Conversation, KnowledgeEntry, Message
from app.schemas.schemas import QAResult
from app.core.config import settings
from app.services import llm, medical, rag, risk, memory, guard
from app.services.llm import LLMError
from app.services.prompts.qa_prompt import build_qa_messages

logger = logging.getLogger(__name__)


def question_hash(question: str) -> str:
    """提问只存哈希，避免儿童健康信息明文落日志。"""
    return hashlib.md5((question or "").encode("utf-8")).hexdigest()[:12]


def age_in_months(birth_date: str) -> Optional[int]:
    """由出生日期算月龄。日期非法返回 None。"""
    try:
        y, m, d = map(int, birth_date.split("-"))
        bd = date(y, m, d)
        today = date.today()
        months = (today.year - bd.year) * 12 + (today.month - bd.month)
        if today.day < bd.day:
            months -= 1
        return max(months, 0)
    except Exception:  # noqa: BLE001
        return None


def build_child_context(child: Child) -> str:
    parts = [f"昵称：{child.nickname}"]
    m = age_in_months(child.birth_date)
    if m is not None:
        parts.append(f"月龄：{m} 个月")
    if child.gender:
        parts.append(f"性别：{child.gender}")
    if child.feeding_method:
        parts.append(f"喂养方式：{child.feeding_method}")
    if child.allergy_history:
        parts.append(f"过敏史：{child.allergy_history}")
    if child.premature:
        parts.append(f"是否早产：{child.premature}")
    return "；".join(parts)


def count_followups(db: Session, conversation_id: int) -> int:
    return (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
            Message.risk_level == "NEED_MORE_INFO",
        )
        .count()
    )


def build_history(db: Session, conversation_id: int, limit: int = 6) -> List[dict]:
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )
    msgs = list(reversed(msgs))
    return [{"role": m.role, "content": m.content} for m in msgs]


def _map_sources(db: Session, ids: List[int]) -> List[dict]:
    out = []
    seen = set()
    for eid in ids:
        if eid in seen:
            continue
        seen.add(eid)
        e = db.get(KnowledgeEntry, eid)
        if e is None:
            continue
        out.append(
            {
                "id": e.id,
                "title": e.title,
                "source": e.source,
                "version": e.version,
                "review_status": e.review_status,
            }
        )
    return out


def _parse_result(data: dict) -> QAResult:
    """宽容解析：把模型常见等价字段/类型差异归一化后强校验。"""
    def to_str_list(v):
        if v is None:
            return []
        if isinstance(v, str):
            return [x for x in re.split(r"[\n；;]+", v.strip()) if x]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    rl = str(data.get("risk_level") or "L4").strip().upper()
    if rl not in ("L3", "L4", "NEED_MORE_INFO"):
        rl = "L4"

    source_ids = []
    raw_src = data.get("source_ids", [])
    if isinstance(raw_src, list):
        for x in raw_src:
            try:
                source_ids.append(int(x))
            except (TypeError, ValueError):
                continue

    fq = data.get("followup_question")
    if isinstance(fq, str):
        fq = fq.strip() or None
    else:
        fq = None

    return QAResult(
        risk_level=rl,
        conclusion=str(data.get("conclusion") or "").strip(),
        actions=to_str_list(data.get("actions")),
        evidence=to_str_list(data.get("evidence")),
        red_flags=to_str_list(data.get("red_flags")),
        disclaimer=str(data.get("disclaimer") or "").strip(),
        followup_question=fq,
        source_ids=source_ids,
    )


def answer_question(
    db: Session, child: Child, question: str, conversation: Conversation
) -> dict:
    """返回 done 事件的数据结构。L1/L2 走确定性话术，L3/L4 走模型。"""
    # 1. 确定性风险分级（安全兜底）
    urgent = risk.classify_urgent(question)
    if urgent in ("L1", "L2"):
        data = risk.L1_RESPONSE if urgent == "L1" else risk.L2_RESPONSE
        return {
            "risk_level": urgent,
            "answer": _format_static(data),
            "conclusion": data["conclusion"],
            "actions": data["actions"],
            "evidence": data["evidence"],
            "red_flags": data["red_flags"],
            "disclaimer": data["disclaimer"],
            "followup_question": None,
            "followup_count": 0,
            "sources": [],
        }

    # 2. 检索 + 构造上下文
    knowledge = rag.retrieve(db, question)
    kb = [
        {
            "id": e.id,
            "title": e.title,
            "content": e.content,
            "source": e.source,
            "applicable_age": e.applicable_age,
            "category": e.category,  # 医疗通道的路由信号
        }
        for e in knowledge
    ]
    child_context = build_child_context(child)
    # 召回已记住的事实（S09 读侧），注入问答上下文
    facts_text = memory.format_facts(memory.recall_facts(db, child.id, question))
    followups = count_followups(db, conversation.id)
    must_answer = followups >= 2
    history = build_history(db, conversation.id)

    # 3. 模型路由：医疗属性问题走 Baichuan-M3-Plus，其余仍走 DeepSeek
    categories = [k.get("category") or "" for k in kb]
    qhash = question_hash(question)
    used_medical = False

    if medical.should_use_medical(child.id) and medical.is_medical_question(
        question, categories, include_semi=settings.medical_semi_categories
    ):
        try:
            med_messages = medical.build_medical_messages(
                child_context, question, kb, history, must_answer, facts_text
            )
            data, _usage = medical.chat_json_medical(med_messages)
            data = medical.apply_escalation(data)
            used_medical = True
            medical.log_medical(child.id, qhash, True, "ok")
        except Exception as e:  # noqa: BLE001
            # 医疗通道失败一律退回 DeepSeek，绝不空窗
            medical.log_medical(child.id, qhash, False, type(e).__name__)
            data, _usage = llm.chat_json(
                build_qa_messages(child_context, question, kb, history, must_answer, facts_text)
            )
    else:
        data, _usage = llm.chat_json(
            build_qa_messages(child_context, question, kb, history, must_answer, facts_text)
        )

    # 4. 结构化校验
    result = _parse_result(data)

    # V2.2 品牌污染检查（铁律三）：CARE 结构不得出现品牌/商品推荐标记
    _brand_hits = guard.scan_brand_markers(
        result.conclusion, " ".join(result.actions),
        " ".join(result.evidence), " ".join(result.red_flags), result.disclaimer,
    )
    if _brand_hits:
        logger.warning("[qa] brand markers detected in CARE: %s", _brand_hits)

    # 5. 追问上限：达到 2 轮强制给结论
    if result.followup_question and must_answer:
        result.followup_question = None
        result.risk_level = "L4" if result.risk_level == "NEED_MORE_INFO" else result.risk_level

    sources = _map_sources(db, result.source_ids)
    logger.info(
        "[qa] child=%s conv=%s medical=%s risk=%s",
        child.id, conversation.id, used_medical, result.risk_level,
    )

    return {
        "risk_level": result.risk_level,
        "answer": result.answer_text,
        "conclusion": result.conclusion,
        "actions": result.actions,
        "evidence": result.evidence,
        "red_flags": result.red_flags,
        "disclaimer": result.disclaimer,
        "followup_question": result.followup_question,
        "followup_count": followups,
        "sources": sources,
    }


def _format_static(data: dict) -> str:
    parts = [f"【结论】{data['conclusion']}"]
    parts.append("【请立即这样做】\n" + "\n".join(f"· {a}" for a in data["actions"]))
    parts.append("【何时必须就医】\n" + "\n".join(f"· {r}" for r in data["red_flags"]))
    parts.append(f"【免责声明】{data['disclaimer']}")
    return "\n\n".join(parts)

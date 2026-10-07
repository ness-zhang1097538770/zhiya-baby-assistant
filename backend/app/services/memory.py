"""记忆召回（S09 Memory 的「读」侧）：把 ChildFact 里记下的事实按相关性读回来注入上下文。

参考 learn-claude-code s09_memory：
- 存储：已由 ChildFact 表承担（save_fact 写入，source=ai_extract，可改可删）。
- 召回：先「选相关条目」，再「加载正文」。本产品一个孩子的事实通常是个位数~十几条，
  每条只有 key/value 很短，所以用确定性关键词匹配做召回（零额外模型成本、零延迟），
  而不是 S09 里那条「先让轻量模型选索引」的路径——那是给几十上百条记忆用的。
- 原则：召回的记忆是「背景知识」，不是新指令；与家长当前说法冲突时以当前说法为准。
"""
import re

from sqlalchemy.orm import Session

from app.models.models import ChildFact

# 事实类别 → 中文标签（与 agent_service 共用，统一从此处取）
FACT_LABELS = {
    "allergy": "过敏",
    "preference": "偏好",
    "milestone": "里程碑",
    "medical": "健康",
    "habit": "习惯",
    "note": "备注",
}
VALID_FACT_CATEGORIES = set(FACT_LABELS)


def list_child_facts(db: Session, child_id: int) -> list[ChildFact]:
    """返回该孩子所有未删除的事实，按最近更新倒序。"""
    return (
        db.query(ChildFact)
        .filter(
            ChildFact.child_id == child_id,
            ChildFact.deleted_at.is_(None),
        )
        .order_by(ChildFact.updated_at.desc())
        .all()
    )


def _keywords(text: str) -> set[str]:
    """抽取可匹配的关键词：连续 2+ 汉字，或 3+ 字母/数字。"""
    text = (text or "").lower()
    words = set(re.findall(r"[\u4e00-\u9fff]{2,}", text))
    words.update(re.findall(r"[a-z0-9_]{3,}", text))
    return words


def recall_facts(db: Session, child_id: int, query: str, max_items: int = 5) -> list[ChildFact]:
    """召回事实。事实少时全量注入（零漏召回），多了按关键词过滤到 max_items 条。

    S09 的「先让轻量模型选相关索引再加载正文」是为几十上百条记忆设计的；
    一个孩子的事实通常是个位数~十几条、每条只有 key/value，全量注入更可靠且 token 开销可忽略。
    """
    facts = list_child_facts(db, child_id)
    if not facts:
        return []

    # 事实很少：直接全量注入，不因关键词匹配不到而漏掉（如「水果」vs「苹果泥」）
    if len(facts) <= max_items:
        return facts

    qwords = _keywords(query)
    if not qwords:
        return facts[:max_items]

    scored = []
    for f in facts:
        haystack = f"{f.key or ''} {f.value or ''} {FACT_LABELS.get(f.category, '')}".lower()
        score = sum(1 for w in qwords if w in haystack)
        # 完整 key 命中 query 是强信号（如 key=鸡蛋，query 含「鸡蛋」）
        if f.key and f.key in (query or ""):
            score += 3
        if score > 0:
            scored.append((score, f))

    # 稳定排序：分数降序；同分保持「最近更新在前」的原有顺序
    scored.sort(key=lambda item: -item[0])
    picked = [f for _, f in scored[:max_items]]
    # 一个关键词都没命中时退回「最近更新的几条」，避免空召回
    return picked if picked else facts[:max_items]


def format_facts(facts: list[ChildFact]) -> str:
    """把召回的事实格式化成注入 Prompt 的纯文本（不含标题/注释，由调用方加）。"""
    if not facts:
        return ""
    lines = [
        f"- [{FACT_LABELS.get(f.category, f.category)}] {f.key}：{f.value}"
        for f in facts
    ]
    return "\n".join(lines)

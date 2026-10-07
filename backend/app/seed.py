"""知识库导入：
1. 《3岁以下婴幼儿健康养育照护指南（试行）》SFT 问答表（xlsx）
2. 知识库/ 下的补充 Markdown（医疗问诊、教育启蒙、营养喂养）
每行/每条转为一条 KnowledgeEntry。
"""
import os
import re

import openpyxl

from app.db import Base, SessionLocal, engine
from app.models.models import KnowledgeEntry

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
XLSX_PATH = os.path.join(PROJECT_ROOT, "知识库", "3岁以下婴幼儿健康养育照护指南_SFT.xlsx")

SOURCE_NAME = "《3岁以下婴幼儿健康养育照护指南（试行）》"

# 主题关键词（用于给每条知识打标签，辅助检索）
TOPIC_KEYWORDS = [
    "养育", "照护", "发育", "生长", "监测", "健康检查", "体格", "心理行为",
    "眼睛", "视力", "屏幕", "听力", "牙齿", "龋", "口腔",
    "营养", "喂养", "母乳", "辅食", "维生素D", "铁", "自主进食", "饮食", "进食",
    "亲子", "交流", "玩耍", "游戏", "运动", "社交",
    "睡眠", "入睡", "推拿", "衣着", "洗漱", "大小便", "环境",
    "伤害", "安全", "看护", "隐患", "紧急", "处置",
    "传染病", "贫血", "营养不良", "佝偻病", "高危儿", "就诊", "危险",
]


def category_for(index: int) -> str:
    """按问题序号归类（1-39，与指南章节对应）。"""
    if index <= 9:
        return "养育照护"
    if index <= 16:
        return "健康监测"
    if index <= 21:
        return "营养喂养"
    if index <= 25:
        return "亲子交流玩耍"
    if index <= 30:
        return "生活照护"
    if index <= 34:
        return "伤害预防"
    return "疾病预防与就诊"


def extract_tags(question: str) -> list[str]:
    return [k for k in TOPIC_KEYWORDS if k in question]


def load_qa_rows(path: str) -> list[tuple[str, str]]:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["SFT训练数据"]
    rows = list(ws.iter_rows(values_only=True))[1:]  # 跳过表头
    return [(str(r[2]).strip(), str(r[3]).strip()) for r in rows if r[2] and r[3]]


def build_entries() -> list[dict]:
    entries = []
    for i, (question, answer) in enumerate(load_qa_rows(XLSX_PATH), start=1):
        entries.append(
            dict(
                title=question.rstrip("？?"),
                category=category_for(i),
                applicable_age="0-3岁",
                content=answer,
                source=SOURCE_NAME,
                version="试行",
                evidence_level="官方指南",
                review_status="已采用",
                tags=",".join(extract_tags(question)),
            )
        )
    return entries


# 补充知识库 Markdown（文件名 → 分类）
KNOWLEDGE_MD_FILES = [
    ("知识库/知识库-医疗问诊.md", "医疗问诊"),
    ("知识库/知识库-教育启蒙.md", "教育启蒙"),
    ("知识库/知识库-营养喂养.md", "营养喂养"),
]


def _is_underline(s: str) -> bool:
    return bool(s) and set(s) <= set("=-")


def parse_md_entries(path: str) -> list[dict]:
    """解析知识库 Markdown：每个条目 = 标题 + 字段（核心内容/适用年龄/权威来源/证据等级/关键词）。"""
    lines = open(path, encoding="utf-8").read().splitlines()
    entries: list[dict] = []
    cur: dict | None = None
    mode: str | None = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or _is_underline(s):
            continue
        next_underline = i + 1 < len(lines) and _is_underline(lines[i + 1].strip())
        if s.startswith("#") or next_underline:
            if cur is not None:
                entries.append(cur)
            cur = {
                "title": s.lstrip("# ").strip(),
                "content": [],
                "applicable_age": "",
                "source": "",
                "evidence_level": "",
                "tags": "",
            }
            mode = None
            continue
        if cur is None:
            continue
        m = re.match(r"^(核心内容|适用年龄|权威来源|证据等级|关键词)[：:]\s*(.*)$", s)
        if m:
            mode = m.group(1)
            val = m.group(2).strip()
            if mode == "核心内容":
                if val:
                    cur["content"].append(val)
            elif mode == "适用年龄":
                cur["applicable_age"] = val
            elif mode == "权威来源":
                cur["source"] = val
            elif mode == "证据等级":
                cur["evidence_level"] = val
            elif mode == "关键词":
                cur["tags"] = val
        elif mode == "核心内容":
            cur["content"].append(s)
    if cur is not None:
        entries.append(cur)
    for e in entries:
        e["content"] = "\n".join(e["content"]).strip()
    return entries


def build_md_entries() -> list[dict]:
    entries = []
    for rel, category in KNOWLEDGE_MD_FILES:
        path = os.path.join(PROJECT_ROOT, rel)
        for e in parse_md_entries(path):
            if not e["content"]:
                continue
            entries.append(
                dict(
                    title=e["title"],
                    category=category,
                    applicable_age=e["applicable_age"] or "0-3岁",
                    content=e["content"],
                    source=e["source"] or "知识库补充资料",
                    version="",
                    evidence_level=e["evidence_level"] or "未标注",
                    review_status="已采用",
                    tags=e["tags"],
                )
            )
    return entries


def seed(db, replace: bool = True):
    """导入知识库。replace=True 时先清空旧知识再导入。"""
    if replace:
        db.query(KnowledgeEntry).delete()
        db.commit()
    xlsx_entries = build_entries()
    md_entries = build_md_entries()
    entries = xlsx_entries + md_entries
    for e in entries:
        db.add(KnowledgeEntry(**e))
    db.commit()
    print(f"知识库已导入 {len(entries)} 条（xlsx 指南 {len(xlsx_entries)} 条 + Markdown 补充 {len(md_entries)} 条）")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db, replace=True)
    finally:
        db.close()

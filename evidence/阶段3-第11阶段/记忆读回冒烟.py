"""真实模型冒烟：记忆「读回」——先记事实，再问相关问题，验证召回 + 注入。

隔离临时库，不污染真实数据；DEEPSEEK_API_KEY 从 backend/.env 读取真实 Key。
"""
import json
import os
import pathlib
import tempfile

_TMP = pathlib.Path(tempfile.mkdtemp())
os.environ["DB_PATH"] = str(_TMP / "smoke.db")
os.environ["ASSETS_DIR"] = str(_TMP / "assets")
os.environ["MEDICAL_ENABLED"] = "false"
os.environ["BAICHUAN_API_KEY"] = ""

from app.db import Base, SessionLocal, engine
from app.models.models import Child, ChildFact, Conversation, Family, Message
from app.services import agent_service, memory, qa_service


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    fam = Family(name="冒烟家庭")
    db.add(fam)
    db.commit()
    db.refresh(fam)
    child = Child(family_id=fam.id, nickname="小糯米", birth_date="2025-01-15")
    db.add(child)
    db.commit()
    db.refresh(child)

    # 1. 先记两条事实（真实 DeepSeek 规划 + 抽取）
    print("=" * 64)
    print("第一步：用一句话入口记住事实")
    for text in ["宝宝对鸡蛋过敏，帮我记一下", "宝宝特别喜欢听小恐龙的故事"]:
        r = agent_service.run_agent(db, child, text)
        print("输入：", text)
        print("  executed：", json.dumps(r["executed"], ensure_ascii=False))

    print("=" * 64)
    print("落库事实：")
    for f in db.query(ChildFact).filter(ChildFact.deleted_at.is_(None)).all():
        print(f"  [{f.category}] {f.key}：{f.value}（{f.source}）")

    # 2. 召回演示：问相关问题，看哪些事实被读回
    print("=" * 64)
    print("第二步：召回（read 侧）")
    for q in ["宝宝能吃鸡蛋吗", "宝宝晚上几点睡"]:
        got = memory.recall_facts(db, child.id, q)
        print("问题：", q)
        print("  召回：", memory.format_facts(got) or "（无）")

    # 3. 真实问答：验证事实注入后，答案能用到记忆
    print("=" * 64)
    print("第三步：真实问答（验证记忆注入到答案）")
    conv = Conversation(child_id=child.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    db.add(Message(conversation_id=conv.id, role="user", content="宝宝能吃鸡蛋吗"))
    db.commit()
    result = qa_service.answer_question(db, child, "宝宝能吃鸡蛋吗", conv)
    print("风险：", result["risk_level"])
    print("结论：", result["conclusion"])
    print("依据：", json.dumps(result["evidence"], ensure_ascii=False))

    db.close()


if __name__ == "__main__":
    main()

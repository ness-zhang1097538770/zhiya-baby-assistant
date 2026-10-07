"""真实模型冒烟：育儿管家（agent）规划 + 执行 + 记忆抽取（隔离临时库，不污染真实数据）。"""
import json
import os
import pathlib
import tempfile

_TMP = pathlib.Path(tempfile.mkdtemp())
os.environ["DB_PATH"] = str(_TMP / "smoke.db")
os.environ["ASSETS_DIR"] = str(_TMP / "assets")
# 不覆盖 DEEPSEEK_API_KEY，让它从 backend/.env 读取真实 Key

from app.db import Base, SessionLocal, engine
from app.models.models import Child, ChildFact, Event, Family, Reminder
from app.services import agent_service


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

    cases = [
        "宝宝对鸡蛋过敏，帮我记一下",
        "记下宝宝刚喝了150ml奶，再定个2小时后的喂奶提醒",
        "8个月的宝宝辅食该吃什么",
        "给宝宝讲个关于勇敢小恐龙的故事",
    ]
    for text in cases:
        r = agent_service.run_agent(db, child, text)
        print("=" * 64)
        print("输入   ：", text)
        print("intent ：", r["intent"])
        print("reply  ：", r["reply"])
        print("params ：", json.dumps(r["params"], ensure_ascii=False))
        print("executed：", json.dumps(r["executed"], ensure_ascii=False))
        print("pending ：", json.dumps(r["pending"], ensure_ascii=False))

    print("=" * 64)
    print("落库校验 -> 事件数：", db.query(Event).count(),
          "| 提醒数：", db.query(Reminder).count(),
          "| 记忆数：", db.query(ChildFact).count())
    for f in db.query(ChildFact).all():
        print("  记忆:", f.category, "|", f.key, "|", f.value, "|", f.source)
    for ev in db.query(Event).all():
        print("  事件:", ev.type, "|", ev.note)
    for rm in db.query(Reminder).all():
        print("  提醒:", rm.type, "|", rm.title, "|", rm.remind_at)
    db.close()


if __name__ == "__main__":
    main()

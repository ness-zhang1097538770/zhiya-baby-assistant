"""真实模型冒烟：Agent Loop —— 追问（need_info）+ 复查补全。

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
        "记一下",                                    # 预期：need_info 追问
        "设个提醒",                                   # 预期：need_info 追问
        "记下宝宝刚喝了150ml奶，再定个2小时后的喂奶提醒",  # 预期：两个动作都办
    ]
    for text in cases:
        r = agent_service.run_agent(db, child, text)
        print("=" * 64)
        print("输入：", text)
        print("intent：", r["intent"])
        if r["intent"] == "need_info":
            print("追问：", r["followup_question"])
        else:
            print("reply：", r["reply"])
            print("executed：", json.dumps(r["executed"], ensure_ascii=False))
            print("pending：", json.dumps(r["pending"], ensure_ascii=False))

    print("=" * 64)
    print("落库：事件", db.query(Event).count(), "| 提醒", db.query(Reminder).count(), "| 记忆", db.query(ChildFact).count())
    db.close()


if __name__ == "__main__":
    main()

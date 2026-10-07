"""测试夹具：临时 SQLite + 种子知识 + TestClient。"""
import json
import os
import pathlib
import tempfile

# 必须在导入 app 之前设置环境变量
_TMP = pathlib.Path(tempfile.mkdtemp())
os.environ["DB_PATH"] = str(_TMP / "test.db")
os.environ["ASSETS_DIR"] = str(_TMP / "story_assets")  # 隔离：测试资源不得写入真实 data/story_assets
os.environ["DEEPSEEK_API_KEY"] = "test-key"
os.environ["SILICONFLOW_API_KEY"] = ""  # 测试不触发真实 embedding 调用，检索自动降级
# 医疗通道默认关闭：测试里按需用 monkeypatch 显式开启，避免误走真实百川
os.environ["BAICHUAN_API_KEY"] = ""
os.environ["MEDICAL_ENABLED"] = "false"
os.environ["MEDICAL_ROLLOUT_PERCENT"] = "0"
os.environ["MEDICAL_WHITELIST_IDS"] = ""

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.models import Family, Session
from app.seed import seed


def parse_sse(response) -> list[tuple[str, dict]]:
    """把 SSE 响应解析成 (event, data) 列表。data 为 JSON 解析后的对象。"""
    events = []
    text = "".join(response.iter_text())
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = "message"
        data_str = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_str += line[len("data:"):].strip()
        data = json.loads(data_str) if data_str else None
        events.append((event, data))
    return events


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    seed(s)
    family = Family(name="测试家庭")
    s.add(family)
    s.commit()
    s.refresh(family)
    token = "test-token"
    s.add(Session(token=token, family_id=family.id))
    s.commit()
    s.close()
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    seed(s)
    yield s
    s.close()
    Base.metadata.drop_all(bind=engine)

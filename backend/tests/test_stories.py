import os

import pytest

from app.services import story_service
from app.services.llm import LLMError


def _fake_image(prompt, save_path):
    """假插画：字节数需满足封面最小大小校验（>=1KB）。"""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 2048)
    return save_path


def _fake_audio(text, save_path, gender="女孩"):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(b"ID3" + b"0" * 512)
    return save_path


def _mock_media(monkeypatch):
    monkeypatch.setattr("app.services.media.generate_image", _fake_image)
    monkeypatch.setattr("app.services.media.generate_audio", _fake_audio)


def _make_child(client):
    r = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2026-01-16"})
    return r.json()["id"]


def _fake_outline(messages, max_retries=2):
    return (
        {"title": "刷牙小英雄", "pages": [{"page_no": i, "outline": f"第{i}页场景"} for i in range(1, 11)]},
        None,
    )


def _fake_content(messages, max_retries=2):
    return (
        {
            "pages": [
                {
                    "page_no": i,
                    "text": f"第{i}页正文",
                    "narration": f"第{i}页朗读",
                    "image_prompt": f"第{i}页插画",
                }
                for i in range(1, 11)
            ]
        },
        None,
    )


def _fake_character(messages, max_retries=2):
    return (
        {
            "hero": {"name": "小糯米", "look": "戴着黄色小帽，圆脸", "personality": "勇敢、好奇"},
            "companions": [{"name": "小白兔", "look": "毛茸茸的白色兔子", "personality": "温柔、爱帮助人"}],
            "art_style": "温暖水彩童趣风",
        },
        None,
    )


def _create_to_character_ready(client, monkeypatch, child_id, **extra):
    """创建故事并走完角色 Agent 步骤，返回 story_id。"""
    monkeypatch.setattr("app.services.llm.chat_json", _fake_character)
    r = client.post(
        f"/api/v1/children/{child_id}/stories",
        json={"character_name": "小糯米", "theme": "刷牙", "age_range": "1-2岁", **extra},
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.get(f"/api/v1/stories/{sid}").json()["status"] == "character_ready"
    return sid


def _confirm_character_to_outline(client, monkeypatch, sid):
    """确认角色 → 生成大纲，返回大纲就绪状态。"""
    monkeypatch.setattr("app.services.llm.chat_json", _fake_outline)
    r = client.post(f"/api/v1/stories/{sid}/confirm-character", json={})
    assert r.status_code == 200
    assert client.get(f"/api/v1/stories/{sid}").json()["status"] == "outline_ready"





def test_create_story_flow(monkeypatch, client):
    """完整链路：角色 Agent → 确认角色 → 大纲 → 确认大纲 → 正文+插画。"""
    child_id = _make_child(client)
    sid = _create_to_character_ready(client, monkeypatch, child_id)

    r2 = client.get(f"/api/v1/stories/{sid}")
    assert r2.json()["character"]["hero"]["name"] == "小糯米"
    assert r2.json()["character"]["companions"][0]["name"] == "小白兔"

    _confirm_character_to_outline(client, monkeypatch, sid)
    r3 = client.get(f"/api/v1/stories/{sid}")
    assert r3.json()["title"] == "刷牙小英雄"
    assert len(r3.json()["outline"]["pages"]) == 10

    # 确认大纲 → 生成正文 → 自动接着生成插画（硬要求：每个故事必须有封面）
    monkeypatch.setattr("app.services.llm.chat_json", _fake_content)
    _mock_media(monkeypatch)
    r4 = client.post(f"/api/v1/stories/{sid}/confirm", json={})
    assert r4.status_code == 200

    r5 = client.get(f"/api/v1/stories/{sid}")
    assert r5.json()["status"] == "ready"
    assert len(r5.json()["pages"]["pages"]) == 10
    assert r5.json()["pages"]["pages"][0]["narration"]
    assert r5.json()["images"] and r5.json()["images"][0]["url"]


def test_confirm_with_edited_outline(monkeypatch, client):
    child_id = _make_child(client)
    sid = _create_to_character_ready(client, monkeypatch, child_id)
    _confirm_character_to_outline(client, monkeypatch, sid)

    edited = {"title": "改过的标题", "pages": [{"page_no": 1, "outline": "改过的第1页"}, {"page_no": 2, "outline": "第2页"}]}
    monkeypatch.setattr("app.services.llm.chat_json", _fake_content)
    _mock_media(monkeypatch)
    r = client.post(f"/api/v1/stories/{sid}/confirm", json={"outline": edited})
    assert r.status_code == 200
    r2 = client.get(f"/api/v1/stories/{sid}")
    assert r2.json()["title"] == "改过的标题"
    assert r2.json()["status"] == "ready"
    assert r2.json()["images"] and r2.json()["images"][0]["url"]


def test_story_failed_on_llm_error(monkeypatch, client):
    child_id = _make_child(client)

    def boom(messages, max_retries=2):
        raise LLMError("LLM_FAILED", "模型失败")

    monkeypatch.setattr("app.services.llm.chat_json", boom)
    sid = client.post(
        f"/api/v1/children/{child_id}/stories",
        json={"character_name": "小糯米", "theme": "刷牙", "age_range": "1-2岁"},
    ).json()["id"]
    r = client.get(f"/api/v1/stories/{sid}")
    assert r.json()["status"] == "failed"
    assert r.json()["error"]


def test_story_list_and_delete(monkeypatch, client):
    child_id = _make_child(client)
    monkeypatch.setattr("app.services.llm.chat_json", _fake_outline)
    sid = client.post(
        f"/api/v1/children/{child_id}/stories",
        json={"character_name": "小糯米", "theme": "刷牙", "age_range": "1-2岁"},
    ).json()["id"]
    client.get(f"/api/v1/stories/{sid}")
    assert len(client.get(f"/api/v1/children/{child_id}/stories").json()["items"]) == 1
    d = client.delete(f"/api/v1/stories/{sid}")
    assert d.status_code == 204
    assert len(client.get(f"/api/v1/children/{child_id}/stories").json()["items"]) == 0


def test_parse_outline_tolerant():
    data = {"title": "t", "pages": [{"page_no": "1", "outline": "x"}, {"outline": "y"}]}
    r = story_service._parse_outline(data)
    assert r["title"] == "t"
    assert len(r["pages"]) == 2
    assert r["pages"][1]["page_no"] == 2


def test_parse_outline_empty_raises():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        story_service._parse_outline({"title": "t", "pages": []})


def test_story_with_gender(monkeypatch, client):
    child_id = _make_child(client)

    def fake(messages, max_retries=2):
        return ({"title": "男孩故事", "pages": [{"page_no": 1, "outline": "x"}]}, None)

    monkeypatch.setattr("app.services.llm.chat_json", fake)
    r = client.post(
        f"/api/v1/children/{child_id}/stories",
        json={"character_name": "小虎", "gender": "男孩", "theme": "踢球", "age_range": "1-2岁"},
    )
    assert r.json()["gender"] == "男孩"
    r2 = client.get(f"/api/v1/stories/{r.json()['id']}")
    assert r2.json()["gender"] == "男孩"


def test_cancel_assets(monkeypatch, client):
    from app.db import SessionLocal
    from app.models.models import Story

    child_id = _make_child(client)
    sid = _create_to_character_ready(client, monkeypatch, child_id)
    _confirm_character_to_outline(client, monkeypatch, sid)
    monkeypatch.setattr("app.services.llm.chat_json", _fake_content)
    _mock_media(monkeypatch)
    client.post(f"/api/v1/stories/{sid}/confirm", json={})
    client.get(f"/api/v1/stories/{sid}")

    db = SessionLocal()
    st = db.get(Story, sid)
    st.cancel_requested = 1
    db.commit()
    db.close()

    def boom(prompt, save_path):
        raise AssertionError("取消后不应再生成插画")

    monkeypatch.setattr("app.services.media.generate_image", boom)
    story_service.generate_assets_task(sid)

    db = SessionLocal()
    st = db.get(Story, sid)
    assert st.status == "cancelled"
    db.close()


def test_generate_assets(monkeypatch, client):
    from app.db import SessionLocal
    from app.models.models import Story

    child_id = _make_child(client)
    sid = _create_to_character_ready(client, monkeypatch, child_id)
    _confirm_character_to_outline(client, monkeypatch, sid)
    monkeypatch.setattr("app.services.llm.chat_json", _fake_content)
    _mock_media(monkeypatch)
    client.post(f"/api/v1/stories/{sid}/confirm", json={})
    assert client.get(f"/api/v1/stories/{sid}").json()["status"] == "ready"

    # 退回 content_ready，验证"补生成插画"接口仍可用
    db = SessionLocal()
    st = db.get(Story, sid)
    st.status = "content_ready"
    db.commit()
    db.close()

    r = client.post(f"/api/v1/stories/{sid}/assets")
    assert r.status_code == 200
    r2 = client.get(f"/api/v1/stories/{sid}")
    assert r2.json()["status"] == "ready"
    assert len(r2.json()["images"]) == 10
    assert len(r2.json()["audio"]) == 10


def test_no_cover_never_ready(monkeypatch, client):
    """硬规则：封面图生成不出来，故事不得标记完成，必须失败且报错可见。"""

    def tiny_image(prompt, save_path):
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(b"PNG")  # 3 字节，明显不合格
        return save_path

    monkeypatch.setattr("app.services.story_service.COVER_RETRIES", 1)  # 跳过重试等待
    monkeypatch.setattr("app.services.media.generate_image", tiny_image)
    monkeypatch.setattr("app.services.media.generate_audio", _fake_audio)

    child_id = _make_child(client)
    sid = _create_to_character_ready(client, monkeypatch, child_id)
    _confirm_character_to_outline(client, monkeypatch, sid)
    monkeypatch.setattr("app.services.llm.chat_json", _fake_content)
    client.post(f"/api/v1/stories/{sid}/confirm", json={})

    r = client.get(f"/api/v1/stories/{sid}")
    assert r.json()["status"] == "failed"
    assert "封面" in (r.json()["error"] or "")


def test_upload_story_photo(monkeypatch, client):
    """上传孩子照片 → 转卡通角色形象图 → 返回相对路径（原照片不落盘）。"""
    def fake_char_img(photo_bytes, save_path, max_retries=3):
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 2048)
        return save_path

    monkeypatch.setattr("app.services.media.generate_character_image", fake_char_img)
    r = client.post(
        "/api/v1/stories/photo",
        files={"file": ("kid.png", b"\x89PNG\r\n\x1a\n" + b"0" * 512, "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["character_image"].startswith("/story_assets/characters/")


def test_create_story_with_character_image(monkeypatch, client):
    """带照片生成的角色形象图创建故事，角色 Agent 产出时保留 character_image。"""
    child_id = _make_child(client)
    sid = _create_to_character_ready(
        client, monkeypatch, child_id, character_image="/story_assets/characters/test.png"
    )
    r = client.get(f"/api/v1/stories/{sid}")
    assert r.json()["character_image"] == "/story_assets/characters/test.png"
    assert r.json()["character"]["hero"]["name"] == "小糯米"


def test_regenerate_character_image(monkeypatch, client):
    """character_ready 状态可重新生成角色形象图（覆盖 character_image）。"""
    child_id = _make_child(client)
    _mock_media(monkeypatch)
    sid = _create_to_character_ready(client, monkeypatch, child_id)
    r = client.post(
        f"/api/v1/stories/{sid}/regenerate-character-image",
        json={"look": "戴红色小帽，圆脸", "art_style": "水彩风"},
    )
    assert r.status_code == 200
    assert r.json()["character_image"]
    assert client.get(f"/api/v1/stories/{sid}").json()["character_image"]


def test_regenerate_character_image_wrong_status(monkeypatch, client):
    """非 character_ready 状态不可重新生成。"""
    child_id = _make_child(client)
    _mock_media(monkeypatch)
    sid = _create_to_character_ready(client, monkeypatch, child_id)
    _confirm_character_to_outline(client, monkeypatch, sid)  # 现为 outline_ready
    r = client.post(f"/api/v1/stories/{sid}/regenerate-character-image", json={})
    assert r.status_code == 400


def test_regenerate_outline(monkeypatch, client):
    """outline_ready 状态可重新生成大纲，后台任务完成后回到 outline_ready。"""
    child_id = _make_child(client)
    sid = _create_to_character_ready(client, monkeypatch, child_id)
    _confirm_character_to_outline(client, monkeypatch, sid)  # 现为 outline_ready，llm 已 mock
    r = client.post(f"/api/v1/stories/{sid}/regenerate-outline", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "outline_generating"
    assert client.get(f"/api/v1/stories/{sid}").json()["status"] == "outline_ready"


def test_regenerate_outline_wrong_status(monkeypatch, client):
    """非 outline_ready 状态不可重新生成大纲。"""
    child_id = _make_child(client)
    sid = _create_to_character_ready(client, monkeypatch, child_id)  # 现为 character_ready
    r = client.post(f"/api/v1/stories/{sid}/regenerate-outline", json={})
    assert r.status_code == 400

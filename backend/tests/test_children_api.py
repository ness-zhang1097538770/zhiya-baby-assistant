import os
import random
import struct
import zlib

from app.api.children import AVATARS_DIR


def _make_png(width: int, height: int, noise: bool = True) -> bytes:
    """生成一张真实 PNG 字节流（随机噪声保证体积超过 1KB），用于头像尺寸校验测试。"""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = struct.pack(">I", len(data)) + tag + data
        return body + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    rng = random.Random(42)
    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # filter type 0
        for _ in range(width * 3):
            raw.append(rng.randrange(256) if noise else 0)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 0))
        + chunk(b"IEND", b"")
    )


def test_create_and_list(client):
    r = client.post(
        "/api/v1/children",
        json={"nickname": "小糯米", "birth_date": "2025-01-15"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["nickname"] == "小糯米"
    assert data["birth_date"] == "2025-01-15"

    r2 = client.get("/api/v1/children")
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1


def test_invalid_date(client):
    r = client.post(
        "/api/v1/children",
        json={"nickname": "小糯米", "birth_date": "2025-13-99"},
    )
    assert r.status_code == 422
    assert "error" in r.json()


def test_missing_nickname(client):
    r = client.post(
        "/api/v1/children",
        json={"nickname": "", "birth_date": "2025-01-15"},
    )
    assert r.status_code == 422


def test_update_and_delete_child(client):
    child_id = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2025-01-15"}).json()["id"]
    r = client.put(f"/api/v1/children/{child_id}", json={"nickname": "小糯米改", "gender": "女孩"})
    assert r.status_code == 200
    assert r.json()["nickname"] == "小糯米改"
    assert r.json()["gender"] == "女孩"

    d = client.delete(f"/api/v1/children/{child_id}")
    assert d.status_code == 204
    # 软删后列表不含
    assert child_id not in [c["id"] for c in client.get("/api/v1/children").json()["items"]]


def test_avatar_upload_rejects_bad_type(client):
    child_id = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2025-01-15"}).json()["id"]
    r = client.post(
        f"/api/v1/children/{child_id}/avatar",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 422


def test_avatar_upload_rejects_tiny_blank_image(client):
    """部分浏览器会把文件替换成 1x1 空白图：必须报错，不能静默存进去。"""
    child_id = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2025-01-15"}).json()["id"]
    blank = _make_png(1, 1, noise=False)
    r = client.post(
        f"/api/v1/children/{child_id}/avatar",
        files={"file": ("blank.png", blank, "image/png")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "IMAGE_INVALID"
    # 未被写入数据库
    assert client.get("/api/v1/children").json()["items"][0].get("avatar") in (None, "")


def test_avatar_upload_rejects_too_small_image(client):
    """体积够但分辨率不足 64x64，同样拒绝。"""
    child_id = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2025-01-15"}).json()["id"]
    small = _make_png(48, 48)
    assert len(small) > 1024
    r = client.post(
        f"/api/v1/children/{child_id}/avatar",
        files={"file": ("small.png", small, "image/png")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "IMAGE_TOO_SMALL"


def test_avatar_upload_accepts_real_image(client):
    child_id = client.post("/api/v1/children", json={"nickname": "小糯米", "birth_date": "2025-01-15"}).json()["id"]
    real = _make_png(128, 128)
    r = client.post(
        f"/api/v1/children/{child_id}/avatar",
        files={"file": ("real.png", real, "image/png")},
    )
    assert r.status_code == 200, r.text
    avatar = r.json()["avatar"]
    assert avatar.startswith("/avatars/")
    saved = os.path.join(AVATARS_DIR, os.path.basename(avatar))
    assert os.path.exists(saved)
    os.remove(saved)  # 测试结束清理，避免污染本地数据目录

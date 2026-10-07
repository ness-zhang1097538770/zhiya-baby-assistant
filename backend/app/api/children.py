"""儿童档案接口（含头像上传、增删改查）。"""
import os
import re
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.core.errors import AppError
from app.db import get_db
from app.models.models import Child
from app.schemas.schemas import ChildCreate, ChildOut, ChildUpdate

router = APIRouter(prefix="/api/v1/children", tags=["children"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AVATARS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
_AVATAR_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/pjpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5MB
# 防御「静默失败」：部分浏览器/容器会把文件替换成 1x1 空白图，
# 上传仍显示成功，但页面只渲染出一个黑块。这里直接拒绝，而不是存进去。
_MIN_AVATAR_BYTES = 1024  # 1KB
_MIN_AVATAR_SIDE = 64  # 最短边至少 64px


def _image_size(content: bytes) -> tuple[int, int] | None:
    """零依赖解析图片真实宽高（PNG / JPEG / WebP）。解析不出就返回 None。"""
    # PNG：固定 8 字节签名 + IHDR 中的宽高（大端）
    if content[:8] == b"\x89PNG\r\n\x1a\n" and len(content) >= 24:
        return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")
    # JPEG：扫描 SOFn 段
    if content[:2] == b"\xff\xd8":
        i = 2
        n = len(content)
        while i + 9 < n:
            if content[i] != 0xFF:
                i += 1
                continue
            marker = content[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height = int.from_bytes(content[i + 5:i + 7], "big")
                width = int.from_bytes(content[i + 7:i + 9], "big")
                return width, height
            if marker == 0xD8 or marker == 0xD9 or 0xD0 <= marker <= 0xD7 or marker == 0x01:
                i += 2
                continue
            seg_len = int.from_bytes(content[i + 2:i + 4], "big")
            if seg_len <= 0:
                return None
            i += 2 + seg_len
        return None
    # WebP：RIFF....WEBP + 子块头
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        fourcc = content[12:16]
        if fourcc == b"VP8 " and len(content) >= 30:
            return (int.from_bytes(content[26:28], "little") & 0x3FFF,
                    int.from_bytes(content[28:30], "little") & 0x3FFF)
        if fourcc == b"VP8L" and len(content) >= 25:
            bits = int.from_bytes(content[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if fourcc == b"VP8X" and len(content) >= 30:
            return (int.from_bytes(content[24:27], "little") + 1,
                    int.from_bytes(content[27:30], "little") + 1)
    return None


def _validate_avatar_image(content: bytes) -> None:
    """校验图片是否真实可用，不合规直接抛错，避免静默写入空白图。"""
    if len(content) < _MIN_AVATAR_BYTES:
        raise AppError(
            "IMAGE_INVALID",
            f"图片文件只有 {len(content)} 字节，可能没有真正上传成功，请重新选择照片",
            422,
        )
    size = _image_size(content)
    if size is None:
        raise AppError("IMAGE_INVALID", "无法识别图片内容，请重新选择一张照片", 422)
    width, height = size
    if min(width, height) < _MIN_AVATAR_SIDE:
        raise AppError(
            "IMAGE_TOO_SMALL",
            f"图片尺寸过小（{width}×{height}），头像至少需要 {_MIN_AVATAR_SIDE}×{_MIN_AVATAR_SIDE} 像素",
            422,
        )


def _valid_date(s: str) -> bool:
    if not _DATE_RE.match(s):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


@router.post("", status_code=201, response_model=ChildOut)
def create_child(
    payload: ChildCreate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    if not _valid_date(payload.birth_date):
        raise AppError("INVALID_DATE", "出生日期格式应为 YYYY-MM-DD", 422)
    child = Child(
        family_id=family_id,
        nickname=payload.nickname.strip(),
        birth_date=payload.birth_date,
        gender=payload.gender,
        feeding_method=payload.feeding_method,
        allergy_history=payload.allergy_history,
        premature=payload.premature,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


@router.get("", response_model=dict)
def list_children(family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    items = (
        db.query(Child)
        .filter(Child.family_id == family_id, Child.deleted_at.is_(None))
        .order_by(Child.id.desc())
        .all()
    )
    return {"items": [ChildOut.model_validate(c).model_dump() for c in items]}


@router.put("/{child_id}", response_model=ChildOut)
def update_child(
    child_id: int,
    payload: ChildUpdate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    child = get_owned_child(db, child_id, family_id)
    if payload.birth_date is not None and not _valid_date(payload.birth_date):
        raise AppError("INVALID_DATE", "出生日期格式应为 YYYY-MM-DD", 422)
    if payload.nickname is not None:
        child.nickname = payload.nickname.strip()
    if payload.birth_date is not None:
        child.birth_date = payload.birth_date
    if payload.gender is not None:
        child.gender = payload.gender
    if payload.feeding_method is not None:
        child.feeding_method = payload.feeding_method
    if payload.allergy_history is not None:
        child.allergy_history = payload.allergy_history
    if payload.premature is not None:
        child.premature = payload.premature
    db.commit()
    db.refresh(child)
    return child


@router.delete("/{child_id}", status_code=204)
def delete_child(
    child_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    child = get_owned_child(db, child_id, family_id)
    child.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


@router.post("/{child_id}/avatar")
def upload_avatar(
    child_id: int,
    file: UploadFile = File(...),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    get_owned_child(db, child_id, family_id)
    content_type = file.content_type or ""
    ext = _AVATAR_TYPES.get(content_type)
    if ext is None:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_IMAGE", "message": "仅支持 JPG/PNG/WebP 图片"}})
    content = file.file.read()
    if len(content) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=422, detail={"error": {"code": "IMAGE_TOO_LARGE", "message": "图片不能超过 5MB"}})
    # 落盘前先确认这是一张真实可用的图片，而不是 1x1 空白图
    _validate_avatar_image(content)
    os.makedirs(AVATARS_DIR, exist_ok=True)
    filename = f"{child_id}_{uuid.uuid4().hex[:8]}.{ext}"
    with open(os.path.join(AVATARS_DIR, filename), "wb") as f:
        f.write(content)
    url = f"/avatars/{filename}"
    child = get_owned_child(db, child_id, family_id)
    child.avatar = url
    db.commit()
    return {"avatar": url}

"""故事工坊接口。"""
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.db import get_db
from app.models.models import Child, Story
from app.schemas.schemas import CharacterImageRegenerate, StoryCharacterConfirm, StoryConfirm, StoryCreate
from app.services import media, story_service, billing

router = APIRouter(prefix="/api/v1", tags=["stories"])

MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 孩子照片上限 10MB


def _story_to_dict(s: Story) -> dict:
    def load(txt):
        try:
            return json.loads(txt) if txt else None
        except json.JSONDecodeError:
            return None

    return {
        "id": s.id,
        "child_id": s.child_id,
        "title": s.title,
        "character_name": s.character_name,
        "character_tags": s.character_tags,
        "gender": s.gender or "女孩",
        "theme": s.theme,
        "age_range": s.age_range,
        "duration": s.duration,
        "education_goal": s.education_goal,
        "family_memory": s.family_memory,
        "status": s.status,
        "character": load(s.character_json),
        "character_image": s.character_image,
        "outline": load(s.outline_json),
        "pages": load(s.pages_json),
        "images": load(s.images_json),
        "audio": load(s.audio_json),
        "error": s.error,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _get_child(db: Session, child_id: int, family_id: int) -> Child:
    return get_owned_child(db, child_id, family_id)


def _get_owned_story(db: Session, story_id: int, family_id: int) -> Story:
    s = db.get(Story, story_id)
    if s is None or s.deleted_at is not None:
        raise HTTPException(status_code=404, detail={"error": {"code": "STORY_NOT_FOUND", "message": "故事不存在"}})
    child = db.get(Child, s.child_id)
    if child is None or child.family_id != family_id:
        raise HTTPException(status_code=404, detail={"error": {"code": "STORY_NOT_FOUND", "message": "故事不存在"}})
    return s


@router.post("/children/{child_id}/stories", status_code=201)
def create_story(
    child_id: int,
    payload: StoryCreate,
    background: BackgroundTasks,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    # 商业化：生成前校验绘本额度并扣减（额度不足返 402，杜绝白嫖插画）
    if not billing.consume_story_book(db, family_id):
        raise HTTPException(status_code=402, detail={"error": {"code": "STORY_QUOTA_EXCEEDED", "message": "本月绘本额度已用完，升级会员或加购绘本包后继续"}})
    s = Story(
        child_id=child_id,
        character_name=payload.character_name.strip(),
        character_tags=payload.character_tags,
        gender=payload.gender if payload.gender in ("男孩", "女孩") else "女孩",
        theme=payload.theme.strip(),
        age_range=payload.age_range,
        duration=payload.duration,
        education_goal=payload.education_goal,
        family_memory=payload.family_memory,
        character_image=payload.character_image,
        status="character_generating",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    background.add_task(story_service.generate_character_task, s.id)
    return _story_to_dict(s)


@router.get("/stories/{story_id}")
def get_story(story_id: int, family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    return _story_to_dict(_get_owned_story(db, story_id, family_id))


@router.post("/stories/photo")
def upload_story_photo(
    file: UploadFile = File(...),
    family_id: int = Depends(get_current_family_id),
):
    """上传孩子照片 → 转成绘本角色形象图 → 返回相对路径。

    隐私：原照片只在内存中处理、从不落盘，转完即丢弃；只保留卡通角色图。
    """
    content = file.file.read(MAX_PHOTO_BYTES + 1)
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail={"error": {"code": "PHOTO_TOO_LARGE", "message": "照片不能超过 10MB"}})
    if not content:
        raise HTTPException(status_code=400, detail={"error": {"code": "PHOTO_EMPTY", "message": "照片为空"}})
    save_path = os.path.join(media.ASSETS_DIR, "characters", f"{uuid.uuid4().hex}.png")
    try:
        abs_path = media.generate_character_image(content, save_path)
    except media.MediaError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": e.code, "message": e.message}})
    return {"character_image": media.rel_path(abs_path)}


@router.post("/stories/{story_id}/confirm-character")
def confirm_character(
    story_id: int,
    payload: StoryCharacterConfirm,
    background: BackgroundTasks,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    s = _get_owned_story(db, story_id, family_id)
    if s.status != "character_ready":
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_STATUS", "message": "当前状态不可确认角色"}})
    if payload.character is not None:
        s.character_json = json.dumps(payload.character, ensure_ascii=False)
    s.status = "outline_generating"
    s.error = None
    db.commit()
    db.refresh(s)
    background.add_task(story_service.generate_outline_task, s.id)
    return _story_to_dict(s)


@router.post("/stories/{story_id}/regenerate-character-image")
def regenerate_character_image(
    story_id: int,
    payload: CharacterImageRegenerate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """重新生成角色形象图（覆盖 character_image），用当前编辑的主角外貌/画风。"""
    s = _get_owned_story(db, story_id, family_id)
    if s.status != "character_ready":
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_STATUS", "message": "当前状态不可重新生成角色形象"}})
    try:
        story_service.regenerate_character_image(s, payload.look, payload.art_style)
    except media.MediaError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": e.code, "message": e.message}})
    db.commit()
    db.refresh(s)
    return _story_to_dict(s)


@router.post("/stories/{story_id}/regenerate-outline")
def regenerate_outline(
    story_id: int,
    background: BackgroundTasks,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """重新生成故事大纲（覆盖 outline_json），走后台任务 + 状态机，前端轮询刷新。"""
    s = _get_owned_story(db, story_id, family_id)
    if s.status != "outline_ready":
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_STATUS", "message": "当前状态不可重新生成大纲"}})
    s.status = "outline_generating"
    s.error = None
    db.commit()
    db.refresh(s)
    background.add_task(story_service.generate_outline_task, s.id)
    return _story_to_dict(s)


@router.post("/stories/{story_id}/confirm")
def confirm_story(
    story_id: int,
    payload: StoryConfirm,
    background: BackgroundTasks,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    s = _get_owned_story(db, story_id, family_id)
    if s.status != "outline_ready":
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_STATUS", "message": "当前状态不可确认大纲"}})
    if payload.outline is not None:
        # 用户可能编辑过大纲
        s.outline_json = json.dumps(payload.outline, ensure_ascii=False)
        title = payload.outline.get("title") if isinstance(payload.outline, dict) else None
        if title:
            s.title = title
    s.status = "content_generating"
    s.error = None
    db.commit()
    db.refresh(s)
    background.add_task(story_service.generate_content_task, s.id)
    return _story_to_dict(s)


@router.post("/stories/{story_id}/assets")
def generate_assets(
    story_id: int,
    background: BackgroundTasks,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    s = _get_owned_story(db, story_id, family_id)
    if s.status != "content_ready":
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_STATUS", "message": "当前状态不可生成插画/朗读"}})
    s.status = "assets_generating"
    s.error = None
    db.commit()
    db.refresh(s)
    background.add_task(story_service.generate_assets_task, s.id)
    return _story_to_dict(s)


@router.post("/stories/{story_id}/cancel")
def cancel_story(story_id: int, family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    s = _get_owned_story(db, story_id, family_id)
    if s.status in ("outline_generating", "content_generating", "assets_generating"):
        s.cancel_requested = 1
        db.commit()
    return _story_to_dict(s)


@router.get("/children/{child_id}/stories")
def list_stories(
    child_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    items = (
        db.query(Story)
        .filter(Story.child_id == child_id, Story.deleted_at.is_(None))
        .order_by(Story.id.desc())
        .all()
    )
    return {"items": [_story_to_dict(s) for s in items]}


@router.delete("/stories/{story_id}", status_code=204)
def delete_story(story_id: int, family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    s = _get_owned_story(db, story_id, family_id)
    s.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

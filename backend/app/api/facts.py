"""儿童记忆/事实接口：查看、编辑、删除（AI 抽取或手动记录的事实）。

对应 Q1 决策：AI 抽取的事实打 ai_extract 标记，家长可在档案里改/删。
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.db import get_db
from app.models.models import Child, ChildFact
from app.schemas.schemas import FactUpdate
from app.services.memory import FACT_LABELS, VALID_FACT_CATEGORIES

router = APIRouter(prefix="/api/v1", tags=["facts"])


def _fact_to_dict(f: ChildFact) -> dict:
    return {
        "id": f.id,
        "child_id": f.child_id,
        "category": f.category,
        "category_label": FACT_LABELS.get(f.category, f.category),
        "key": f.key,
        "value": f.value,
        "source": f.source,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


def _fact_owned(db: Session, f: ChildFact, family_id: int) -> bool:
    child = db.get(Child, f.child_id)
    return child is not None and child.family_id == family_id


@router.get("/children/{child_id}/facts")
def list_facts(
    child_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    get_owned_child(db, child_id, family_id)
    items = (
        db.query(ChildFact)
        .filter(ChildFact.child_id == child_id, ChildFact.deleted_at.is_(None))
        .order_by(ChildFact.updated_at.desc(), ChildFact.id.desc())
        .all()
    )
    return {"items": [_fact_to_dict(f) for f in items]}


@router.put("/facts/{fact_id}")
def update_fact(
    fact_id: int,
    payload: FactUpdate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    f = db.get(ChildFact, fact_id)
    if f is None or f.deleted_at is not None or not _fact_owned(db, f, family_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "FACT_NOT_FOUND", "message": "记忆不存在"}})
    if payload.category is not None:
        if payload.category not in VALID_FACT_CATEGORIES:
            raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_CATEGORY", "message": "记忆类别不合法"}})
        f.category = payload.category
    if payload.key is not None:
        key = payload.key.strip()
        if not key:
            raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_KEY", "message": "名称不能为空"}})
        f.key = key[:100]
    if payload.value is not None:
        value = payload.value.strip()
        if not value:
            raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_VALUE", "message": "内容不能为空"}})
        f.value = value[:500]
    db.commit()
    db.refresh(f)
    return _fact_to_dict(f)


@router.delete("/facts/{fact_id}", status_code=204)
def delete_fact(
    fact_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    f = db.get(ChildFact, fact_id)
    if f is None or f.deleted_at is not None or not _fact_owned(db, f, family_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "FACT_NOT_FOUND", "message": "记忆不存在"}})
    f.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

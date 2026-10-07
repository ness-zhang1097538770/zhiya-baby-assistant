"""成长事件记录 + 时间线接口。"""
import json
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.db import get_db
from app.models.models import Child, Event
from app.schemas.schemas import EVENT_TYPES, EventCreate, EventUpdate

router = APIRouter(prefix="/api/v1", tags=["events"])


def _event_to_dict(e: Event) -> dict:
    return {
        "id": e.id,
        "child_id": e.child_id,
        "type": e.type,
        "title": e.title,
        "note": e.note,
        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        "data": json.loads(e.data_json) if e.data_json else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _get_child(db: Session, child_id: int, family_id: int) -> Child:
    return get_owned_child(db, child_id, family_id)


def _event_owned(db: Session, e: Event, family_id: int) -> bool:
    child = db.get(Child, e.child_id)
    return child is not None and child.family_id == family_id


@router.post("/children/{child_id}/events", status_code=201)
def create_event(
    child_id: int,
    payload: EventCreate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    if payload.type not in EVENT_TYPES:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_TYPE", "message": "事件类型不合法"}})
    e = Event(
        child_id=child_id,
        type=payload.type,
        title=payload.title,
        note=payload.note,
        occurred_at=payload.occurred_at,
        data_json=json.dumps(payload.data, ensure_ascii=False) if payload.data else None,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _event_to_dict(e)


@router.get("/children/{child_id}/events")
def list_events(
    child_id: int,
    type: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    q = db.query(Event).filter(Event.child_id == child_id, Event.deleted_at.is_(None))
    if type:
        q = q.filter(Event.type == type)
    if date_from:
        q = q.filter(Event.occurred_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Event.occurred_at < datetime.combine(datetime.fromisoformat(date_to).date(), time.max))
    items = q.order_by(Event.occurred_at.desc(), Event.id.desc()).all()
    return {"items": [_event_to_dict(e) for e in items]}


@router.get("/children/{child_id}/timeline")
def timeline(
    child_id: int,
    type: str | None = Query(default=None),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    q = db.query(Event).filter(Event.child_id == child_id, Event.deleted_at.is_(None))
    if type:
        q = q.filter(Event.type == type)
    items = q.order_by(Event.occurred_at.desc(), Event.id.desc()).all()
    groups: list[dict] = []
    for e in items:
        d = e.occurred_at.date().isoformat() if e.occurred_at else ""
        if not groups or groups[-1]["date"] != d:
            groups.append({"date": d, "items": []})
        groups[-1]["items"].append(_event_to_dict(e))
    return {"groups": groups}


@router.put("/events/{event_id}")
def update_event(
    event_id: int,
    payload: EventUpdate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    e = db.get(Event, event_id)
    if e is None or e.deleted_at is not None or not _event_owned(db, e, family_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "EVENT_NOT_FOUND", "message": "记录不存在"}})
    if payload.title is not None:
        e.title = payload.title
    if payload.note is not None:
        e.note = payload.note
    if payload.occurred_at is not None:
        e.occurred_at = payload.occurred_at
    if payload.data is not None:
        e.data_json = json.dumps(payload.data, ensure_ascii=False)
    db.commit()
    db.refresh(e)
    return _event_to_dict(e)


@router.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    e = db.get(Event, event_id)
    if e is None or e.deleted_at is not None or not _event_owned(db, e, family_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "EVENT_NOT_FOUND", "message": "记录不存在"}})
    e.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

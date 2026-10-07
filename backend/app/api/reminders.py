"""提醒接口。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.db import get_db
from app.models.models import Child, Reminder
from app.schemas.schemas import REMINDER_TYPES, ReminderCreate, ReminderUpdate

router = APIRouter(prefix="/api/v1", tags=["reminders"])


def _reminder_to_dict(r: Reminder) -> dict:
    return {
        "id": r.id,
        "child_id": r.child_id,
        "type": r.type,
        "title": r.title,
        "note": r.note,
        "remind_at": r.remind_at.isoformat() if r.remind_at else None,
        "repeat": r.repeat,
        "enabled": bool(r.enabled),
        "notified_at": r.notified_at.isoformat() if r.notified_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _get_child(db: Session, child_id: int, family_id: int) -> Child:
    return get_owned_child(db, child_id, family_id)


def _reminder_owned(db: Session, r: Reminder, family_id: int) -> bool:
    child = db.get(Child, r.child_id)
    return child is not None and child.family_id == family_id


@router.post("/children/{child_id}/reminders", status_code=201)
def create_reminder(
    child_id: int,
    payload: ReminderCreate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    if payload.type not in REMINDER_TYPES:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_TYPE", "message": "提醒类型不合法"}})
    r = Reminder(
        child_id=child_id,
        type=payload.type,
        title=payload.title,
        note=payload.note,
        remind_at=payload.remind_at,
        repeat=payload.repeat if payload.repeat in ("one", "daily", "weekly") else "one",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _reminder_to_dict(r)


@router.get("/children/{child_id}/reminders")
def list_reminders(
    child_id: int,
    enabled: bool | None = Query(default=None),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    q = db.query(Reminder).filter(Reminder.child_id == child_id, Reminder.deleted_at.is_(None))
    if enabled is not None:
        q = q.filter(Reminder.enabled == (1 if enabled else 0))
    items = q.order_by(Reminder.remind_at.asc()).all()
    return {"items": [_reminder_to_dict(r) for r in items]}


@router.get("/children/{child_id}/reminders/upcoming")
def upcoming_reminders(
    child_id: int,
    days: int = Query(default=7, ge=1, le=365),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    _get_child(db, child_id, family_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    until = now + timedelta(days=days)
    items = (
        db.query(Reminder)
        .filter(
            Reminder.child_id == child_id,
            Reminder.deleted_at.is_(None),
            Reminder.enabled == 1,
            Reminder.remind_at >= now,
            Reminder.remind_at <= until,
        )
        .order_by(Reminder.remind_at.asc())
        .all()
    )
    return {"items": [_reminder_to_dict(r) for r in items]}


@router.put("/reminders/{reminder_id}")
def update_reminder(
    reminder_id: int,
    payload: ReminderUpdate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    r = db.get(Reminder, reminder_id)
    if r is None or r.deleted_at is not None or not _reminder_owned(db, r, family_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "REMINDER_NOT_FOUND", "message": "提醒不存在"}})
    if payload.title is not None:
        r.title = payload.title
    if payload.note is not None:
        r.note = payload.note
    if payload.remind_at is not None:
        r.remind_at = payload.remind_at
    if payload.enabled is not None:
        r.enabled = 1 if payload.enabled else 0
    db.commit()
    db.refresh(r)
    return _reminder_to_dict(r)


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(
    reminder_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    r = db.get(Reminder, reminder_id)
    if r is None or r.deleted_at is not None or not _reminder_owned(db, r, family_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "REMINDER_NOT_FOUND", "message": "提醒不存在"}})
    r.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

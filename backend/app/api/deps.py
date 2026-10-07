"""鉴权依赖：从 Authorization 头解析当前家庭。"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import Child, Session
from app.services import cost


def get_current_family_id(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> int:
    """解析 Bearer token → 家庭 id；未登录/失效抛 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "请先登录"}})
    token = authorization[len("Bearer "):].strip()
    session = db.query(Session).filter(Session.token == token).first()
    if session is None:
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "登录已失效，请重新登录"}})
    cost.set_family(session.family_id)
    return session.family_id


def get_owned_child(db: Session, child_id: int, family_id: int) -> Child:
    """校验孩子属于当前家庭，否则 404（不泄露其他家庭存在性）。"""
    child = db.get(Child, child_id)
    if child is None or child.family_id != family_id:
        raise HTTPException(status_code=404, detail={"error": {"code": "CHILD_NOT_FOUND", "message": "儿童档案不存在"}})
    return child

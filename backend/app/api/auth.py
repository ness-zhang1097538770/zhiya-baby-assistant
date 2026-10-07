"""邀请码登录接口。"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id
from app.db import get_db
from app.models.models import InviteCode, Session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    invite_code: str


def _new_token() -> str:
    return secrets.token_hex(32)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    code = (payload.invite_code or "").strip().upper()
    invite = db.query(InviteCode).filter(InviteCode.code == code).first()
    if invite is None:
        raise HTTPException(status_code=401, detail={"error": {"code": "INVALID_CODE", "message": "邀请码无效"}})
    token = _new_token()
    db.add(Session(token=token, family_id=invite.family_id))
    db.commit()
    return {"token": token, "family_id": invite.family_id}


@router.get("/me")
def me(family_id: int = Depends(get_current_family_id)):
    return {"family_id": family_id}


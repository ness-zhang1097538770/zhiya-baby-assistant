"""智慧陪伴智能体接口。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_family_id
from app.services import companion_service

router = APIRouter(prefix="/api/v1/companion", tags=["companion"])


class AnalyzeRequest(BaseModel):
    text: str


class GenerateRequest(BaseModel):
    mode: str
    child_nickname: str | None = None
    situation: str | None = None
    gender: str = "女孩"


@router.post("/analyze")
def analyze(payload: AnalyzeRequest, family_id: int = Depends(get_current_family_id)):
    return companion_service.analyze_emotion(payload.text)


@router.post("/generate")
def generate(payload: GenerateRequest, family_id: int = Depends(get_current_family_id)):
    return companion_service.generate_companion(
        payload.mode,
        payload.child_nickname,
        payload.situation,
        payload.gender,
    )

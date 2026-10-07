"""入口意图识别接口。只做理解与路由建议，不触发任何医疗/危险动作。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.db import get_db
from app.schemas.schemas import IntentRequest, IntentResult
from app.services import intent_service

router = APIRouter(prefix="/api/v1/intent", tags=["intent"])


@router.post("/classify", response_model=IntentResult)
def classify(
    payload: IntentRequest,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    # 校验儿童归属，确保请求来自本家庭
    get_owned_child(db, payload.child_id, family_id)
    return intent_service.classify_intent(payload.text)

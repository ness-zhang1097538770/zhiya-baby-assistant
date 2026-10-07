"""育儿管家接口：一句话入口 → 直接执行 + 记忆抽取（不触发任何未确认的危险/花钱动作）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.db import get_db
from app.schemas.schemas import AgentRequest, AgentResult
from app.services import agent_service

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.post("/run", response_model=AgentResult)
def run(
    payload: AgentRequest,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    # 校验儿童归属，确保只操作本家庭的档案
    child = get_owned_child(db, payload.child_id, family_id)
    return agent_service.run_agent(db, child, payload.text)

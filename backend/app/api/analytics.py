"""埋点与指标接口（商业化 C-3 批次）。

- POST /api/v1/analytics/events：产品行为埋点上报（登录态带 family_id，匿名维度带 device_id）。
- GET /api/v1/metrics/cost：单家庭月度模型成本 + 成本红线告警（指标看板雏形）。
"""
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id
from app.db import get_db
from app.models.models import AnalyticsEvent
from app.schemas.schemas import AnalyticsEventRequest
from app.services import cost

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.post("/analytics/events")
def track_event(
    payload: AnalyticsEventRequest,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """产品行为埋点：event 为行为名，props 为关键字段（前端自定）。"""
    db.add(AnalyticsEvent(
        family_id=family_id,
        device_id=payload.device_id,
        event=payload.event,
        props_json=json.dumps(payload.props, ensure_ascii=False) if payload.props else None,
    ))
    db.commit()
    return {"ok": True}


@router.get("/metrics/cost")
def family_cost(
    month: str | None = Query(None, max_length=7),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """单家庭月度模型成本与告警状态（指标看板雏形）。"""
    return {
        "month": month,
        "total_cost_cny": cost.monthly_cost(db, family_id, month),
        "threshold_cny": cost.COST_ALERT_THRESHOLD,
        "alert": cost.check_cost_alert(db, family_id),
    }

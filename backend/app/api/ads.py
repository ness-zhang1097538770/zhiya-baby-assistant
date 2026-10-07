"""广告接口：硬屏蔽 + 取广告 + 事件上报（商业化 C-2 批次，不上真实投放）。

硬屏蔽规则（前端隐藏不算权限，后端再挡一道）：
- 风险回答页（risk_level ∈ L1/L2/L3）零广告
- 医疗会话（medical=true）零广告
- 会员全站零广告（在 ad_service 内按 is_member 短路）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id
from app.core.errors import AppError
from app.db import get_db
from app.schemas.schemas import AdEventRequest
from app.services import ad_service, billing

router = APIRouter(prefix="/api/v1/ads", tags=["ads"])

RISK_SHIELD = {"L1", "L2", "L3"}


@router.get("")
def get_ads(
    page: str = Query(..., max_length=30),
    age_bucket: str = Query("", max_length=10),
    consent: bool = Query(False),
    risk_level: str | None = Query(None, max_length=20),
    medical: bool = Query(False),
    device_id: str | None = Query(None, max_length=64),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """取广告。风险/医疗会话直接返回空（硬屏蔽）。"""
    if risk_level in RISK_SHIELD or medical:
        return {"ads": []}
    is_member = billing.effective_plan(db, family_id) != "free"
    ads = ad_service.get_ads(
        db, page=page, age_bucket=age_bucket, consent=consent,
        device_id=device_id, is_member=is_member,
    )
    return {"ads": ads}


@router.post("/events")
def log_event(payload: AdEventRequest, db: Session = Depends(get_db)):
    """广告事件上报（曝光/点击/关闭/投诉）。匿名设备维度，无需登录。"""
    try:
        entry = ad_service.log_event(
            db,
            device_id=payload.device_id,
            slot=payload.slot,
            action=payload.action,
            ad_id=payload.ad_id,
            age_bucket=payload.age_bucket,
        )
    except AppError as e:
        raise HTTPException(status_code=e.status, detail={"error": {"code": e.code, "message": e.message}})
    return {"id": entry.id}

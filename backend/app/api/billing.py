"""会员订阅与绘本额度接口（商业化 C-1 批次）。

- 内测/灰度期不接真实支付：订阅用白名单开通或兑换码；加购同样不真实扣款。
- 额度在故事创建前校验（见 stories.py），额度不足返回 402。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id
from app.core.errors import AppError
from app.db import get_db
from app.schemas.schemas import PurchaseRequest, RedeemRequest, SubscribeRequest
from app.services import billing

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _credit_dict(c):
    return {
        "id": c.id,
        "kind": c.kind,
        "total": c.total,
        "used": c.used,
        "period": c.period,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
    }


@router.get("/entitlements")
def entitlements(family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    return billing.get_entitlements(db, family_id)


@router.post("/subscribe")
def subscribe(
    payload: SubscribeRequest,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """白名单/测试开通订阅（不接真实支付）。"""
    try:
        sub = billing.subscribe(db, family_id, payload.source)
    except AppError as e:
        raise HTTPException(status_code=e.status, detail={"error": {"code": e.code, "message": e.message}})
    return {"plan": sub.plan, "status": sub.status, "source": sub.source,
            "period_end": sub.period_end.isoformat() if sub.period_end else None}


@router.post("/redeem")
def redeem(
    payload: RedeemRequest,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """兑换码开通（内测 ¥99 首年的落地方式）。"""
    try:
        sub = billing.redeem(db, family_id, payload.code)
    except AppError as e:
        raise HTTPException(status_code=e.status, detail={"error": {"code": e.code, "message": e.message}})
    return {"plan": sub.plan, "status": sub.status, "source": sub.source,
            "period_end": sub.period_end.isoformat() if sub.period_end else None}


@router.post("/purchase")
def purchase(
    payload: PurchaseRequest,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """单次加购（绘本包）。"""
    try:
        credit = billing.purchase(db, family_id, payload.sku)
    except AppError as e:
        raise HTTPException(status_code=e.status, detail={"error": {"code": e.code, "message": e.message}})
    return _credit_dict(credit)


@router.post("/cancel-renew")
def cancel_renew(family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    """取消自动续费（到期前仍享权益）。"""
    try:
        sub = billing.cancel_renew(db, family_id)
    except AppError as e:
        raise HTTPException(status_code=e.status, detail={"error": {"code": e.code, "message": e.message}})
    return {"plan": sub.plan, "status": sub.status, "auto_renew": bool(sub.auto_renew)}

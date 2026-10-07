"""广告服务：与生成链路物理隔离，只按 {page, age_bucket, consent} 取广告。

铁律三（不污染答案）的工程保证：
1. 本服务拿不到 child_id、对话内容、健康记录，只拿粗粒度年龄分桶 + 同意开关 + 匿名设备 ID。
2. 频控按匿名设备 ID，日志不关联 child_id。
3. 会员全站无广告；风险/医疗屏蔽在 API 层先行（见 api/ads.py）。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.models import Ad, AdLog, naive_now

FREE_DAILY_AD_CAP = 2       # 免费用户日曝光上限（条）
ADVERTISER_DAILY_CAP = 2    # 同广告主日曝光上限（次）

SLOTS = {"shelf", "profile", "home", "cocreate"}
AGE_BUCKETS = {"0-1", "1-3", ""}
ACTIONS = {"impression", "click", "close", "report"}


def _today_start():
    now = naive_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_ads(
    db: Session,
    page: str,
    age_bucket: str,
    consent: bool,
    device_id: Optional[str] = None,
    is_member: bool = False,
    daily_cap: int = FREE_DAILY_AD_CAP,
) -> list[dict]:
    """取当前广告位应展示的广告（未命中返回空列表）。"""
    if not consent:
        return []
    if is_member:
        return []
    if page not in SLOTS:
        return []
    if age_bucket not in AGE_BUCKETS:
        return []

    today_start = _today_start()
    # 频控：匿名设备日曝光上限
    if device_id:
        impressions_today = (
            db.query(AdLog)
            .filter(
                AdLog.device_id == device_id,
                AdLog.action == "impression",
                AdLog.created_at >= today_start,
            )
            .count()
        )
        if impressions_today >= daily_cap:
            return []

    q = db.query(Ad).filter(Ad.active == 1, Ad.slot == page)
    if age_bucket:
        q = q.filter(
            (Ad.target_age_bucket == age_bucket)
            | (Ad.target_age_bucket == "")
            | (Ad.target_age_bucket.is_(None))
        )
    ads = q.order_by(Ad.id).all()

    result: list[dict] = []
    for ad in ads:
        # 同广告主日频控
        if device_id:
            adv_today = (
                db.query(AdLog)
                .filter(
                    AdLog.device_id == device_id,
                    AdLog.ad_id == ad.id,
                    AdLog.action == "impression",
                    AdLog.created_at >= today_start,
                )
                .count()
            )
            if adv_today >= ADVERTISER_DAILY_CAP:
                continue
        result.append({
            "ad_id": ad.id,
            "advertiser": ad.advertiser,
            "title": ad.title,
            "slot": ad.slot,
            "age_bucket": ad.target_age_bucket,
            "image_url": ad.image_url,
            "landing_url": ad.landing_url,
        })
    return result


def log_event(
    db: Session,
    device_id: str,
    slot: str,
    action: str,
    ad_id: Optional[int] = None,
    age_bucket: Optional[str] = None,
) -> AdLog:
    """记录广告事件（曝光/点击/关闭/投诉），匿名设备维度，不关联 child_id。"""
    if action not in ACTIONS:
        raise AppError("INVALID_ACTION", "无效的广告事件类型")
    if slot not in SLOTS:
        raise AppError("INVALID_SLOT", "无效的广告位")
    if age_bucket is not None and age_bucket not in AGE_BUCKETS:
        raise AppError("INVALID_AGE_BUCKET", "无效的年龄分桶")
    entry = AdLog(
        device_id=device_id,
        ad_id=ad_id,
        slot=slot,
        age_bucket=age_bucket,
        action=action,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

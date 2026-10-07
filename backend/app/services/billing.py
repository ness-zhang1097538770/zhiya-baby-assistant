"""会员订阅与绘本额度：权益配置、兑换码开通、额度校验/扣减。

设计要点（对应《商业化落地设计-V1》第 2、4 节）：
1. 订阅挂在 Family 层级（邀请码登录 → Session → Family 即付费与家庭协作单元）。
2. 权益表是单一来源常量 PLANS，前端不硬编码。
3. 额度在「生成前校验、成功后扣减」（事务内），杜绝白嫖插画。
4. 内测/灰度期只支持兑换码/白名单开通，不接真实支付（支付后置）。
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.models import RedeemCode, StoryCredit, Subscription, naive_now

REDEEM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆字符

# ===== 权益配置（单一来源，前端不硬编码）=====
# 免费版：问答日限 30；绘本新赠 3 本此后 1 本/月；记录/提醒无限；书架 20 本；记忆 3 个月
PLANS = {
    "free": {
        "qa_daily_limit": 30,
        "story_monthly_grant": 1,
        "story_new_bonus": 3,
        "bookshelf_limit": 20,
        "memory_months": 3,
        "ai_insight": False,
        "multi_child": False,
        "long_answer": False,
        "ads": True,
    },
    "yearly": {
        "qa_daily_limit": 100,
        "story_monthly_grant": 30,
        "story_new_bonus": 0,
        "bookshelf_limit": None,   # 无限
        "memory_months": None,     # 全量
        "ai_insight": True,
        "multi_child": True,
        "long_answer": True,
        "ads": False,
    },
    "monthly": {
        "qa_daily_limit": 100,
        "story_monthly_grant": 30,
        "story_new_bonus": 0,
        "bookshelf_limit": None,
        "memory_months": None,
        "ai_insight": True,
        "multi_child": True,
        "long_answer": True,
        "ads": False,
    },
}

# 价格来源（source → 计划 + 时长），内测期仅作白名单/兑换码开通，不真实扣款
PRICE = {
    "promo_99": {"plan": "yearly", "price_cny": 99, "period_days": 365},
    "yearly_198": {"plan": "yearly", "price_cny": 198, "period_days": 365},
    "monthly_28": {"plan": "monthly", "price_cny": 28, "period_days": 30},
}

# 加购 SKU
PURCHASES = {
    "pack_5": {"kind": "story_books", "books": 5, "days": 30, "price_cny": 9.9},
    "pack_20": {"kind": "story_books", "books": 20, "days": 90, "price_cny": 29.9},
    "report_1": {"kind": "report", "books": 0, "days": 30, "price_cny": 6.9},
}


def _now() -> datetime:
    return naive_now()


def _month_key(dt: Optional[datetime] = None) -> str:
    d = dt or _now()
    return d.strftime("%Y-%m")


def _gen_code() -> str:
    return "".join(secrets.choice(REDEEM_ALPHABET) for _ in range(10))


# ===== 订阅查询 =====

def get_subscription(db: Session, family_id: int) -> Optional[Subscription]:
    return db.query(Subscription).filter(Subscription.family_id == family_id).first()


def effective_plan(db: Session, family_id: int) -> str:
    """返回当前有效计划名（考虑过期）。到期自动置 expired 并回落到 free。"""
    sub = get_subscription(db, family_id)
    if sub is None:
        return "free"
    if sub.status != "active":
        return "free"
    if sub.period_end is not None and sub.period_end < _now():
        sub.status = "expired"
        db.commit()
        return "free"
    return sub.plan


def _grant_monthly(db: Session, family_id: int, plan: str, month: str) -> None:
    """当账期不存在月额度时按计划发放；升级时补足当月额度（只增不减）。"""
    target = PLANS[plan]["story_monthly_grant"]
    row = (
        db.query(StoryCredit)
        .filter(
            StoryCredit.family_id == family_id,
            StoryCredit.kind == "monthly_grant",
            StoryCredit.period == month,
        )
        .first()
    )
    if row is None:
        db.add(StoryCredit(
            family_id=family_id,
            kind="monthly_grant",
            total=target,
            used=0,
            period=month,
        ))
    elif row.total < target:
        # 升级（free→yearly/monthly）后补足当月额度
        row.total = target


def _grant_bonus(db: Session, family_id: int, plan: str) -> None:
    """新用户赠本（仅 free 计划一次性）。"""
    bonus = PLANS[plan]["story_new_bonus"]
    if bonus <= 0:
        return
    exists = (
        db.query(StoryCredit)
        .filter(StoryCredit.family_id == family_id, StoryCredit.kind == "free_bonus")
        .first()
    )
    if exists is None:
        db.add(StoryCredit(
            family_id=family_id,
            kind="free_bonus",
            total=bonus,
            used=0,
            period="once",
        ))


def ensure_grants(db: Session, family_id: int) -> None:
    """幂等发放当前应得的额度（赠本 + 当月额度）。"""
    plan = effective_plan(db, family_id)
    _grant_bonus(db, family_id, plan)
    _grant_monthly(db, family_id, plan, _month_key())
    db.commit()


def available_story_books(db: Session, family_id: int) -> int:
    """当前可用绘本本数（未过期、未用完的额度之和）。"""
    ensure_grants(db, family_id)
    now = _now()
    rows = (
        db.query(StoryCredit)
        .filter(
            StoryCredit.family_id == family_id,
            (StoryCredit.expires_at.is_(None)) | (StoryCredit.expires_at > now),
            StoryCredit.used < StoryCredit.total,
        )
        .all()
    )
    return sum(r.total - r.used for r in rows)


def consume_story_book(db: Session, family_id: int) -> bool:
    """扣 1 本额度。优先扣「先到期的」，再按创建顺序。返回是否扣减成功。"""
    ensure_grants(db, family_id)
    now = _now()
    row = (
        db.query(StoryCredit)
        .filter(
            StoryCredit.family_id == family_id,
            (StoryCredit.expires_at.is_(None)) | (StoryCredit.expires_at > now),
            StoryCredit.used < StoryCredit.total,
        )
        .order_by(
            StoryCredit.expires_at.is_(None),  # False(0) 在前 = 先到期的先扣
            StoryCredit.expires_at,
            StoryCredit.id,
        )
        .first()
    )
    if row is None:
        return False
    row.used += 1
    db.commit()
    return True


# ===== 开通 / 兑换 / 加购 =====

def _activate(db: Session, family_id: int, source: str) -> Subscription:
    if source not in PRICE:
        raise AppError("INVALID_SOURCE", "无效的订阅来源")
    spec = PRICE[source]
    sub = get_subscription(db, family_id)
    start = _now()
    if sub is None:
        sub = Subscription(family_id=family_id)
        db.add(sub)
    sub.plan = spec["plan"]
    sub.status = "active"
    sub.source = source
    sub.auto_renew = 1 if source == "monthly_28" else 0
    sub.period_start = start
    sub.period_end = start + timedelta(days=spec["period_days"])
    db.commit()
    db.refresh(sub)
    return sub


def subscribe(db: Session, family_id: int, source: str) -> Subscription:
    """白名单/测试开通（不接真实支付）。"""
    return _activate(db, family_id, source)


def redeem(db: Session, family_id: int, code: str) -> Subscription:
    """兑换码开通：一码一用，用后绑定家庭。"""
    rc = db.query(RedeemCode).filter(RedeemCode.code == code.strip().upper()).first()
    if rc is None:
        raise AppError("INVALID_CODE", "兑换码无效")
    if rc.used_by is not None:
        raise AppError("CODE_USED", "兑换码已被使用")
    rc.used_by = family_id
    rc.used_at = _now()
    sub = _activate(db, family_id, rc.source)
    return sub


def purchase(db: Session, family_id: int, sku: str) -> StoryCredit:
    """单次加购：绘本包（pack_5/pack_20）。月报 report_1 尚未实现。"""
    if sku not in PURCHASES:
        raise AppError("INVALID_SKU", "无效的加购项")
    spec = PURCHASES[sku]
    if spec["kind"] != "story_books":
        raise AppError("SKU_NOT_READY", "该加购项暂未开放")
    credit = StoryCredit(
        family_id=family_id,
        kind="addon_pack",
        total=spec["books"],
        used=0,
        expires_at=_now() + timedelta(days=spec["days"]),
    )
    db.add(credit)
    db.commit()
    db.refresh(credit)
    return credit


def cancel_renew(db: Session, family_id: int) -> Subscription:
    """取消自动续费（到期前仍享权益）。"""
    sub = get_subscription(db, family_id)
    if sub is None:
        raise AppError("NO_SUBSCRIPTION", "当前无订阅")
    sub.auto_renew = 0
    db.commit()
    db.refresh(sub)
    return sub


def generate_redeem_codes(db: Session, count: int, source: str = "promo_99") -> list[str]:
    """生成兑换码（用于内测 ¥99 首年分发）。"""
    if source not in PRICE:
        raise AppError("INVALID_SOURCE", "无效的订阅来源")
    codes: list[str] = []
    for _ in range(count):
        code = _gen_code()
        db.add(RedeemCode(code=code, source=source))
        codes.append(code)
    db.commit()
    return codes


# ===== 权益查询 =====

def get_entitlements(db: Session, family_id: int) -> dict:
    plan = effective_plan(db, family_id)
    conf = PLANS[plan]
    sub = get_subscription(db, family_id)
    return {
        "plan": plan,
        "status": sub.status if sub else "free",
        "source": sub.source if sub else "none",
        "period_end": sub.period_end.isoformat() if (sub and sub.period_end) else None,
        "auto_renew": bool(sub.auto_renew) if sub else False,
        "story_books_available": available_story_books(db, family_id),
        "entitlements": {
            "qa_daily_limit": conf["qa_daily_limit"],
            "story_monthly_grant": conf["story_monthly_grant"],
            "bookshelf_limit": conf["bookshelf_limit"],
            "memory_months": conf["memory_months"],
            "ai_insight": conf["ai_insight"],
            "multi_child": conf["multi_child"],
            "long_answer": conf["long_answer"],
            "ads": conf["ads"],
        },
    }

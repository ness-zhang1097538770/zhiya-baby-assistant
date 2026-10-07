"""模型成本埋点：单家庭月度成本聚合 + 成本红线告警（商业化 C-3 批次）。

设计要点（对应商业化落地设计第 4、5 节）：
1. 每次模型/媒体调用记录一条 CostLog；family_id 归属通过 contextvar 传递
   （在 deps 与 story_service 后台任务中设置）。
2. 价格表为量级假设，待实测核定（用真实账单反算：近 30 天消耗 / 调用次数）。
3. 成本红线：单家庭月度模型成本 > 会员 ARPU 30%（≈¥5）触发告警。
"""
import contextvars

from app.db import SessionLocal
from app.models.models import CostLog, naive_now

# 当前请求/后台任务归属的家庭（deps.get_current_family_id 与 story_service 中设置）
_current_family: contextvars.ContextVar = contextvars.ContextVar("cost_family", default=None)

# 成本红线：会员年卡折合月均 ARPU 16.5 元 × 30% ≈ ¥5（待实测后核定）
MEMBER_ARPU = 16.5
COST_ALERT_RATIO = 0.30
COST_ALERT_THRESHOLD = round(MEMBER_ARPU * COST_ALERT_RATIO, 2)

# 单位价格（元）：量级假设，待实测核定
PRICE = {
    "deepseek-flash": {"unit": "1k_tokens", "price": 0.001},
    "Baichuan-M3-Plus": {"unit": "1k_tokens", "price": 0.02},
    "Kwai-Kolors/Kolors": {"unit": "image", "price": 0.12},
    "Qwen/Qwen-Image-Edit": {"unit": "image", "price": 0.15},
    "FunAudioLLM/CosyVoice2-0.5B": {"unit": "audio", "price": 0.01},
}


def set_family(family_id) -> None:
    _current_family.set(family_id)


def get_family():
    return _current_family.get()


def record(model: str, action: str, tokens: int | None = None, count: int = 1,
           family_id: int | None = None) -> None:
    """记录一条成本。action: chat / image / tts。归属优先用显式 family_id，其次 contextvar。"""
    fid = family_id if family_id is not None else _current_family.get()
    spec = PRICE.get(model, {})
    price = spec.get("price", 0.0)
    if action == "chat":
        cost_cny = (tokens or 0) / 1000.0 * price
    else:
        cost_cny = (count or 0) * price
    db = SessionLocal()
    try:
        db.add(CostLog(
            family_id=fid, model=model, action=action,
            tokens=tokens, cost_cny=round(cost_cny, 6),
        ))
        db.commit()
    finally:
        db.close()


def monthly_cost(db, family_id: int, month: str | None = None) -> float:
    """单家庭某月模型总成本（默认当月）。"""
    key = month or naive_now().strftime("%Y-%m")
    rows = db.query(CostLog).filter(CostLog.family_id == family_id).all()
    return round(sum(r.cost_cny for r in rows
                     if r.created_at and r.created_at.strftime("%Y-%m") == key), 4)


def check_cost_alert(db, family_id: int) -> bool:
    """成本红线告警：单家庭月度模型成本 > 阈值。"""
    return monthly_cost(db, family_id) > COST_ALERT_THRESHOLD

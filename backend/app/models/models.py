"""数据库模型。"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.db import Base


def now():
    return datetime.now(timezone.utc)


def naive_now():
    """无时区 UTC 时间：SQLite DateTime 列统一用 naive 存，避免比对时的时区不一致。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Family(Base):
    __tablename__ = "families"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), default="我的家庭")
    created_at = Column(DateTime, default=now)


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), unique=True, index=True, nullable=False)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    created_at = Column(DateTime, default=now)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    created_at = Column(DateTime, default=now)


class Child(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True)
    nickname = Column(String(50), nullable=False)
    birth_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    gender = Column(String(10), nullable=True)
    feeding_method = Column(String(20), nullable=True)
    allergy_history = Column(Text, nullable=True)
    premature = Column(String(10), nullable=True)
    avatar = Column(String(200), nullable=True)  # 头像图片 URL
    deleted_at = Column(DateTime, nullable=True)  # 软删除
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    messages = relationship(
        "Message", back_populates="conversation", order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(10), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    risk_level = Column(String(20), nullable=True)
    sources_json = Column(Text, nullable=True)
    followup_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)

    conversation = relationship("Conversation", back_populates="messages")


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    applicable_age = Column(String(50), nullable=True)
    content = Column(Text, nullable=False)
    source = Column(String(200), nullable=False)
    version = Column(String(50), nullable=True)
    evidence_level = Column(String(50), nullable=True)
    review_status = Column(String(50), default="待医学审核")
    tags = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=now)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    type = Column(String(20), nullable=False)  # feeding/sleep/diaper/growth/milestone/custom
    title = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False)
    data_json = Column(Text, nullable=True)  # 结构化字段（喂养量/睡眠时长/身高体重等）
    deleted_at = Column(DateTime, nullable=True)  # 软删除
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    type = Column(String(20), nullable=False)  # vaccine/feeding/routine/custom
    title = Column(String(100), nullable=False)
    note = Column(Text, nullable=True)
    remind_at = Column(DateTime, nullable=False)
    repeat = Column(String(20), default="one")  # MVP 先 one
    enabled = Column(Integer, default=1)  # 0/1
    notified_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # 软删除
    created_at = Column(DateTime, default=now)


class ChildFact(Base):
    """儿童记忆/事实表：从对话抽取的结构化事实（过敏/偏好/里程碑等）。"""
    __tablename__ = "child_facts"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    category = Column(String(20), nullable=False)  # allergy/preference/milestone/medical/habit/note
    key = Column(String(100), nullable=False)
    value = Column(String(500), nullable=False)
    source = Column(String(20), default="ai_extract")  # ai_extract / manual
    deleted_at = Column(DateTime, nullable=True)  # 软删除
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    title = Column(String(200), nullable=True)
    character_name = Column(String(50), nullable=False)
    character_tags = Column(String(200), nullable=True)
    gender = Column(String(10), default="女孩")  # 男孩 / 女孩
    theme = Column(String(100), nullable=False)
    age_range = Column(String(50), nullable=False)
    duration = Column(String(50), nullable=True)
    education_goal = Column(String(200), nullable=True)
    family_memory = Column(Text, nullable=True)
    status = Column(String(30), default="character_generating")  # character_generating/character_ready/outline_generating/outline_ready/content_generating/content_ready/assets_generating/ready/failed/cancelled
    character_json = Column(Text, nullable=True)  # 角色 Agent 产出：主角/配角/画风设定
    character_image = Column(String(500), nullable=True)  # 照片转出的角色形象图（相对路径，原照片已删）
    outline_json = Column(Text, nullable=True)
    pages_json = Column(Text, nullable=True)
    images_json = Column(Text, nullable=True)
    audio_json = Column(Text, nullable=True)
    cancel_requested = Column(Integer, default=0)  # 1 = 用户请求停止
    error = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Subscription(Base):
    """会员订阅：挂在 Family 层级（邀请码登录 → Session → Family 即付费与家庭协作单元）。"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), unique=True, nullable=False)
    plan = Column(String(20), default="free")       # free / monthly / yearly / trial
    status = Column(String(20), default="active")   # active / expired / cancelled
    source = Column(String(20), default="none")     # none / promo_99 / yearly_198 / monthly_28
    auto_renew = Column(Integer, default=0)         # 0/1（仅连续包月=1）
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=naive_now)
    updated_at = Column(DateTime, default=naive_now, onupdate=naive_now)


class StoryCredit(Base):
    """绘本额度台账：月额度随账期重置、加购包带有效期、新用户赠本一次性。"""
    __tablename__ = "story_credits"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)       # free_bonus / monthly_grant / addon_pack
    total = Column(Integer, default=0)              # 本包总额度（本）
    used = Column(Integer, default=0)               # 已用（本）
    period = Column(String(20), nullable=True)      # 月额度账期 "YYYY-MM"；free_bonus 固定 "once"
    expires_at = Column(DateTime, nullable=True)    # 加购包过期时间；月额度/赠本为空
    created_at = Column(DateTime, default=naive_now)


class RedeemCode(Base):
    """会员兑换码：内测/灰度期不接真实支付的开通方式（对应商业化落地设计第 2.4 节）。"""
    __tablename__ = "redeem_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), unique=True, index=True, nullable=False)
    source = Column(String(20), default="promo_99")  # 对应 PRICE key
    used_by = Column(Integer, ForeignKey("families.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=naive_now)


class Ad(Base):
    """广告素材目录：C-2 只建框架不接真实投放，默认 active=0（留白）。"""
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    advertiser = Column(String(100), nullable=False)
    title = Column(String(200), nullable=True)
    slot = Column(String(30), nullable=False)          # shelf / profile / home / cocreate
    target_age_bucket = Column(String(10), nullable=True)  # "0-1" / "1-3" / ""（全部）
    image_url = Column(String(500), nullable=True)
    landing_url = Column(String(500), nullable=True)
    active = Column(Integer, default=0)                # 0/1，默认不上线
    created_at = Column(DateTime, default=naive_now)


class AdLog(Base):
    """广告日志：按匿名设备 ID 记录，不得与 child_id / family_id 关联（合规证据 + 频控 + A/B）。"""
    __tablename__ = "ad_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), nullable=False, index=True)  # 匿名设备 ID（前端 localStorage 生成）
    ad_id = Column(Integer, nullable=True)
    slot = Column(String(30), nullable=False)
    age_bucket = Column(String(10), nullable=True)
    action = Column(String(20), nullable=False)        # impression / click / close / report
    created_at = Column(DateTime, default=naive_now)


class CostLog(Base):
    """模型/媒体成本日志：按家庭归属，用于单家庭月度成本聚合与成本红线告警。"""
    __tablename__ = "cost_logs"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True, index=True)
    model = Column(String(80), nullable=False)
    action = Column(String(20), nullable=False)        # chat / image / tts
    tokens = Column(Integer, nullable=True)
    cost_cny = Column(Float, default=0.0)
    created_at = Column(DateTime, default=naive_now)


class AnalyticsEvent(Base):
    """产品行为埋点：登录态带 family_id，匿名设备维度带 device_id，用于北极星/留存等指标。"""
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    event = Column(String(50), nullable=False)
    props_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=naive_now)

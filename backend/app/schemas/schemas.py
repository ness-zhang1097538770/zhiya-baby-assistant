"""Pydantic 请求/响应结构。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

EVENT_TYPES = {"feeding", "sleep", "diaper", "growth", "milestone", "custom"}
REMINDER_TYPES = {"vaccine", "feeding", "routine", "custom"}


class ChildCreate(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=50)
    birth_date: str = Field(..., min_length=8, max_length=10)  # YYYY-MM-DD
    gender: Optional[str] = None
    feeding_method: Optional[str] = None
    allergy_history: Optional[str] = None
    premature: Optional[str] = None


class ChildUpdate(BaseModel):
    nickname: Optional[str] = Field(None, min_length=1, max_length=50)
    birth_date: Optional[str] = Field(None, min_length=8, max_length=10)
    gender: Optional[str] = None
    feeding_method: Optional[str] = None
    allergy_history: Optional[str] = None
    premature: Optional[str] = None


class ChildOut(BaseModel):
    id: int
    nickname: str
    birth_date: str
    gender: Optional[str] = None
    feeding_method: Optional[str] = None
    allergy_history: Optional[str] = None
    premature: Optional[str] = None
    avatar: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QARequest(BaseModel):
    child_id: int
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[int] = None


class EventCreate(BaseModel):
    type: str
    title: Optional[str] = None
    note: Optional[str] = None
    occurred_at: datetime
    data: Optional[Dict[str, Any]] = None


class EventUpdate(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None
    occurred_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None


class EventOut(BaseModel):
    id: int
    child_id: int
    type: str
    title: Optional[str] = None
    note: Optional[str] = None
    occurred_at: datetime
    data: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReminderCreate(BaseModel):
    type: str
    title: str = Field(..., min_length=1, max_length=100)
    note: Optional[str] = None
    remind_at: datetime
    repeat: str = "one"


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None
    remind_at: Optional[datetime] = None
    enabled: Optional[bool] = None


class ReminderOut(BaseModel):
    id: int
    child_id: int
    type: str
    title: str
    note: Optional[str] = None
    remind_at: datetime
    repeat: str
    enabled: bool
    notified_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StoryCreate(BaseModel):
    character_name: str = Field(..., min_length=1, max_length=50)
    character_tags: Optional[str] = None
    gender: Optional[str] = "女孩"  # 男孩 / 女孩
    theme: str = Field(..., min_length=1, max_length=100)
    age_range: str = Field(..., min_length=1, max_length=50)
    duration: Optional[str] = None
    education_goal: Optional[str] = None
    family_memory: Optional[str] = None
    character_image: Optional[str] = None  # 照片转出的角色形象图相对路径（可选，原照片已删）


class StoryCharacterConfirm(BaseModel):
    character: Optional[Dict[str, Any]] = None  # 可带编辑后的角色设定


class CharacterImageRegenerate(BaseModel):
    """重新生成角色形象图：可带当前编辑的主角外貌/画风（为空时回退用已存角色设定）。"""

    look: Optional[str] = Field(None, max_length=500)
    art_style: Optional[str] = Field(None, max_length=200)


class StoryConfirm(BaseModel):
    outline: Optional[Dict[str, Any]] = None  # 可带编辑后的大纲


class OutlinePage(BaseModel):
    page_no: int
    outline: str


class Outline(BaseModel):
    title: str = ""
    pages: List[OutlinePage] = []


class ContentPage(BaseModel):
    page_no: int
    text: str = ""
    narration: str = ""
    image_prompt: str = ""


class StoryContent(BaseModel):
    pages: List[ContentPage] = []


class Source(BaseModel):
    id: int
    title: str
    source: str
    version: Optional[str] = None
    review_status: str = "待医学审核"


class QAResult(BaseModel):
    """模型结构化输出（经宽容解析 + 强校验）。"""

    risk_level: str = "L4"  # L3 / L4 / NEED_MORE_INFO
    conclusion: str = ""
    actions: List[str] = []
    evidence: List[str] = []
    red_flags: List[str] = []
    disclaimer: str = ""
    followup_question: Optional[str] = None
    source_ids: List[int] = []  # 模型引用的知识条目 ID，由服务层映射为 Source

    @property
    def answer_text(self) -> str:
        """用于流式展示的完整文本。"""
        parts = []
        if self.conclusion:
            parts.append(f"【结论】{self.conclusion}")
        if self.actions:
            parts.append("【可以这么做】\n" + "\n".join(f"· {a}" for a in self.actions))
        if self.evidence:
            parts.append("【依据】\n" + "\n".join(f"· {e}" for e in self.evidence))
        if self.red_flags:
            parts.append("【出现这些情况请尽快就医】\n" + "\n".join(f"· {r}" for r in self.red_flags))
        if self.disclaimer:
            parts.append(f"【免责声明】{self.disclaimer}")
        return "\n\n".join(parts)


class IntentRequest(BaseModel):
    """入口意图识别请求。只做理解与路由，不触发任何医疗/危险动作。"""

    text: str = Field(..., min_length=1, max_length=200)
    child_id: int


class IntentResult(BaseModel):
    """意图识别结果。intent 决定前端路由，params 为抽取的槽位。"""

    intent: str  # ask / record / reminder / story / unknown
    params: Dict[str, Any] = {}


class AgentRequest(BaseModel):
    """育儿管家请求：一句话入口，理解 + 直接执行 + 记忆抽取。"""

    text: str = Field(..., min_length=1, max_length=200)
    child_id: int


class AgentExecutedItem(BaseModel):
    tool: str
    summary: str


class AgentPendingItem(BaseModel):
    tool: str
    summary: str
    params: Dict[str, Any] = {}


class AgentResult(BaseModel):
    """育儿管家结果。intent：ask/action/need_info/unknown；executed 为已执行动作，pending 为待确认动作。
    followup_question：intent=need_info 时的追问。"""

    intent: str
    reply: str = ""
    followup_question: Optional[str] = None
    params: Dict[str, Any] = {}
    executed: List[AgentExecutedItem] = []
    pending: List[AgentPendingItem] = []


class FactUpdate(BaseModel):
    """记忆/事实编辑请求（可改可不改的字段，None 表示不改）。"""

    category: Optional[str] = Field(None, max_length=20)
    key: Optional[str] = Field(None, min_length=1, max_length=100)
    value: Optional[str] = Field(None, min_length=1, max_length=500)


class SubscribeRequest(BaseModel):
    source: str = Field(..., max_length=20)  # promo_99 / yearly_198 / monthly_28


class RedeemRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)


class PurchaseRequest(BaseModel):
    sku: str = Field(..., max_length=20)  # pack_5 / pack_20 / report_1


class AdEventRequest(BaseModel):
    """广告事件上报：匿名设备维度，不关联 child_id。"""

    device_id: str = Field(..., min_length=8, max_length=64)
    ad_id: Optional[int] = None
    slot: str = Field(..., max_length=30)
    age_bucket: Optional[str] = None
    action: str = Field(..., max_length=20)  # impression / click / close / report


class AnalyticsEventRequest(BaseModel):
    """产品行为埋点上报：登录态带 family_id（后端从 token 取），匿名维度带 device_id。"""

    device_id: str = Field(..., min_length=8, max_length=64)
    event: str = Field(..., min_length=1, max_length=50)
    props: Optional[Dict[str, Any]] = None


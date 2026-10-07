"""L1-L4 风险分级（确定性规则，安全兜底，不交给模型自主决定）。"""
from typing import Optional

# L1 危急：单个关键词命中即判 L1（这些情况须立即急救/急诊）
L1_KEYWORDS = [
    "窒息", "意识丧失", "昏迷", "紫绀", "发绀", "青紫", "抽搐", "惊厥",
    "无呼吸", "停止呼吸", "呼吸暂停", "没有呼吸", "大出血", "严重外伤", "休克",
]

# L2 紧急：单独关键词命中即判 L2
L2_KEYWORDS = [
    "持续呕吐", "反复呕吐", "血便", "便血", "脱水", "呼吸困难", "囟门凹陷",
    "少尿", "无尿", "精神萎靡", "意识模糊",
]

# L2 组合：高热 + 精神状态差等
L2_COMBO_HIGH_FEVER = ["高热", "高烧", "烧到39", "烧到40"]
L2_COMBO_BAD_STATE = ["精神差", "萎靡", "嗜睡", "没精神", "反应差"]


def classify_urgent(question: str) -> Optional[str]:
    """返回 "L1" / "L2"，非紧急返回 None（交模型进一步分级 L3/L4）。"""
    q = question or ""
    for kw in L1_KEYWORDS:
        if kw in q:
            return "L1"
    for kw in L2_KEYWORDS:
        if kw in q:
            return "L2"
    has_fever = any(kw in q for kw in L2_COMBO_HIGH_FEVER)
    has_bad = any(kw in q for kw in L2_COMBO_BAD_STATE)
    if has_fever and has_bad:
        return "L2"
    return None


L1_RESPONSE = {
    "risk_level": "L1",
    "conclusion": "这是可能危及生命的情况，请立即采取急救措施并拨打 120。",
    "actions": [
        "立即拨打 120 或前往最近的急诊",
        "让孩子保持呼吸道通畅，呕吐时侧卧、防止误吸",
        "不要喂水、喂食物或药物",
        "保持冷静，持续观察孩子的呼吸和意识",
    ],
    "evidence": ["此为危急情况的安全处置提示，不构成医疗诊断。"],
    "red_flags": ["呼吸停止或明显困难", "意识不清、叫不醒", "皮肤青紫", "持续抽搐"],
    "disclaimer": "本提示不能替代专业急救和医疗，请立即就医。",
}

L2_RESPONSE = {
    "risk_level": "L2",
    "conclusion": "孩子的情况需要尽快就医，请立即前往医院或急诊。",
    "actions": [
        "尽快就医（急诊）",
        "途中密切观察孩子的呼吸、精神状况",
        "不要自行用药或采取未经证实的方法",
    ],
    "evidence": ["此为紧急情况的就医提示，不构成医疗诊断。"],
    "red_flags": ["出现意识改变", "呼吸困难或皮肤青紫", "抽搐", "精神越来越差"],
    "disclaimer": "本提示不能替代专业医疗，请尽快就医。",
}

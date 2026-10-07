"""知识库检索：语义匹配（向量）+ 模糊匹配（字符 n-gram）+ 领域词表打分。

- 语义：SiliconFlow embedding（bge-m3）余弦相似度；无 Key / 调用失败自动降级。
- 模糊：字符 bigram 重合度（Dice），容忍语序差异与部分错别字。
- 领域词表/同义词：确定性兜底，保证无网络也能检索。
"""
import hashlib
import json
import math
import os
import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import KnowledgeEntry

# 同义词扩展：用户口语问法 → 领域词
SYNONYMS = {
    "饮食": ["辅食", "喂养", "吃饭", "营养", "食物", "进食"],
    "辅食": ["饮食", "喂养", "吃饭", "进食"],
    "吃什么": ["辅食", "饮食", "喂养", "食物", "进食"],
    "吃饭": ["辅食", "饮食", "喂养", "进食"],
    "喂": ["喂养", "辅食", "进食", "母乳"],
    "营养": ["饮食", "辅食", "喂养"],
    "发烧": ["发热", "退烧", "体温"],
    "发热": ["发烧", "退烧", "体温"],
    "退烧": ["发热", "发烧"],
    "拉肚子": ["腹泻", "排便", "大便"],
    "便便": ["腹泻", "排便", "大便"],
    "大便": ["腹泻", "排便"],
    "睡觉": ["睡眠", "入睡", "哄睡"],
    "夜醒": ["睡眠", "入睡", "哄睡"],
    "哄睡": ["睡眠", "入睡"],
    "睡不好": ["睡眠", "入睡"],
    "打疫苗": ["疫苗", "接种", "预防针"],
    "预防针": ["疫苗", "接种"],
    "接种": ["疫苗"],
    "长高": ["身高", "体重", "生长", "体格"],
    "不长个": ["身高", "体重", "发育", "生长"],
    "长牙": ["牙齿", "口腔", "龋"],
    "看屏幕": ["眼睛", "视力", "屏幕"],
    "看手机": ["眼睛", "视力", "屏幕"],
    "红疹": ["皮疹", "湿疹"],
    "出疹": ["皮疹", "湿疹"],
    "皮肤": ["湿疹", "皮疹"],
    "湿疹": ["皮疹"],
    "说话": ["语言", "讲话", "沟通"],
    "讲话": ["语言", "说话", "沟通"],
    "开口说话": ["语言", "讲话"],
    "幼儿园": ["入园", "分离焦虑"],
    "入园": ["幼儿园", "分离焦虑", "适应"],
    "不肯去": ["入园", "分离焦虑"],
    "退烧药": ["退热药", "布洛芬", "对乙酰氨基酚"],
    "退热药": ["退烧药", "布洛芬", "对乙酰氨基酚"],
    "转奶": ["配方奶", "奶粉"],
    "奶粉": ["配方奶", "转奶", "冲泡"],
    "过敏": ["花生", "鸡蛋", "湿疹", "皮疹"],
    "麻疹": ["急疹", "幼儿急疹", "出疹", "皮疹"],
    "急疹": ["幼儿急疹", "出疹", "皮疹"],
    "拉稀": ["腹泻", "大便", "补液", "脱水"],
    "脱水": ["补液", "腹泻"],
    "规矩": ["规则", "管教", "正面管教"],
    "立规矩": ["规则", "管教", "正面管教"],
    "不听话": ["管教", "规则"],
    "规则意识": ["规则", "管教"],
}

# 领域词表：命中即作为检索词
VOCAB = [
    "养育", "照护", "发育", "生长", "里程碑", "全面发展", "自主", "自我调节", "回应", "需求",
    "监测", "健康检查", "体检", "体格", "身高", "体重", "心理行为",
    "眼睛", "视力", "屏幕", "听力", "牙齿", "龋", "口腔", "检查",
    "营养", "喂养", "母乳", "辅食", "维生素D", "维生素", "铁", "贫血",
    "自主进食", "饮食", "进食", "吃饭", "挑食", "奶",
    "亲子", "交流", "玩耍", "游戏", "运动", "社交", "陪伴", "互动",
    "睡眠", "入睡", "睡觉", "夜醒", "哄睡", "推拿", "衣着", "穿衣",
    "洗漱", "洗澡", "大小便", "排便", "换尿布", "环境", "居家",
    "伤害", "安全", "看护", "隐患", "紧急", "处置", "急救", "跌倒", "烫伤", "异物",
    "发热", "发烧", "退烧", "腹泻", "拉肚子", "便秘", "皮疹", "湿疹", "咳嗽", "感冒",
    "传染病", "营养不良", "佝偻病", "高危儿", "就诊", "危险", "疫苗", "接种", "预防针",
    "退热药", "退烧药", "布洛芬", "对乙酰氨基酚", "补液", "脱水", "麻疹", "急疹", "幼儿急疹",
    "呼吸道", "鼻塞", "流涕", "蜂蜜", "三凹征", "呼吸急促", "抗生素",
    "语言", "说话", "讲话", "沟通", "词汇", "入园", "幼儿园", "分离焦虑", "管教", "规则", "叛逆",
    "阅读", "绘本", "共读", "感官", "视觉", "抓握", "地板时间", "客体",
    "转奶", "配方奶", "奶粉", "冲泡", "挺舌反射", "铁强化", "米粉", "肉泥", "过敏", "花生", "鸡蛋", "坚果",
]

# 打分权重与阈值
FUZZY_WEIGHT = 4.0       # 模糊匹配
SEMANTIC_WEIGHT = 6.0    # 语义匹配
SEMANTIC_MIN_SIM = 0.45  # 语义相似度下限，低于此视为不相关


def _question_terms(question: str) -> tuple[set, set]:
    """提取问题关键词，返回 (直接词, 同义词扩展词)。"""
    q = question or ""
    direct = set()
    expanded = set()
    for v in VOCAB:
        if v in q:
            direct.add(v)
    for k, vs in SYNONYMS.items():
        if k in q:
            direct.add(k)
            for v in vs:
                (direct if v in q else expanded).add(v)
    direct.update(re.findall(r"[a-z0-9]+", q.lower()))
    return direct, expanded


def _bigrams(text: str) -> set:
    """中文按相邻字符切 bigram；英文/数字归一到小写。"""
    t = re.sub(r"\s+", "", (text or "").lower())
    return {t[i : i + 2] for i in range(len(t) - 1)}


def _fuzzy_score(question: str, entry: KnowledgeEntry) -> float:
    """字符 bigram Dice 重合度（0..1），容忍语序差异与部分错别字。"""
    q = _bigrams(question)
    field = _bigrams(f"{entry.title} {entry.tags or ''} {entry.category} {entry.content[:300]}")
    if not q or not field:
        return 0.0
    inter = len(q & field)
    return 2.0 * inter / (len(q) + len(field))


# ===== 语义匹配（Embedding + 余弦相似度） =====
_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "embedding_cache.json")
_cache: Optional[dict] = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def _save_cache() -> None:
    global _cache
    if _cache is None:
        return
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except Exception:
        pass


def _entry_key(e: KnowledgeEntry) -> str:
    return hashlib.md5(f"{e.id}:{e.title}:{e.content}".encode("utf-8")).hexdigest()


def _entry_text(e: KnowledgeEntry) -> str:
    return f"{e.title}\n{e.content}"


def _embed(texts: list[str]) -> Optional[list]:
    from app.services import embeddings
    return embeddings.embed_texts(texts)


def _entry_vectors(entries: list) -> Optional[list]:
    """返回与 entries 对齐的向量列表；语义不可用返回 None。"""
    cache = _load_cache()
    vectors: list = [None] * len(entries)
    to_embed_texts: list[str] = []
    to_embed_idx: list[int] = []
    for i, e in enumerate(entries):
        key = _entry_key(e)
        cached = cache.get(str(e.id))
        if isinstance(cached, dict) and cached.get("key") == key and cached.get("vec"):
            vectors[i] = cached["vec"]
        else:
            to_embed_texts.append(_entry_text(e))
            to_embed_idx.append(i)
    if to_embed_texts:
        emb = _embed(to_embed_texts)
        if emb is None or len(emb) != len(to_embed_texts):
            return None
        for i, vec in zip(to_embed_idx, emb):
            vectors[i] = vec
            cache[str(entries[i].id)] = {"key": _entry_key(entries[i]), "vec": vec}
        _save_cache()
    if all(v is not None for v in vectors):
        return vectors
    return None


def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(db: Session, question: str, top_k: int = 3) -> List[KnowledgeEntry]:
    entries = db.query(KnowledgeEntry).all()
    if not entries:
        return []
    direct, expanded = _question_terms(question)

    # 语义相似度（不可用则为 None，自动降级为关键词 + 模糊）
    semantic_sims: Optional[list] = None
    vectors = _entry_vectors(entries)
    if vectors is not None:
        q_emb = _embed([question])
        if q_emb and q_emb[0]:
            semantic_sims = [_cosine(q_emb[0], v) for v in vectors]

    scored = []
    for i, e in enumerate(entries):
        field = f"{e.title} {e.tags or ''} {e.category} {e.applicable_age or ''} {e.content[:400]}"
        score = 0.0
        # 1. 关键词/同义词
        for t in direct:
            if len(t) >= 2 and t in field:
                score += 3
        for t in expanded:
            if len(t) >= 2 and t in field:
                score += 1
        if e.title:
            if any(t in e.title for t in direct if len(t) >= 2):
                score += 3
            elif any(t in e.title for t in expanded if len(t) >= 2):
                score += 1
        # 2. 模糊匹配
        score += _fuzzy_score(question, e) * FUZZY_WEIGHT
        # 3. 语义匹配
        if semantic_sims is not None and semantic_sims[i] >= SEMANTIC_MIN_SIM:
            score += semantic_sims[i] * SEMANTIC_WEIGHT
        scored.append((score, e))

    scored.sort(key=lambda x: (-x[0], x[1].id))
    # 只返回有命中的条目；无命中返回空列表（由模型走“谨慎回答/建议就医”分支）
    return [e for s, e in scored if s > 0][:top_k]

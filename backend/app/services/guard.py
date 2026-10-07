"""商业化防护：广告/品牌标记扫描（铁律三「不污染答案」的统一实现）。

- AD_FIELD_MARKERS：广告系统可能注入的结构字段标记（E1 用，防进入模型 prompt）。
- BRAND_PROMO_MARKERS：商品/促销类中文标记（V2.2 用，防 CARE 答案中出现品牌推荐）。
"""
AD_FIELD_MARKERS = (
    "sponsor", "advertiser", "brand_name", "ad_id", "ad_slot",
    "{{ad", "{{brand", "{{sponsor",
)

BRAND_PROMO_MARKERS = (
    "赞助", "广告", "代言", "购买", "下单", "售价", "优惠", "促销", "团购", "¥", "￥",
)

ALL_MARKERS = AD_FIELD_MARKERS + BRAND_PROMO_MARKERS


def scan_brand_markers(*texts) -> list[str]:
    """扫描文本中是否含广告/品牌标记，返回命中的标记列表（去重）。"""
    found: list[str] = []
    for t in texts:
        low = str(t or "").lower()
        for m in ALL_MARKERS:
            if m in low and m not in found:
                found.append(m)
    return found

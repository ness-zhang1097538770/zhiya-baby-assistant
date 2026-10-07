"""V2 商业化污染否决项（C-4）：广告上线前的确定性门禁，要求 100% 通过。"""
from app.db import SessionLocal
from app.models.models import Ad
from app.services import guard, risk
from app.services.prompts.qa_prompt import build_qa_messages


def _add_ad(slot="home", age="0-1"):
    s = SessionLocal()
    ad = Ad(advertiser="测试品牌", title="t", slot=slot, target_age_bucket=age, active=1)
    s.add(ad)
    s.commit()
    s.close()


def _get_ads(client, **params):
    q = {"page": "shelf", "age_bucket": "1-3", "consent": "true", "device_id": "v2-device-0001"}
    q.update(params)
    return client.get("/api/v1/ads", params=q)


def test_v21_risk_and_medical_shield(client):
    """V2.1：风险回答页（L1/L2/L3）与医疗会话不得渲染任何广告。"""
    _add_ad()
    for level in ("L1", "L2", "L3"):
        assert _get_ads(client, risk_level=level).json() == {"ads": []}, level
    assert _get_ads(client, medical="true").json() == {"ads": []}


def test_v22_care_no_brand_markers():
    """V2.2：CARE 结构（结论/行动/依据/就医信号）中不得出现品牌/商品推荐标记。"""
    # 含促销/商品推荐标记 → 被扫描命中
    assert guard.scan_brand_markers("建议购买退热贴") != []
    assert guard.scan_brand_markers("", "点击链接下单", "") != []
    assert guard.scan_brand_markers("限时优惠，扫码购买") != []
    # 正常循证答案 → 不命中
    assert guard.scan_brand_markers("多喝温水、注意休息", "观察精神状态", "依据《指南》") == []


def test_v23_risk_and_prompt_ad_independent(db):
    """V2.3：广告有无不影响风险分级与就医引导结论（确定性分级 + prompt 不含广告）。"""
    q = "宝宝高烧还精神萎靡"
    assert risk.classify_urgent(q) == "L2"
    # 广告目录有数据后，确定性风险分级不受影响
    _add_ad()
    assert risk.classify_urgent(q) == "L2"
    # 问答 prompt 不含任何广告/品牌标记（广告进不了模型输入）
    msgs = build_qa_messages("月龄：12个月；喂养方式：母乳", q, [], [], False, "")
    for m in msgs:
        assert guard.scan_brand_markers(m["content"]) == []

"""医疗通道路由（Baichuan-M3-Plus）测试：路由判断 / 灰度 / 解析 / 升级 / 端到端降级。"""
import pytest

from app.core.config import settings
from app.services import medical
from tests.conftest import parse_sse


# ===== 路由判断 =====
def test_is_medical_by_category():
    assert medical.is_medical_question("随便问", ["医疗问诊"]) is True
    assert medical.is_medical_question("随便问", ["疾病预防与就诊"]) is True


def test_is_medical_semi_category_off_by_default():
    assert medical.is_medical_question("随便问", ["健康监测"]) is False
    assert medical.is_medical_question("随便问", ["伤害预防"]) is False


def test_is_medical_semi_category_opt_in():
    assert medical.is_medical_question("随便问", ["健康监测"], include_semi=True) is True


def test_is_medical_keyword_fallback():
    assert medical.is_medical_question("宝宝发烧了怎么办", []) is True
    assert medical.is_medical_question("宝宝一直咳嗽", ["营养喂养"]) is True


def test_is_medical_excluded_hints():
    assert medical.is_medical_question("发烧的绘本推荐", []) is False
    assert medical.is_medical_question("早教游戏咳嗽怎么玩", []) is False


def test_is_medical_neutral():
    assert medical.is_medical_question("8 个月辅食加什么", ["营养喂养"]) is False


# ===== 灰度开关 =====
def test_should_use_medical_disabled(monkeypatch):
    monkeypatch.setattr(settings, "medical_enabled", False)
    monkeypatch.setattr(settings, "medical_rollout_percent", 100)
    assert medical.should_use_medical(1) is False


def test_should_use_medical_whitelist(monkeypatch):
    monkeypatch.setattr(settings, "medical_enabled", True)
    monkeypatch.setattr(settings, "medical_rollout_percent", 0)
    monkeypatch.setattr(settings, "medical_whitelist_ids", "1,3")
    assert medical.should_use_medical(1) is True
    assert medical.should_use_medical(3) is True
    assert medical.should_use_medical(2) is False


def test_should_use_medical_full_rollout(monkeypatch):
    monkeypatch.setattr(settings, "medical_enabled", True)
    monkeypatch.setattr(settings, "medical_rollout_percent", 100)
    monkeypatch.setattr(settings, "medical_whitelist_ids", "")
    assert medical.should_use_medical(42) is True


def test_should_use_medical_stable_bucket(monkeypatch):
    monkeypatch.setattr(settings, "medical_enabled", True)
    monkeypatch.setattr(settings, "medical_rollout_percent", 50)
    monkeypatch.setattr(settings, "medical_whitelist_ids", "")
    results = {medical.should_use_medical(i) for i in range(1, 200)}
    assert medical.should_use_medical(7) == medical.should_use_medical(7)
    assert results == {True, False}  # 50% 分桶两端都应出现


# ===== JSON 宽容解析 =====
def test_parse_json_plain():
    assert medical._parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_markdown_fence():
    assert medical._parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_noise():
    assert medical._parse_json('好的，结果如下：{"a": 1}') == {"a": 1}


def test_parse_json_invalid():
    with pytest.raises(ValueError):
        medical._parse_json("这不是 JSON")


# ===== 升级提示 =====
def test_apply_escalation_off():
    data = {"conclusion": "观察即可", "red_flags": ["发热加重"]}
    out = medical.apply_escalation(dict(data))
    assert out["conclusion"] == "观察即可"
    assert out["red_flags"] == ["发热加重"]


def test_apply_escalation_on():
    data = {"conclusion": "先观察", "red_flags": ["精神差"], "escalate": True}
    out = medical.apply_escalation(data)
    assert out["conclusion"].startswith("建议尽快带孩子面诊医生")
    assert "尽快线下就医" in out["red_flags"]


# ===== 端到端：医疗问题走百川、非医疗走 DeepSeek、失败降级 =====
def _make_child(client):
    r = client.post(
        "/api/v1/children",
        json={"nickname": "小糯米", "birth_date": "2025-01-15", "feeding_method": "已添加辅食"},
    )
    return r.json()["id"]


def _enable_medical(monkeypatch):
    monkeypatch.setattr(settings, "medical_enabled", True)
    monkeypatch.setattr(settings, "medical_rollout_percent", 100)
    monkeypatch.setattr(settings, "medical_whitelist_ids", "")
    monkeypatch.setattr(settings, "medical_semi_categories", False)


def test_qa_medical_question_uses_medical_channel(monkeypatch, client):
    _enable_medical(monkeypatch)
    child_id = _make_child(client)

    def fake_medical(messages, max_retries=1):
        return (
            {
                "risk_level": "L3",
                "conclusion": "这是百川医疗通道给出的结论",
                "actions": ["监测体温", "多喝水"],
                "evidence": ["来自医疗模型"],
                "red_flags": ["持续高热"],
                "disclaimer": "不替代医生。",
                "followup_question": None,
                "source_ids": [],
            },
            None,
        )

    def _llm_must_not_call(*a, **k):
        raise AssertionError("医疗问题不应走 DeepSeek 通道")

    monkeypatch.setattr("app.services.medical.chat_json_medical", fake_medical)
    monkeypatch.setattr("app.services.llm.chat_json", _llm_must_not_call)

    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "宝宝发烧了怎么办"}
    ) as resp:
        events = parse_sse(resp)

    done = [e for e in events if e[0] == "done"][0][1]
    assert done["conclusion"] == "这是百川医疗通道给出的结论"
    assert done["risk_level"] == "L3"


def test_qa_non_medical_question_uses_deepseek(monkeypatch, client):
    _enable_medical(monkeypatch)
    child_id = _make_child(client)

    def fake_llm(messages, max_retries=2):
        return (
            {
                "risk_level": "L4",
                "conclusion": "这是 DeepSeek 通用通道的结论",
                "actions": ["由少到多添加辅食"],
                "evidence": [],
                "red_flags": [],
                "disclaimer": "请咨询医生。",
                "followup_question": None,
                "source_ids": [],
            },
            None,
        )

    def _medical_must_not_call(*a, **k):
        raise AssertionError("非医疗问题不应走百川通道")

    monkeypatch.setattr("app.services.llm.chat_json", fake_llm)
    monkeypatch.setattr("app.services.medical.chat_json_medical", _medical_must_not_call)

    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "8 个月辅食加什么"}
    ) as resp:
        events = parse_sse(resp)

    done = [e for e in events if e[0] == "done"][0][1]
    assert done["conclusion"] == "这是 DeepSeek 通用通道的结论"


def test_qa_medical_failure_falls_back_to_deepseek(monkeypatch, client):
    _enable_medical(monkeypatch)
    child_id = _make_child(client)

    def fake_medical_fail(messages, max_retries=1):
        raise RuntimeError("百川不可用")

    def fake_llm(messages, max_retries=2):
        return (
            {
                "risk_level": "L4",
                "conclusion": "降级到 DeepSeek 的结论",
                "actions": ["先观察体温"],
                "evidence": [],
                "red_flags": ["持续高热需就医"],
                "disclaimer": "请咨询医生。",
                "followup_question": None,
                "source_ids": [],
            },
            None,
        )

    monkeypatch.setattr("app.services.medical.chat_json_medical", fake_medical_fail)
    monkeypatch.setattr("app.services.llm.chat_json", fake_llm)

    with client.stream(
        "POST", "/api/v1/qa", json={"child_id": child_id, "question": "宝宝发烧了怎么办"}
    ) as resp:
        events = parse_sse(resp)

    # 不应出现 error 事件，且应拿到 DeepSeek 的降级结论
    errs = [e for e in events if e[0] == "error"]
    assert errs == []
    done = [e for e in events if e[0] == "done"][0][1]
    assert done["conclusion"] == "降级到 DeepSeek 的结论"

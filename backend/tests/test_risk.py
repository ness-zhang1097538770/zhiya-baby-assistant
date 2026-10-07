from app.services.risk import classify_urgent


def test_l1_critical():
    assert classify_urgent("宝宝突然抽搐怎么办") == "L1"
    assert classify_urgent("孩子窒息了") == "L1"


def test_l2_urgent():
    assert classify_urgent("孩子持续呕吐") == "L2"
    assert classify_urgent("大便有血便") == "L2"


def test_l2_combo_fever_and_bad_state():
    assert classify_urgent("宝宝高热而且精神差") == "L2"


def test_not_urgent_returns_none():
    assert classify_urgent("8 个月宝宝辅食可以加什么") is None
    assert classify_urgent("宝宝睡眠倒退怎么办") is None

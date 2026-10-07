"""记忆召回（S09 Memory 读侧）：按相关性读回 ChildFact，注入问答/管家上下文。"""
from app.models.models import Child, ChildFact, Family
from app.services import memory
from app.services.memory import format_facts, list_child_facts, recall_facts


def _mk_child(db) -> Child:
    fam = Family(name="测试家庭")
    db.add(fam)
    db.commit()
    db.refresh(fam)
    c = Child(family_id=fam.id, nickname="小糯米", birth_date="2025-01-15")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _add_fact(db, child_id, category, key, value, deleted=False):
    f = ChildFact(
        child_id=child_id,
        category=category,
        key=key,
        value=value,
        source="ai_extract",
    )
    if deleted:
        from datetime import datetime

        f.deleted_at = datetime.now()
    db.add(f)
    db.commit()
    return f


# ---- 存储读取 ----

def test_list_child_facts_only_active_and_ordered(db):
    child = _mk_child(db)
    _add_fact(db, child.id, "allergy", "鸡蛋", "过敏")
    _add_fact(db, child.id, "preference", "苹果泥", "喜欢吃")
    _add_fact(db, child.id, "habit", "午睡", "两点左右", deleted=True)
    other = _mk_child(db)
    _add_fact(db, other.id, "allergy", "牛奶", "过敏")

    facts = list_child_facts(db, child.id)
    assert len(facts) == 2
    assert all(f.deleted_at is None for f in facts)
    assert {f.key for f in facts} == {"鸡蛋", "苹果泥"}


# ---- 召回 ----

def test_recall_facts_returns_empty_when_no_facts(db):
    child = _mk_child(db)
    assert recall_facts(db, child.id, "宝宝能吃鸡蛋吗") == []


def test_recall_facts_injects_all_when_few(db):
    child = _mk_child(db)
    _add_fact(db, child.id, "allergy", "鸡蛋", "过敏")
    _add_fact(db, child.id, "preference", "苹果泥", "喜欢吃")
    # 事实少时全量注入，即使问题与某条无关也不漏召回（如「水果」与「苹果泥」的语义关联）
    got = recall_facts(db, child.id, "宝宝喜欢吃什么水果")
    assert {f.key for f in got} == {"鸡蛋", "苹果泥"}


def test_recall_facts_filters_when_many(db):
    child = _mk_child(db)
    _add_fact(db, child.id, "allergy", "鸡蛋", "过敏")
    _add_fact(db, child.id, "allergy", "牛奶", "过敏")
    _add_fact(db, child.id, "allergy", "花生", "过敏")
    _add_fact(db, child.id, "preference", "苹果泥", "喜欢吃")
    _add_fact(db, child.id, "habit", "午睡", "两点左右")
    _add_fact(db, child.id, "milestone", "翻身", "已会")
    got = recall_facts(db, child.id, "宝宝能吃鸡蛋和牛奶吗", max_items=3)
    keys = [f.key for f in got]
    # 只命中鸡蛋、牛奶两条，不应为凑满 max_items 而塞无关事实
    assert sorted(keys) == ["牛奶", "鸡蛋"]
    assert len(got) == 2


def test_recall_facts_respects_max_items(db):
    child = _mk_child(db)
    _add_fact(db, child.id, "allergy", "鸡蛋", "过敏")
    _add_fact(db, child.id, "allergy", "牛奶", "过敏")
    _add_fact(db, child.id, "allergy", "花生", "过敏")
    got = recall_facts(db, child.id, "鸡蛋 牛奶 花生", max_items=2)
    assert len(got) == 2


# ---- 格式化 ----

def test_format_facts_empty():
    assert format_facts([]) == ""


def test_format_facts_uses_chinese_labels(db):
    child = _mk_child(db)
    _add_fact(db, child.id, "allergy", "鸡蛋", "过敏")
    got = format_facts(recall_facts(db, child.id, "鸡蛋"))
    assert "[过敏] 鸡蛋：过敏" in got


# ---- 去重（S09 should_store_memory） ----

def test_save_fact_dedup_updates_same_key(db):
    from app.services import agent_service

    child = _mk_child(db)
    agent_service._do_save_fact(db, child.id, {"category": "allergy", "key": "鸡蛋", "value": "过敏"})
    summary = agent_service._do_save_fact(db, child.id, {"category": "allergy", "key": "鸡蛋", "value": "严重过敏"})
    facts = db.query(ChildFact).filter(ChildFact.child_id == child.id, ChildFact.deleted_at.is_(None)).all()
    assert len(facts) == 1
    assert facts[0].value == "严重过敏"
    assert "更新" in summary


def test_save_fact_dedup_skips_exact_duplicate(db):
    from app.services import agent_service

    child = _mk_child(db)
    agent_service._do_save_fact(db, child.id, {"category": "allergy", "key": "鸡蛋", "value": "过敏"})
    summary = agent_service._do_save_fact(db, child.id, {"category": "allergy", "key": "鸡蛋", "value": "过敏"})
    facts = db.query(ChildFact).filter(ChildFact.child_id == child.id, ChildFact.deleted_at.is_(None)).all()
    assert len(facts) == 1
    assert "未重复添加" in summary

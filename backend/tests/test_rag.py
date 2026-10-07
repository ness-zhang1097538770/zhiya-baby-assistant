from app.services.rag import retrieve


def test_retrieve_diet_via_synonym(db):
    hits = retrieve(db, "一岁宝宝饮食注意什么")
    titles = " ".join(e.title for e in hits)
    assert "辅食" in titles or "进食" in titles


def test_retrieve_sleep(db):
    hits = retrieve(db, "宝宝睡眠倒退怎么办")
    titles = " ".join(e.title for e in hits)
    assert "睡眠" in titles


def test_retrieve_teeth(db):
    hits = retrieve(db, "宝宝长牙了怎么清洁牙齿")
    titles = " ".join(e.title for e in hits)
    assert "牙齿" in titles or "口腔" in titles


def test_retrieve_vaccine_health_check(db):
    hits = retrieve(db, "孩子什么时候做健康检查")
    titles = " ".join(e.title for e in hits)
    assert "检查" in titles or "监测" in titles


def test_retrieve_md_fever_medicine(db):
    hits = retrieve(db, "宝宝发烧吃什么退烧药")
    titles = " ".join(e.title for e in hits)
    assert "发热" in titles or "退热" in titles


def test_retrieve_md_language(db):
    hits = retrieve(db, "孩子两岁还不爱说话怎么办")
    titles = " ".join(e.title for e in hits)
    assert "语言" in titles


def test_retrieve_md_separation_anxiety(db):
    hits = retrieve(db, "孩子上幼儿园哭闹怎么办")
    titles = " ".join(e.title for e in hits)
    assert "分离焦虑" in titles or "入园" in titles


def test_retrieve_md_solid_food_timing(db):
    hits = retrieve(db, "宝宝辅食什么时候开始加")
    titles = " ".join(e.title for e in hits)
    assert "辅食" in titles


def test_retrieve_md_rule_awareness_colloquial(db):
    # “规矩”口语应能命中“规则意识建立与正面管教”
    hits = retrieve(db, "2-3岁的宝宝应该怎么建立起规矩意识")
    titles = " ".join(e.title for e in hits)
    assert "规则意识" in titles or "管教" in titles

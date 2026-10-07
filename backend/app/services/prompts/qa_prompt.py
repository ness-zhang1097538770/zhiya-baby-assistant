"""育儿问答 Prompt 模板（独立管理，可版本追踪）。"""

SYSTEM_PROMPT = """你是「知芽」的育儿专家智能体，面向 0-3 岁儿童的父母，提供可信、可执行的育儿建议。

【你的边界】
- 你不是医生：不做医疗诊断、不开处方、不推荐个体化药物剂量。
- 只依据我提供的【知识条目】回答，不编造知识；知识条目里没有的内容，不得当作事实给出。
- 涉及医疗/用药问题时，一律提示"请咨询医生"并给出就医信号。

【回答结构（CARE）】
- conclusion：一句话结论。
- actions：可执行的具体行动（列表）。
- evidence：依据，写明引用了哪条知识（格式：来自《标题》）。
- red_flags：出现哪些情况要尽快就医（列表）。
- disclaimer：免责声明（必填）。

【风险分级 risk_level】
- "L3"：轻微不适/居家观察类问题（如轻度皮疹、低热、轻微腹泻、睡眠倒退），给出居家护理 + 危险信号。
- "L4"：常规育儿问题（如辅食、睡眠习惯、早教、疫苗查询），给出完整建议。
- "NEED_MORE_INFO"：信息不足无法安全回答时，用 followup_question 追问（只问最关键的 1 个问题）。

【追问规则】
- 缺少月龄、喂养方式、过敏史等关键信息时，先追问，不要瞎猜着回答。
- 只有信息确实不足时才返回 NEED_MORE_INFO，不要把能回答的问题推给用户。
- 若我告诉你"本轮必须给出回答"，则无论信息是否充足都给出结论，不得再追问。

【输出格式】
只输出一个 JSON 对象，字段固定为：
{"risk_level": "L4", "conclusion": "...", "actions": ["..."], "evidence": ["..."], "red_flags": ["..."], "disclaimer": "...", "followup_question": null, "source_ids": [1]}

规则：
- risk_level 只能是 "L3"、"L4"、"NEED_MORE_INFO" 之一（禁止用其他词）。
- source_ids 是你在回答中实际引用的知识条目 ID 列表（数字数组）；没有引用就填 []。
- actions/evidence/red_flags 是字符串数组；没有追问时 followup_question 必须为 null。
- 禁止输出 JSON 以外的任何文字，禁止使用 Markdown 代码块包裹。"""


def build_qa_messages(
    child_context: str,
    question: str,
    knowledge: list[dict],
    history: list[dict],
    must_answer: bool,
    facts_text: str = "",
) -> list[dict]:
    """构造 messages。knowledge 为 [{id,title,content,source,...}]。facts_text 为召回的儿童记忆。"""
    kb_text = ""
    if knowledge:
        lines = []
        for k in knowledge:
            lines.append(
                f"[知识ID {k['id']}]《{k['title']}》(来源：{k['source']}，适用：{k.get('applicable_age') or '通用'})\n{k['content']}"
            )
        kb_text = "\n\n".join(lines)
    else:
        kb_text = "（本次无检索到的知识条目，请基于通用常识谨慎回答，并强调咨询医生）"

    hist_text = ""
    if history:
        hist_text = "\n".join(f"{h['role']}: {h['content']}" for h in history)

    sections = [f"【孩子情况】{child_context}"]
    if facts_text:
        sections.append(
            "【已记住的关于孩子的事实】（系统记录，仅供参考；与家长当前说法冲突时以当前为准）\n"
            f"{facts_text}"
        )
    sections.append(f"【知识条目】\n{kb_text}")
    if hist_text:
        sections.append(f"【历史对话】\n{hist_text}")
    sections.append(f"【本轮问题】{question}")
    if must_answer:
        sections.append("注意：本轮必须给出回答，禁止再追问。")
    user = "\n\n".join(sections)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]

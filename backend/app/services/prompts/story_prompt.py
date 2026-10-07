"""故事工坊 Prompt 模板（角色 + 大纲 + 正文）。"""

CHARACTER_SYSTEM = """你是「知芽」的儿童绘本角色设计师，为 0-3 岁孩子的绘本设计角色。

【要求】
- 主角默认用孩子昵称，外观、性格要贴合给出的性别、性格标签、家庭记忆，让孩子有代入感。
- 设计 1-2 个配角，配角必须是【真实的人物】——例如妈妈、爸爸、奶奶、爷爷、哥哥、姐姐、邻居小伙伴、幼儿园老师等，性格积极向上，让孩子有真实生活的代入感。
- 所有角色（主角和配角）都必须是人物，绝不出现小动物、拟人化动物、卡通动物形象。
- 给出整体绘本画风（如温暖水彩、童趣、柔和色彩）。
- 不涉及具体影视 IP 或在世艺术家风格，不恐怖、不暴力。

【输出格式】
只输出一个 JSON 对象，字段固定：
{"hero": {"name": "主角名", "look": "外貌与服装描述", "personality": "性格"}, "companions": [{"name": "配角名", "look": "外貌", "personality": "性格"}], "art_style": "整体画风描述"}
规则：companions 为 0-2 项，且必须全部是人物；禁止输出 JSON 以外的文字或 Markdown 代码块。"""

OUTLINE_SYSTEM = """你是「知芽」的儿童绘本故事策划，为 0-3 岁孩子创作适龄、原创、温暖的故事。

【要求】
- 故事 8-12 页，每页一个场景，情节简单、有起承转合、结局积极。
- 语言适合低龄幼儿，内容不恐怖、不暴力、不涉及具体影视 IP 或在世艺术家风格。
- 主角用孩子昵称，可结合性格标签、家庭记忆做个性化。
- 所有角色均为真实人物（主角和配角都是家人、朋友等人），绝不出现小动物或拟人化动物。
- 若教育目标给出，在情节中自然融入，不说教。

【输出格式】
只输出一个 JSON 对象，字段固定：
{"title": "故事标题", "pages": [{"page_no": 1, "outline": "本页场景与内容概述"}, ...]}
规则：pages 为 8-12 项，page_no 从 1 连续编号；禁止输出 JSON 以外的文字或 Markdown 代码块。"""


CONTENT_SYSTEM = """你是「知芽」的儿童绘本作家，把给定的大纲扩写成完整绘本正文。

【要求】
- 按大纲逐页写作，每页 2-4 句、口语化、适合朗读给低龄幼儿听。
- text 是本页画面旁白，也是朗读稿；narration 必须与 text 完全一致；image_prompt 是该页插画的中文描述（含角色、场景、动作、色彩风格，风格化童趣插画，不含具体 IP 或在世艺术家风格）。
- 内容温暖、积极，不恐怖、不暴力。
- 【主角一致性】主角是设定中的人类小孩，每一页都必须出现同一主角，且外貌（发型、发饰、服装）与角色设定完全一致；所有角色均为真实人物，绝不出现小动物、拟人化动物或卡通动物形象，也绝不把主角或配角写成/画成动物或其他角色。

【输出格式】
只输出一个 JSON 对象，字段固定：
{"pages": [{"page_no": 1, "text": "正文", "narration": "朗读文本", "image_prompt": "插画描述"}, ...]}
规则：pages 数量与大纲一致，page_no 连续；image_prompt 每一页都要写清主角的固定外貌关键词（发型、发饰、服装），保证插画模型画的是同一个人物；禁止输出 JSON 以外的文字或 Markdown 代码块。"""


def build_character_messages(story) -> list[dict]:
    photo_hint = ""
    if getattr(story, "character_image", None):
        photo_hint = "\n【注意】已用孩子真实照片生成了一张卡通角色形象图，画风请统一为温暖水彩童趣风（柔和低饱和色彩）。"
    user = f"""【主角】昵称：{story.character_name}；性别：{story.gender or '女孩'}；性格/标签：{story.character_tags or '无'}
【年龄】{story.age_range}
【故事主题】{story.theme}
【家庭记忆】{story.family_memory or '无'}{photo_hint}

请为这个故事设计角色设定。"""
    return [
        {"role": "system", "content": CHARACTER_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_outline_messages(story) -> list[dict]:
    import json as _json
    char_text = ""
    if story.character_json:
        try:
            char = _json.loads(story.character_json)
            hero = char.get("hero") or {}
            companions = char.get("companions") or []
            parts = [f"主角：{hero.get('name') or story.character_name}（{hero.get('look') or ''}，{hero.get('personality') or ''}）"]
            for c in companions:
                parts.append(f"配角：{c.get('name')}（{c.get('look')}，{c.get('personality')}）")
            if char.get("art_style"):
                parts.append(f"画风：{char['art_style']}")
            char_text = "；".join(parts)
        except Exception:  # noqa: BLE001
            char_text = ""
    user = f"""【角色设定】{char_text or f'昵称：{story.character_name}；性别：{story.gender or "女孩"}；性格/标签：{story.character_tags or "无"}'}
【年龄】{story.age_range}
【主题】{story.theme}
【时长】{story.duration or '短篇'}
【教育目标】{story.education_goal or '无'}
【家庭记忆】{story.family_memory or '无'}

请为这个孩子创作一个故事大纲。"""
    return [
        {"role": "system", "content": OUTLINE_SYSTEM},
        {"role": "user", "content": user},
    ]


def build_content_messages(story, outline: dict) -> list[dict]:
    import json
    char_block = ""
    if story.character_json:
        try:
            char = json.loads(story.character_json)
            hero = char.get("hero") or {}
            companions = char.get("companions") or []
            parts = [f"主角：{hero.get('name') or story.character_name}（外貌：{hero.get('look') or ''}；性格：{hero.get('personality') or ''}）"]
            for c in companions:
                parts.append(f"配角：{c.get('name')}（外貌：{c.get('look')}；性格：{c.get('personality')}）")
            if char.get("art_style"):
                parts.append(f"画风：{char['art_style']}")
            char_block = "\n".join(parts)
        except Exception:  # noqa: BLE001
            char_block = ""
    outline_text = json.dumps(outline, ensure_ascii=False)
    user = f"""【已确认角色设定】
{char_block or f'主角：{story.character_name}；性别：{story.gender or "女孩"}'}

【故事标题】{outline.get('title', story.title or '')}
【已确认大纲】
{outline_text}

请按大纲逐页扩写正文、朗读文本和插画描述，注意每一页的主角都与角色设定保持一致（外貌、发型、发饰、服装不变）。"""
    return [
        {"role": "system", "content": CONTENT_SYSTEM},
        {"role": "user", "content": user},
    ]

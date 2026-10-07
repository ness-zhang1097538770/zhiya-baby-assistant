"""故事工坊编排：大纲生成、正文生成、插画/朗读生成（后台任务）。"""
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from app.db import SessionLocal
from app.models.models import Story, Child
from app.services import llm, media, cost
from app.services.prompts.story_prompt import build_character_messages, build_content_messages, build_outline_messages

# 封面图是硬要求：每张故事绘本必须有一张真实插画作为封面，不允许静默产出无封面的故事
COVER_MIN_BYTES = 1024
COVER_RETRIES = 3
AUDIO_MIN_BYTES = 256
# 插画/朗读并发数：串行要 20 次来回，并发后总耗时主要看最慢的一批
ASSET_WORKERS = 4


def _parse_character(data: dict) -> dict:
    """宽容解析角色设定 JSON。hero.name 允许为空（前端回退用孩子昵称）。"""
    hero = data.get("hero") if isinstance(data.get("hero"), dict) else {}
    companions: List[dict] = []
    raw = data.get("companions")
    if isinstance(raw, list):
        for c in raw[:2]:
            if isinstance(c, dict) and str(c.get("name") or "").strip():
                companions.append(
                    {
                        "name": str(c.get("name") or "").strip(),
                        "look": str(c.get("look") or "").strip(),
                        "personality": str(c.get("personality") or "").strip(),
                    }
                )
    return {
        "hero": {
            "name": str(hero.get("name") or "").strip(),
            "look": str(hero.get("look") or "").strip(),
            "personality": str(hero.get("personality") or "").strip(),
        },
        "companions": companions,
        "art_style": str(data.get("art_style") or "").strip(),
    }


def _parse_outline(data: dict) -> dict:
    """宽容解析大纲 JSON，返回 {title, pages:[{page_no, outline}]}。"""
    title = str(data.get("title") or "").strip()
    raw = data.get("pages")
    pages: List[dict] = []
    if isinstance(raw, list):
        for i, p in enumerate(raw, 1):
            if isinstance(p, dict):
                try:
                    page_no = int(p.get("page_no") or i)
                except (TypeError, ValueError):
                    page_no = i
                outline = str(p.get("outline") or "").strip()
                if outline:
                    pages.append({"page_no": page_no, "outline": outline})
    if not pages:
        raise ValueError("大纲解析失败：无有效页")
    return {"title": title, "pages": pages}


def _parse_content(data: dict) -> dict:
    """宽容解析正文 JSON，返回 {pages:[{page_no, text, narration, image_prompt}]}。"""
    raw = data.get("pages")
    pages: List[dict] = []
    if isinstance(raw, list):
        for i, p in enumerate(raw, 1):
            if isinstance(p, dict):
                try:
                    page_no = int(p.get("page_no") or i)
                except (TypeError, ValueError):
                    page_no = i
                text = str(p.get("text") or "").strip()
                # 朗读稿必须与页面正文完全一致，方便用户边看边听
                narration = text
                image_prompt = str(p.get("image_prompt") or "").strip()
                if text:
                    pages.append(
                        {
                            "page_no": page_no,
                            "text": text,
                            "narration": narration,
                            "image_prompt": image_prompt,
                        }
                    )
    if not pages:
        raise ValueError("正文解析失败：无有效页")
    return {"pages": pages}


def _run(story_id: int, step: str):
    """后台任务统一入口。step: outline / content。"""
    db = SessionLocal()
    try:
        story = db.get(Story, story_id)
        if story is None:
            return
        _set_cost_family(db, story)
        if story.cancel_requested:
            story.status = "cancelled"
            db.commit()
            return
        if step == "character":
            messages = build_character_messages(story)
            data, _usage = llm.chat_json(messages)
            character = _parse_character(data)
            story.character_json = json.dumps(character, ensure_ascii=False)
            story.status = "character_ready"
            # 无照片时：用角色外貌生成一张"定妆图"作后续插画统一参考，保证主角跨页一致
            if not story.character_image:
                _ensure_character_ref(story, character)
        elif step == "outline":
            messages = build_outline_messages(story)
            data, _usage = llm.chat_json(messages)
            outline = _parse_outline(data)
            story.outline_json = json.dumps(outline, ensure_ascii=False)
            story.title = outline["title"] or story.title
            story.status = "outline_ready"
        else:  # content
            outline = json.loads(story.outline_json) if story.outline_json else {"title": story.title or "", "pages": []}
            messages = build_content_messages(story, outline)
            data, _usage = llm.chat_json(messages)
            content = _parse_content(data)
            story.pages_json = json.dumps(content, ensure_ascii=False)
            story.status = "content_ready"
        story.error = None
        db.commit()
        # 正文完成后自动接着生成插画：保证每个故事都有封面图，不再停在"待生成插画"等用户再点一次
        if step == "content" and not story.cancel_requested:
            story.status = "assets_generating"
            db.commit()
            generate_assets_task(story_id)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        story = db.get(Story, story_id)
        if story is not None:
            story.status = "failed"
            story.error = _err_text(e)
            db.commit()
    finally:
        db.close()


def _err_text(e: Exception) -> str:
    code = getattr(e, "code", None) or type(e).__name__
    msg = getattr(e, "message", None) or str(e)
    return f"{code}: {msg}"[:500]


def generate_character_task(story_id: int):
    _run(story_id, "character")


def generate_outline_task(story_id: int):
    _run(story_id, "outline")


def generate_content_task(story_id: int):
    _run(story_id, "content")


def _cancelled(db, story_id: int) -> bool:
    return bool(db.get(Story, story_id).cancel_requested)


def _set_cost_family(db, story: Story) -> None:
    """把成本归属设到故事所属家庭（后台任务不经过 API 依赖，需显式设置）。"""
    child = db.get(Child, story.child_id)
    if child is not None and child.family_id is not None:
        cost.set_family(child.family_id)


def _mark_cancelled(db, story: Story) -> None:
    story.status = "cancelled"
    db.commit()


def _ensure_character_ref(story, character: dict) -> None:
    """无照片时，用角色外貌生成一张定妆图作为后续插画统一参考；失败不阻断（回退纯文生图）。"""
    try:
        hero = character.get("hero") or {}
        look = (hero.get("look") or "").strip()
        art = (character.get("art_style") or "").strip() or "温暖水彩童趣风"
        if not look:
            return
        ref_path = os.path.join(media.ASSETS_DIR, "characters", f"{uuid.uuid4().hex}.png")
        media.generate_image(
            f"{look}。{art}。正面半身像，纯色浅色背景，儿童绘本角色设定图，圆润可爱，柔和低饱和色彩。",
            ref_path,
        )
        story.character_image = media.rel_path(ref_path)
    except Exception:  # noqa: BLE001
        pass


def regenerate_character_image(story, look: str | None = None, art_style: str | None = None) -> None:
    """用当前角色外貌 + 画风重新生成角色形象图（覆盖 character_image）。失败抛 MediaError。"""
    character = json.loads(story.character_json) if story.character_json else {}
    hero = (character or {}).get("hero") or {}
    # 优先用前端传来的最新编辑值，否则回退到已存角色设定
    look = (look or "").strip() or (hero.get("look") or "").strip()
    art = (art_style or "").strip() or (character.get("art_style") or "").strip() or "温暖水彩童趣风"
    if not look:
        raise media.MediaError("NO_CHARACTER_LOOK", "还没有主角外貌，请先在下方填写主角外貌再重新生成")
    ref_path = os.path.join(media.ASSETS_DIR, "characters", f"{uuid.uuid4().hex}.png")
    media.generate_image(
        f"{look}。{art}。正面半身像，纯色浅色背景，儿童绘本角色设定图，圆润可爱，柔和低饱和色彩。",
        ref_path,
    )
    story.character_image = media.rel_path(ref_path)


def _character_ref_abs(story) -> str | None:
    """拿到角色的参考图绝对路径；没有或不存在的返回 None。"""
    if not story.character_image:
        return None
    try:
        abs_p = media.abs_path(story.character_image)
        return abs_p if os.path.exists(abs_p) and os.path.getsize(abs_p) >= COVER_MIN_BYTES else None
    except Exception:  # noqa: BLE001
        return None


def _generate_page_image(char_ref: str | None, prompt: str, path: str) -> str:
    """有角色参考图就走图生图（保长相一致），否则回退纯文生图；图生图失败也回退纯文生图，保证绘本能继续。"""
    if char_ref:
        try:
            return media.generate_page_image(char_ref, prompt, path)
        except media.MediaError:
            return media.generate_image(prompt, path)
    return media.generate_image(prompt, path)


def _generate_cover(prompt: str, path: str, char_ref: str | None = None) -> str:
    """封面图必须成功：失败重试，仍失败则抛错（绝不留无封面的故事）。"""
    last: Exception | None = None
    for attempt in range(COVER_RETRIES):
        try:
            abs_path = _generate_page_image(char_ref, prompt, path)
            size = os.path.getsize(abs_path)
            if size >= COVER_MIN_BYTES:
                return abs_path
            last = RuntimeError(f"封面图过小（{size} 字节）")
        except Exception as e:  # noqa: BLE001
            last = e
        if attempt < COVER_RETRIES - 1:
            time.sleep(3)
    raise RuntimeError(f"封面图生成失败：{_err_text(last) if last else '未知原因'}")


def _dump(mapping: dict) -> str:
    """{page_no: url} → 按页码排序的 [{"page_no","url"}] JSON。"""
    return json.dumps(
        [{"page_no": n, "url": mapping[n]} for n in sorted(mapping, key=lambda x: int(x))],
        ensure_ascii=False,
    )


def _asset_job(kind: str, page: dict, base: str, gender: str, char_ref: str | None = None) -> str:
    """单页素材：插画或朗读。已生成过且文件有效就直接复用，重跑/续传时省下重复调用。"""
    n = page.get("page_no")
    if kind == "image":
        path = os.path.join(base, f"page_{n}.png")
        if os.path.exists(path) and os.path.getsize(path) >= COVER_MIN_BYTES:
            return media.rel_path(path)
        prompt = page.get("image_prompt") or page.get("text", "")
        return media.rel_path(_generate_page_image(char_ref, prompt, path))
    path = os.path.join(base, f"page_{n}.mp3")
    if os.path.exists(path) and os.path.getsize(path) >= AUDIO_MIN_BYTES:
        return media.rel_path(path)
    return media.rel_path(
        media.generate_audio(page.get("text", ""), path, gender=gender)  # 朗读稿用正文，与画面一致
    )


def generate_assets_task(story_id: int):
    """为每页生成插画 + 朗读音频。封面（第一页）优先生成并强制成功，其余素材并发生成。"""
    db = SessionLocal()
    try:
        story = db.get(Story, story_id)
        if story is None or not story.pages_json:
            return
        _set_cost_family(db, story)
        pages = json.loads(story.pages_json).get("pages", [])
        if not pages:
            raise ValueError("无正文页，无法生成封面")
        base = os.path.join(media.ASSETS_DIR, str(story_id))
        gender = story.gender or "女孩"
        char_ref = _character_ref_abs(story)
        if _cancelled(db, story_id):
            _mark_cancelled(db, story)
            return

        # 1) 封面优先：先出图先落库，用户能尽早看到封面
        first = pages[0]
        n0 = first.get("page_no")
        cover_abs = _generate_cover(
            first.get("image_prompt") or first.get("text", ""),
            os.path.join(base, f"page_{n0}.png"),
            char_ref,
        )
        images = {n0: media.rel_path(cover_abs)}
        story.images_json = _dump(images)
        db.commit()

        # 2) 其余插画 + 全部朗读并发生成，边完成边落库（页面能逐页看到）
        jobs = []
        for i, p in enumerate(pages):
            n = p.get("page_no")
            if i != 0:
                jobs.append(("image", n, p))
            jobs.append(("audio", n, p))

        audios: dict = {}
        ex = ThreadPoolExecutor(max_workers=ASSET_WORKERS)
        try:
            futures = {
                ex.submit(_asset_job, kind, p, base, gender, char_ref): (kind, n)
                for kind, n, p in jobs
            }
            for fut in as_completed(futures):
                if _cancelled(db, story_id):  # 停止请求：取消未开始的任务，已提交的不等
                    ex.shutdown(wait=False, cancel_futures=True)
                    _mark_cancelled(db, story)
                    return
                kind, n = futures[fut]
                url = fut.result()  # 任一页失败 → 外层标记 failed 并报出可见错误
                if kind == "image":
                    images[n] = url
                    story.images_json = _dump(images)
                else:
                    audios[n] = url
                    story.audio_json = _dump(audios)
                db.commit()
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        # 2) 收尾校验：封面图必须真实存在且不是空文件，否则不允许标记完成
        if not os.path.exists(cover_abs) or os.path.getsize(cover_abs) < COVER_MIN_BYTES:
            raise RuntimeError("封面图缺失或过小，不允许标记完成")
        story.images_json = _dump(images)
        story.audio_json = _dump(audios)
        story.status = "ready"
        story.error = None
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        story = db.get(Story, story_id)
        if story is not None:
            story.status = "failed"
            story.error = _err_text(e)
            db.commit()
    finally:
        db.close()

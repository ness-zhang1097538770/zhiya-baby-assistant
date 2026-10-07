"""硅基流动媒体服务：文生图（插画）+ 图生图（照片转角色）+ 语音合成（朗读）。"""
import base64
import io
import os
import time

import httpx
from PIL import Image

from app.core.config import settings
from app.services import cost as cost_service

ASSETS_DIR = settings.assets_dir or os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "story_assets"
)


class MediaError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _client() -> httpx.Client:
    if not settings.siliconflow_api_key:
        raise MediaError("SF_NO_KEY", "缺少硅基流动 API Key")
    return httpx.Client(
        base_url=settings.siliconflow_base_url,
        headers={"Authorization": f"Bearer {settings.siliconflow_api_key}"},
        timeout=180,
    )


def generate_image(prompt: str, save_path: str, max_retries: int = 5) -> str:
    """文生图：调用硅基流动 → 下载图片保存到本地 → 返回文件绝对路径。
    遇限流（429 IPM）时等待后重试。"""
    client = _client()
    try:
        for attempt in range(max_retries + 1):
            r = client.post(
                "/images/generations",
                json={
                    "model": settings.siliconflow_image_model,
                    "prompt": prompt,
                    "image_size": "960x1280",  # 3:4 竖版绘本比例
                },
            )
            if r.status_code == 200:
                data = r.json()
                url = data["images"][0]["url"]
                img = client.get(url)
                img.raise_for_status()
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(img.content)
                cost_service.record(settings.siliconflow_image_model, "image", count=1)
                return save_path
            if (r.status_code == 429 or r.status_code >= 500) and attempt < max_retries:
                # 限流/服务端瞬时错误退避：先短后长，持续失败最多等 60 秒
                time.sleep(min(60, 15 * (attempt + 1)))
                continue
            r.raise_for_status()
        raise MediaError("SF_IMAGE_RATE_LIMIT", "图片生成持续限流，请稍后重试")
    except MediaError:
        raise
    except Exception as e:  # noqa: BLE001
        raise MediaError("SF_IMAGE_FAILED", f"{type(e).__name__}: {str(e)[:200]}")
    finally:
        client.close()


def _to_jpeg_b64(data: bytes, quality: int = 90) -> str:
    """任意图片字节 → JPEG 的 base64（图生图统一入参）。"""
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:  # noqa: BLE001
        raise MediaError("SF_PHOTO_INVALID", f"图片无法读取：{type(e).__name__}")


def _image_edit(b64_jpeg: str, prompt: str, save_path: str, max_retries: int, rate_code: str, fail_code: str) -> str:
    """Qwen-Image-Edit 图生图：入参 JPEG base64 + 指令 → 下载结果保存到本地。"""
    client = _client()
    try:
        for attempt in range(max_retries + 1):
            r = client.post(
                "/images/generations",
                json={
                    "model": settings.siliconflow_character_image_model,
                    "prompt": prompt,
                    "image": f"data:image/jpeg;base64,{b64_jpeg}",
                    "image_size": "960x1280",
                },
            )
            if r.status_code == 200:
                data = r.json()
                url = data["images"][0]["url"]
                img_resp = client.get(url)
                img_resp.raise_for_status()
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(img_resp.content)
                cost_service.record(settings.siliconflow_character_image_model, "image", count=1)
                return save_path
            if (r.status_code == 429 or r.status_code >= 500) and attempt < max_retries:
                time.sleep(min(60, 15 * (attempt + 1)))
                continue
            r.raise_for_status()
        raise MediaError(rate_code, "绘本插画生成持续限流，请稍后重试")
    except MediaError:
        raise
    except Exception as e:  # noqa: BLE001
        raise MediaError(fail_code, f"{type(e).__name__}: {str(e)[:200]}")
    finally:
        client.close()


def generate_character_image(photo_bytes: bytes, save_path: str, max_retries: int = 3) -> str:
    """照片转绘本角色形象：Qwen-Image-Edit 图生图。

    照片统一转 JPEG 后以 data URI 传入，模型按指令转成儿童绘本卡通角色，
    生成的角色形象图保存到本地，原照片由调用方负责删除（隐私）。
    """
    b64 = _to_jpeg_b64(photo_bytes)
    prompt = (
        "把这张照片转成儿童绘本风格的卡通角色形象：圆润可爱的水彩童趣风，柔和低饱和色彩，"
        "保留孩子的主要特征（发型、脸型、表情、穿着），保持人物形象、不要变成动物，正面半身像，纯色浅色背景，"
        "适合作为绘本主角的设定图。"
    )
    return _image_edit(b64, prompt, save_path, max_retries, "SF_CHAR_IMAGE_RATE_LIMIT", "SF_CHAR_IMAGE_FAILED")


def generate_page_image(character_image_abs: str, scene_prompt: str, save_path: str, max_retries: int = 3) -> str:
    """以已确认的角色形象图作参考，把主角放进指定场景，保证长相/发型/服装跨页一致。

    角色参考图统一转 JPEG 后以 data URI 传入 Qwen-Image-Edit，模型按指令保持主角不变、
    只更换场景与姿势；场景中的其他人物/小动物按 scene_prompt 描述绘制。
    """
    with open(character_image_abs, "rb") as f:
        b64 = _to_jpeg_b64(f.read())
    prompt = (
        "保持图中角色的长相、发型、发饰、服装完全一致，不要改变主角形象、也不要把主角变成动物或其他人。"
        "把主角放进以下场景，姿势与动作按场景自然调整；场景中的其他人物按描述绘制，不出现小动物："
        + scene_prompt
        + "。整体统一为温暖水彩童趣风，柔和低饱和色彩，圆润可爱。"
    )
    return _image_edit(b64, prompt, save_path, max_retries, "SF_PAGE_IMAGE_RATE_LIMIT", "SF_PAGE_IMAGE_FAILED")


def generate_audio(text: str, save_path: str, gender: str = "女孩") -> str:
    """TTS：按性别选音色，调用硅基流动 → 保存 mp3 到本地 → 返回文件绝对路径。"""
    if gender == "男孩":
        voice = settings.siliconflow_tts_voice_boy
        instruction = settings.siliconflow_tts_instruction_boy
    else:
        voice = settings.siliconflow_tts_voice_girl
        instruction = settings.siliconflow_tts_instruction_girl
    client = _client()
    try:
        r = client.post(
            "/audio/speech",
            json={
                "model": settings.siliconflow_tts_model,
                "input": f"{instruction}<|endofprompt|>{text}",
                "voice": voice,
                "response_format": "mp3",
            },
        )
        r.raise_for_status()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(r.content)
        cost_service.record(settings.siliconflow_tts_model, "tts", count=1)
        return save_path
    except MediaError:
        raise
    except Exception as e:  # noqa: BLE001
        raise MediaError("SF_TTS_FAILED", type(e).__name__)
    finally:
        client.close()


def rel_path(abs_path: str) -> str:
    """绝对路径 → 可访问的 URL 相对路径（/story_assets/...）。"""
    rel = os.path.relpath(abs_path, ASSETS_DIR)
    return "/story_assets/" + rel.replace(os.sep, "/")


def abs_path(rel_url: str) -> str:
    """URL 相对路径（/story_assets/...）→ 磁盘绝对路径。"""
    return os.path.join(ASSETS_DIR, rel_url.removeprefix("/story_assets/"))

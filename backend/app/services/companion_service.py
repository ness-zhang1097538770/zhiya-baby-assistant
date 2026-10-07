"""智慧陪伴智能体：情绪识别 + 陪伴脚本生成 + 语音合成。"""
import os
import uuid

from app.services import llm, media
from app.services.prompts.companion_prompt import build_companion_messages, build_emotion_messages

COMPANION_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "companion_assets")
MODES = {"separation", "emotion", "sleep"}


def _parse_emotion(data: dict) -> dict:
    emotion = str(data.get("emotion") or "其他").strip() or "其他"
    mode = str(data.get("mode") or "sleep").strip()
    if mode not in MODES:
        mode = "sleep"
    suggestion = str(data.get("suggestion") or "").strip()
    return {"emotion": emotion, "mode": mode, "suggestion": suggestion}


def analyze_emotion(text: str) -> dict:
    data, _ = llm.chat_json(build_emotion_messages(text))
    return _parse_emotion(data)


def _parse_script(data: dict) -> dict:
    title = str(data.get("title") or "陪伴").strip()
    segments: list[str] = []
    raw = data.get("segments")
    if isinstance(raw, list):
        for s in raw:
            if isinstance(s, str) and s.strip():
                segments.append(s.strip())
    if not segments:
        segments = ["宝贝，我在这里陪着你。"]
    breathing = data.get("breathing") or {}
    try:
        b_in = max(1, min(10, int(breathing.get("in", 4))))
    except (TypeError, ValueError):
        b_in = 4
    try:
        b_out = max(1, min(10, int(breathing.get("out", 4))))
    except (TypeError, ValueError):
        b_out = 4
    return {"title": title, "segments": segments, "breathing": {"in": b_in, "out": b_out}}


def generate_companion(
    mode: str,
    child_nickname: str | None = None,
    situation: str | None = None,
    gender: str = "女孩",
) -> dict:
    if mode not in MODES:
        mode = "sleep"
    data, _ = llm.chat_json(build_companion_messages(mode, child_nickname, situation))
    script = _parse_script(data)
    # 整段语音合成（朗读稿 = 陪伴脚本，保持一致）
    full_text = "。".join(script["segments"])
    os.makedirs(COMPANION_ASSETS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:12]}.mp3"
    abs_path = media.generate_audio(full_text, os.path.join(COMPANION_ASSETS_DIR, filename), gender=gender)
    rel = os.path.relpath(abs_path, COMPANION_ASSETS_DIR)
    script["audio_url"] = "/companion_assets/" + rel.replace(os.sep, "/")
    return script

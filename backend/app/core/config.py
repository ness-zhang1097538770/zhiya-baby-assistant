"""应用配置：从环境变量 / .env 读取，不含秘密默认值。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout: float = 60.0
    db_path: str = "data/app.db"

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_embedding_model: str = "BAAI/bge-m3"
    siliconflow_image_model: str = "Kwai-Kolors/Kolors"
    siliconflow_character_image_model: str = "Qwen/Qwen-Image-Edit"  # 照片转绘本角色形象
    siliconflow_tts_model: str = "FunAudioLLM/CosyVoice2-0.5B"
    siliconflow_tts_voice_girl: str = "FunAudioLLM/CosyVoice2-0.5B:diana"  # 女孩：欢快女声
    siliconflow_tts_voice_boy: str = "FunAudioLLM/CosyVoice2-0.5B:david"   # 男孩：欢快男声
    siliconflow_tts_instruction_girl: str = "用甜甜的、奶声奶气的、柔柔的语气朗读"
    siliconflow_tts_instruction_boy: str = "用奶声奶气的、活泼的小男孩声音朗读"

    # ===== 医疗通道：Baichuan-M3-Plus（问育儿）=====
    # 默认关闭。确认效果后把 medical_enabled 置 true 并按比例放量。
    baichuan_api_key: str = ""
    baichuan_base_url: str = "https://api.baichuan-ai.com/v1"
    baichuan_model: str = "Baichuan-M3-Plus"
    baichuan_timeout: float = 60.0
    baichuan_temperature: float = 0.2

    medical_enabled: bool = False          # 总开关，出问题秒级关停
    medical_rollout_percent: int = 0       # 0-100，按 child_id 稳定分桶
    medical_whitelist_ids: str = ""        # 强制开启的 child_id，逗号分隔，如 "1,2,3"
    medical_semi_categories: bool = False  # 是否把「健康监测/伤害预防」也算医疗主题

    # 故事插画/朗读资源存放目录；留空则用默认 data/story_assets（测试可覆盖隔离）
    assets_dir: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

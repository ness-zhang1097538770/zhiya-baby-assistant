"""硅基流动 Embedding 服务（语义检索用）。"""
import httpx

from app.core.config import settings


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """把文本批量转为向量；无 Key 或调用失败返回 None（调用方降级）。"""
    if not settings.siliconflow_api_key or not texts:
        return None
    try:
        r = httpx.post(
            f"{settings.siliconflow_base_url}/embeddings",
            headers={"Authorization": f"Bearer {settings.siliconflow_api_key}"},
            json={"model": settings.siliconflow_embedding_model, "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        data = sorted(r.json().get("data", []), key=lambda d: d.get("index", 0))
        return [d.get("embedding") for d in data if d.get("embedding")]
    except Exception:
        return None

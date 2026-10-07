"""FastAPI 入口。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, children, companion, events, facts, intent, qa, reminders, stories, agent, billing, ads, analytics
from app.core.errors import AppError
from app.db import Base, SessionLocal, engine
from app.services.families import ensure_bootstrap
from app.services.media import ASSETS_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_bootstrap(db)
    finally:
        db.close()
    yield


app = FastAPI(title="知芽 API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def no_cache(request: Request, call_next):
    """开发期禁用缓存，避免浏览器拿到旧版页面。"""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.exception_handler(AppError)
def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(HTTPException)
def http_error_handler(request: Request, exc: HTTPException):
    # 统一错误结构：{"error": {"code", "message"}}，不泄露堆栈
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(detail)}},
    )


@app.exception_handler(RequestValidationError)
def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "请求参数不合法"}},
    )


app.include_router(auth.router)
app.include_router(children.router)
app.include_router(companion.router)
app.include_router(intent.router)
app.include_router(qa.router)
app.include_router(events.router)
app.include_router(reminders.router)
app.include_router(facts.router)
app.include_router(stories.router)
app.include_router(agent.router)
app.include_router(billing.router)
app.include_router(ads.router)
app.include_router(analytics.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


# 故事插画/音频静态目录（必须在 "/" 挂载之前）
os.makedirs(ASSETS_DIR, exist_ok=True)
app.mount("/story_assets", StaticFiles(directory=ASSETS_DIR), name="story_assets")

# 宝宝头像静态目录
AVATARS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "avatars")
os.makedirs(AVATARS_DIR, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=AVATARS_DIR), name="avatars")

# 陪伴语音静态目录
COMPANION_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "companion_assets")
os.makedirs(COMPANION_DIR, exist_ok=True)
app.mount("/companion_assets", StaticFiles(directory=COMPANION_DIR), name="companion_assets")

# 最小验收界面（必须放在所有 API 路由之后，避免拦截 /api 路径）
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

"""统一错误结构：{"error": {"code", "message"}}。"""
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status


def error_response(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
    )


def error_payload(code: str, message: str) -> dict:
    """用于 SSE error 事件的统一结构。"""
    return {"error": {"code": code, "message": message}}

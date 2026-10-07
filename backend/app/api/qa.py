"""育儿问答接口（SSE 流式）。"""
import json
from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_family_id, get_owned_child
from app.core.errors import AppError, error_payload
from app.db import get_db
from app.models.models import Child, Conversation, Message
from app.schemas.schemas import QARequest
from app.services import qa_service
from app.services.llm import LLMError

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_stream(text: str, size: int = 24) -> Generator[str, None, None]:
    for i in range(0, len(text), size):
        yield _sse("chunk", {"text": text[i : i + size]})


@router.post("")
def ask(
    payload: QARequest,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    child = get_owned_child(db, payload.child_id, family_id)

    # 会话归属校验
    if payload.conversation_id is not None:
        conversation = db.get(Conversation, payload.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail={"error": {"code": "CONV_NOT_FOUND", "message": "会话不存在"}})
        if conversation.child_id != child.id:
            raise HTTPException(status_code=400, detail={"error": {"code": "CONV_MISMATCH", "message": "会话不属于该儿童"}})
    else:
        conversation = Conversation(child_id=child.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # 持久化用户消息
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.question))
    db.commit()

    def event_stream() -> Generator[str, None, None]:
        try:
            result = qa_service.answer_question(db, child, payload.question, conversation)
        except LLMError as e:
            yield _sse("error", {**error_payload(e.code, e.message), "conversation_id": conversation.id})
            return
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {**error_payload("INTERNAL_ERROR", f"服务内部错误：{type(e).__name__}"), "conversation_id": conversation.id})
            return

        # 持久化助手消息
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=result["answer"],
                risk_level=result["risk_level"],
                sources_json=json.dumps(result["sources"], ensure_ascii=False),
                followup_count=result["followup_count"],
            )
        )
        db.commit()

        # 流式输出答案文本 + done
        yield from _chunk_stream(result["answer"])
        done = {
            "conversation_id": conversation.id,
            "risk_level": result["risk_level"],
            "answer": result["answer"],
            "conclusion": result["conclusion"],
            "actions": result["actions"],
            "evidence": result["evidence"],
            "red_flags": result["red_flags"],
            "disclaimer": result["disclaimer"],
            "followup_question": result["followup_question"],
            "followup_count": result["followup_count"],
            "sources": result["sources"],
        }
        yield _sse("done", done)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations")
def list_conversations(
    child_id: int = Query(...),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """列出某个儿童的历史会话，title 取首条用户消息前 24 字。"""
    get_owned_child(db, child_id, family_id)
    convs = (
        db.query(Conversation)
        .filter(Conversation.child_id == child_id)
        .order_by(Conversation.id.desc())
        .all()
    )
    items = []
    for c in convs:
        first_user = (
            db.query(Message)
            .filter(Message.conversation_id == c.id, Message.role == "user")
            .order_by(Message.id)
            .first()
        )
        text = (first_user.content or "").strip() if first_user else ""
        title = text[:24] + ("…" if len(text) > 24 else "") if text else "新会话"
        items.append(
            {
                "id": c.id,
                "child_id": c.child_id,
                "title": title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
        )
    return {"items": items}


@router.get("/conversations/{conversation_id}")
def conversation_history(
    conversation_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONV_NOT_FOUND", "message": "会话不存在"}})
    # 会话归属校验：属于当前家庭才可读
    child = db.get(Child, conversation.child_id)
    if child is None or child.family_id != family_id:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONV_NOT_FOUND", "message": "会话不存在"}})
    msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id).all()
    return {
        "conversation_id": conversation.id,
        "child_id": conversation.child_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "risk_level": m.risk_level,
                "sources": json.loads(m.sources_json) if m.sources_json else [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }


def _owned_conversation(db: Session, conversation_id: int, family_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONV_NOT_FOUND", "message": "会话不存在"}})
    child = db.get(Child, conversation.child_id)
    if child is None or child.family_id != family_id:
        raise HTTPException(status_code=404, detail={"error": {"code": "CONV_NOT_FOUND", "message": "会话不存在"}})
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, conversation_id, family_id)
    db.query(Message).filter(Message.conversation_id == conversation.id).delete(synchronize_session=False)
    db.delete(conversation)
    db.commit()


@router.delete("/conversations", status_code=204)
def delete_all_conversations(
    child_id: int = Query(...),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    get_owned_child(db, child_id, family_id)
    conv_ids = [c.id for c in db.query(Conversation).filter(Conversation.child_id == child_id).all()]
    if conv_ids:
        db.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.child_id == child_id).delete(synchronize_session=False)
    db.commit()

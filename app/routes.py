from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from app.config import settings
from app.handler.chat_handler import handle_chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(default="", description="User message content")
    thread_id: Optional[str] = Field(default=None, description="Unique conversation thread ID")
    agent_type: str = Field(default="auto", description="Target agent type (auto, news, email, etc.)")


@router.get("/")
def index():
    logger.debug("Received request on GET /")
    return {"message": "Zimbo AI backend is running"}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/api/agent/status")
def agent_status():
    logger.debug("Received request on GET /api/agent/status")
    return {
        "status": "ready" if settings.has_llm_key else "no-llm-key",
        "name": "Zimbo AI",
        "mode": "news-and-email",
        "model": settings.LLM_MODEL,
        "llm_configured": settings.has_llm_key,
    }


@router.post("/api/agent/chat")
def chat(payload: ChatRequest):
    message = payload.message
    thread_id = payload.thread_id or uuid4().hex
    if not isinstance(thread_id, str) or not thread_id.strip() or len(thread_id) > 128:
        logger.warning("Invalid thread_id received in chat request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id must be a non-empty string of at most 128 characters",
        )

    agent_type = payload.agent_type
    logger.info(
        f"Incoming chat request | thread_id: '{thread_id.strip()}' | agent_type: '{agent_type}' | message: '{message[:80]}...'"
    )

    try:
        result = handle_chat(message, thread_id.strip(), agent_type=agent_type)
    except Exception as e:
        logger.exception(f"Agent chat failed for thread_id '{thread_id.strip()}': {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="agent request failed",
        )

    if "error" in result:
        logger.warning(f"Chat request validation error: {result['error']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    logger.info(
        f"Chat completed successfully | route: '{result.get('route')}' | thread_id: '{thread_id.strip()}'"
    )
    return {
        "reply": result.get("answer", ""),
        "route": result.get("route", ""),
        "thread_id": thread_id.strip(),
    }


@router.post("/api/news/check-now")
def trigger_news_check():
    """Trigger an immediate background news check and dispatch job."""
    from app.services.scheduler import check_and_dispatch_news, sent_news_store

    logger.info("Manual trigger received for news monitoring check via POST /api/news/check-now")
    try:
        check_and_dispatch_news()
        sent_items = sent_news_store.load()
        logger.info(f"Manual news check completed | total sent records: {len(sent_items)}")
        return {
            "status": "success",
            "message": "Manual news check completed",
            "total_sent_records": len(sent_items),
        }
    except Exception as e:
        logger.exception(f"Manual news check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/api/news/sent")
def get_sent_news():
    """Get history of news articles dispatched via background scheduler."""
    from app.services.scheduler import sent_news_store

    items = sent_news_store.load()
    logger.debug(f"Fetched sent news history | total records: {len(items)}")
    return {
        "total": len(items),
        "items": items,
    }




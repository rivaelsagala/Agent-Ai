from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from app.config import settings
from app.handler.chat_handler import handle_chat

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return jsonify({"message": "Atlas AI email backend is running"})


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/api/agent/status")
def agent_status():
    return jsonify(
        {
            "status": "ready" if settings.has_llm_key else "no-llm-key",
            "name": "Atlas AI",
            "mode": "email-only",
            "model": settings.LLM_MODEL,
            "llm_configured": settings.has_llm_key,
        }
    )

@bp.post("/api/agent/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body must be an object"}), 400

    message = payload.get("message", "")
    thread_id = payload.get("thread_id") or uuid4().hex
    if not isinstance(thread_id, str) or not thread_id.strip() or len(thread_id) > 128:
        return jsonify(
            {"error": "thread_id must be a non-empty string of at most 128 characters"}
        ), 400

    agent_type = payload.get("agent_type", "auto")
    try:
        result = handle_chat(message, thread_id.strip(), agent_type=agent_type)
    except Exception:
        current_app.logger.exception("Agent chat failed")
        return jsonify({"error": "agent request failed"}), 502
    if "error" in result:
        return jsonify(result), 400
    return jsonify(
        {
            "reply": result.get("answer", ""),
            "route": result.get("route", ""),
            "thread_id": thread_id.strip(),
        }
    )


@bp.post("/api/news/check-now")
def trigger_news_check():
    """Trigger an immediate background news check and dispatch job."""
    from app.services.scheduler import check_and_dispatch_news, sent_news_store
    try:
        check_and_dispatch_news()
        sent_items = sent_news_store.load()
        return jsonify({
            "status": "success",
            "message": "Manual news check completed",
            "total_sent_records": len(sent_items)
        })
    except Exception as e:
        current_app.logger.exception("Manual news check failed")
        return jsonify({"error": str(e)}), 500


@bp.get("/api/news/sent")
def get_sent_news():
    """Get history of news articles dispatched via background scheduler."""
    from app.services.scheduler import sent_news_store
    items = sent_news_store.load()
    return jsonify({
        "total": len(items),
        "items": items
    })


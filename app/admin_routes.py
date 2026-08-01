"""Protected endpoints for setup, diagnostics, and manual monitoring runs."""
import secrets
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.config import settings
from app.database.postgres import DatabaseConfigurationError

admin_bp = Blueprint("market_admin", __name__)

CHANNEL_TYPES = {"telegram", "whatsapp", "email"}
CATEGORIES = {
    "disclosure",
    "financial_report",
    "corporate_action",
    "regulation",
    "monetary_policy",
    "market_event",
    "general",
}


def require_admin_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not settings.ADMIN_API_KEY:
            return jsonify({"error": "ADMIN_API_KEY is not configured"}), 503
        supplied = request.headers.get("X-Admin-Key", "")
        if not secrets.compare_digest(supplied, settings.ADMIN_API_KEY):
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped


def _service_error(exc: Exception):
    current_app.logger.exception("Market-news operation failed")
    status = 503 if isinstance(exc, DatabaseConfigurationError) else 500
    return jsonify({"error": str(exc)}), status


@admin_bp.get("/api/market/status")
@require_admin_key
def market_status():
    try:
        from app.market_runtime import get_repository

        return jsonify(get_repository().status_counts())
    except Exception as exc:
        return _service_error(exc)


@admin_bp.post("/api/monitor/run")
@require_admin_key
def run_monitor():
    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode", "cycle") if isinstance(payload, dict) else "cycle"
    try:
        from app.market_runtime import get_monitor_service, get_notification_service

        monitor = get_monitor_service()
        if mode == "cycle":
            result = monitor.run_cycle()
        elif mode == "collect":
            result = monitor.collect_due_sources()
        elif mode == "process":
            result = monitor.process_new_items()
        elif mode == "digest":
            result = monitor.create_digests(payload.get("period_key", "manual"))
        elif mode == "deliver":
            result = get_notification_service().dispatch_pending()
        else:
            return jsonify({"error": "invalid mode"}), 400
        return jsonify({"mode": mode, "result": result})
    except Exception as exc:
        return _service_error(exc)


@admin_bp.post("/api/notifications/test")
@require_admin_key
def test_notification():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    channel_type = payload.get("channel_type")
    destination = payload.get("destination")
    if channel_type not in CHANNEL_TYPES:
        return jsonify({"error": "invalid channel_type"}), 400
    if not isinstance(destination, str) or not destination.strip():
        return jsonify({"error": "destination is required"}), 400
    try:
        from app.market_runtime import get_notification_service

        result = get_notification_service().send_test(
            channel_type,
            destination.strip(),
            payload.get(
                "message",
                "Tes notifikasi Atlas AI Market News berhasil.",
            ),
            payload.get("channel_config") or {},
        )
        return jsonify(result)
    except Exception as exc:
        return _service_error(exc)


@admin_bp.post("/api/subscribers")
@require_admin_key
def create_subscriber():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body must be an object"}), 400

    display_name = payload.get("display_name")
    channel_type = payload.get("channel_type")
    destination = payload.get("destination")
    tickers = payload.get("tickers", [])
    receive_all = bool(payload.get("receive_all", False))
    minimum_impact = payload.get("minimum_impact", 3)
    categories = payload.get("categories", [])

    if not isinstance(display_name, str) or not display_name.strip():
        return jsonify({"error": "display_name is required"}), 400
    if channel_type not in CHANNEL_TYPES:
        return jsonify({"error": "invalid channel_type"}), 400
    if not isinstance(destination, str) or not destination.strip():
        return jsonify({"error": "destination is required"}), 400
    if not isinstance(tickers, list) or not all(isinstance(value, str) for value in tickers):
        return jsonify({"error": "tickers must be a list of strings"}), 400
    if not receive_all and not tickers:
        return jsonify({"error": "provide tickers or set receive_all=true"}), 400
    if (
        isinstance(minimum_impact, bool)
        or not isinstance(minimum_impact, int)
        or not 1 <= minimum_impact <= 5
    ):
        return jsonify({"error": "minimum_impact must be between 1 and 5"}), 400
    if (
        not isinstance(categories, list)
        or not all(category in CATEGORIES for category in categories)
    ):
        return jsonify({"error": "invalid categories"}), 400
    if not isinstance(payload.get("channel_config", {}), dict):
        return jsonify({"error": "channel_config must be an object"}), 400

    try:
        from app.market_runtime import get_repository

        result = get_repository().create_subscriber(
            display_name=display_name.strip(),
            channel_type=channel_type,
            destination=destination.strip(),
            tickers=tickers,
            receive_all=receive_all,
            minimum_impact=minimum_impact,
            categories=categories,
            is_verified=bool(payload.get("is_verified", False)),
            channel_config=payload.get("channel_config") or {},
        )
        return jsonify(result), 201
    except Exception as exc:
        return _service_error(exc)

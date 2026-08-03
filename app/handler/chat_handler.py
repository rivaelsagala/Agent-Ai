"""Request handlers that bridge HTTP layer and use-cases."""
from loguru import logger
from app.usecases.chat_usecase import chat


def handle_chat(message: str, thread_id: str, agent_type: str = "auto") -> dict:
    if not isinstance(message, str) or not message.strip():
        logger.warning(f"handle_chat validation failed: empty message from thread_id '{thread_id}'")
        return {"error": "message is required"}
    logger.debug(f"Handling chat request for thread_id '{thread_id}' (agent_type={agent_type})")
    return chat(message.strip(), thread_id, agent_type=agent_type)


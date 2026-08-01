"""Request handlers that bridge HTTP layer and use-cases."""
from app.usecases.chat_usecase import chat


def handle_chat(message: str, thread_id: str, agent_type: str = "auto") -> dict:
    if not isinstance(message, str) or not message.strip():
        return {"error": "message is required"}
    return chat(message.strip(), thread_id, agent_type=agent_type)

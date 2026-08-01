"""Use-case orchestration: high-level operations the API exposes."""
from app.service.agents.email_agent import run_email_agent
from app.service.database.store import chat_history


def chat(message: str, thread_id: str) -> dict:
    """Run the email agent and persist the exchange."""
    answer = run_email_agent(message, thread_id)
    record = {
        "thread_id": thread_id,
        "message": message,
        "route": "email",
        "answer": answer,
    }
    chat_history.append(record)
    return record

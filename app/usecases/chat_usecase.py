"""Use-case orchestration: high-level operations the API exposes."""
from loguru import logger
from app.services.agents.email_agent import run_email_agent
from app.services.agents.news_agent import run_news_agent
from app.services.agents.supervisor_agent import route_message
from app.services.database.store import chat_history


def chat(message: str, thread_id: str, agent_type: str = "auto") -> dict:
    """Run the appropriate agent (news/email/auto) and persist the exchange."""

    # Jika agent_type sudah ditentukan eksplisit oleh caller, langsung gunakan.
    # Jika "auto", serahkan keputusan routing kepada LLM Supervisor Agent.
    if agent_type == "news":
        route = "news"
    elif agent_type == "email":
        route = "email"
    else:
        # LLM Supervisor Agent memutuskan routing secara cerdas
        logger.info(f"Invoking LLM Supervisor Agent for routing | thread_id: '{thread_id}'")
        route = route_message(message)

    if route == "news":
        logger.info(f"Routing query to NEWS AGENT | thread_id: '{thread_id}'")
        answer = run_news_agent(message, thread_id)
    else:
        logger.info(f"Routing query to EMAIL AGENT | thread_id: '{thread_id}'")
        answer = run_email_agent(message, thread_id)

    record = {
        "thread_id": thread_id,
        "message": message,
        "route": route,
        "answer": answer,
    }
    chat_history.append(record)
    logger.debug(f"Chat history record saved for thread_id '{thread_id}' (route={route})")
    return record

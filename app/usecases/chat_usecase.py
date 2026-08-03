"""Use-case orchestration: high-level operations the API exposes."""
from loguru import logger
from app.services.agents.email_agent import run_email_agent
from app.services.agents.news_agent import run_news_agent
from app.services.database.store import chat_history


def chat(message: str, thread_id: str, agent_type: str = "auto") -> dict:
    """Run the appropriate agent (news/email/auto) and persist the exchange."""
    lowered = message.lower()
    
    # Auto-detect routing if agent_type is "auto"
    if agent_type == "news" or (
        agent_type == "auto"
        and any(
            k in lowered
            for k in [
                "berita",
                "saham",
                "idx",
                "ojk",
                "bank indonesia",
                "bi",
                "alert",
                "pasar",
                "keterbukaan",
            ]
        )
    ):
        logger.info(f"Routing query to NEWS AGENT | thread_id: '{thread_id}'")
        answer = run_news_agent(message, thread_id)
        route = "news"
    else:
        logger.info(f"Routing query to EMAIL AGENT | thread_id: '{thread_id}'")
        answer = run_email_agent(message, thread_id)
        route = "email"

    record = {
        "thread_id": thread_id,
        "message": message,
        "route": route,
        "answer": answer,
    }
    chat_history.append(record)
    logger.debug(f"Chat history record saved for thread_id '{thread_id}' (route={route})")
    return record


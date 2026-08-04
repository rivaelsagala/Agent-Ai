"""
supervisor_agent.py
LLM-based Supervisor Agent yang menggunakan LangGraph untuk memutuskan
agent mana (news / email) yang paling tepat menangani permintaan pengguna.

Menggantikan keyword-based routing (if "berita" in message) dengan
LLM reasoning yang lebih cerdas dan akurat.
"""
from functools import lru_cache
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated
from loguru import logger

from app.llm import get_llm


# ── State Schema ──────────────────────────────────────────────────────────────

class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    route: str  # "news" | "email"


# ── Routing Prompt ────────────────────────────────────────────────────────────

SUPERVISOR_PROMPT = """Kamu adalah Supervisor AI yang bertugas menentukan agent mana yang paling tepat untuk menangani permintaan pengguna.

Pilihan agent yang tersedia:
- **news** : Untuk semua pertanyaan atau permintaan terkait berita keuangan, pasar saham, emiten, IDX, OJK, Bank Indonesia, Bloomberg, analisis saham, sentimen pasar, notifikasi berita, atau alert pasar modal.
- **email** : Untuk semua permintaan mengirim, membaca, membalas, atau mengelola email. Juga sebagai default untuk percakapan umum yang tidak berhubungan dengan berita pasar.

Balas HANYA dengan satu kata: `news` atau `email`. Jangan tambahkan penjelasan apapun."""


# ── Supervisor Node ───────────────────────────────────────────────────────────

def supervisor_node(state: SupervisorState) -> dict:
    """LLM memutuskan routing: 'news' atau 'email'."""
    messages = state["messages"]
    user_message = messages[-1].content if messages else ""

    llm = get_llm(temperature=0)
    response = llm.invoke([
        SystemMessage(content=SUPERVISOR_PROMPT),
        HumanMessage(content=user_message),
    ])

    decision = response.content.strip().lower()
    # Sanitize: pastikan hanya nilai valid yang diterima
    route = "news" if "news" in decision else "email"
    logger.info(f"[Supervisor] LLM routing decision: '{decision}' → route='{route}'")
    return {"route": route}


# ── Build LangGraph Supervisor ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def build_supervisor() -> StateGraph:
    """Build dan compile LangGraph supervisor routing graph."""
    graph = StateGraph(SupervisorState)
    graph.add_node("supervisor", supervisor_node)
    graph.set_entry_point("supervisor")
    graph.add_edge("supervisor", END)
    return graph.compile()


# ── Public Interface ───────────────────────────────────────────────────────────

def route_message(message: str) -> Literal["news", "email"]:
    """
    Gunakan LLM Supervisor untuk memutuskan agent yang tepat.
    Returns: 'news' atau 'email'
    """
    supervisor = build_supervisor()
    result = supervisor.invoke({
        "messages": [HumanMessage(content=message)],
        "route": "email",  # default fallback
    })
    return result.get("route", "email")

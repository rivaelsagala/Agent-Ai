"""
news_agent.py
Agent LangGraph (ReAct-style) yang bertugas memantau, menganalisis,
dan mengirimkan berita pasar keuangan/saham (IDX, BI, OJK).
"""

from functools import lru_cache

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from app.llm import get_llm
from app.services.tools.news_tools import NEWS_TOOLS

SYSTEM_PROMPT = """Kamu adalah Asisten AI Analis Berita Pasar Saham & Ekonomi Indonesia (Zimbo Market AI).

Tools yang kamu miliki:
1. fetch_market_news: mengambil berita terbaru dari Bursa Efek Indonesia (IDX), Bank Indonesia (BI), atau OJK.
2. analyze_market_news: menganalisis dampak, sentimen, dan emiten (ticker) yang terpengaruh dari berita tertentu.
3. send_market_alert: mengirimkan alert / ringkasan berita ke pengguna via WhatsApp, Telegram, atau Email.

Aturan Kerja:
1. Jawab pertanyaan pengguna seputar berita pasar saham, ekonomi makro, atau regulasi keuangan dengan relevan dan akurat.
2. Saat mengambil berita pasar (fetch_market_news), sajikan ringkasan berita secara rapi, jelas, dan mudah dibaca.
3. Jika pengguna meminta analisis berita atau prediksi dampak ke emiten/saham tertentu, gunakan tool analyze_market_news.
4. Jika pengguna meminta untuk mengirim notifikasi atau alert berita ke WhatsApp, Telegram, atau Email, gunakan tool send_market_alert.
5. Selalu gunakan bahasa Indonesia yang profesional dan sopan.
"""


@lru_cache(maxsize=1)
def build_news_agent():
    """Membuat instance agent LangGraph untuk berita pasar."""
    logger.info("Building News Agent ReAct graph...")
    llm = get_llm(temperature=0)
    checkpointer = MemorySaver()

    agent = create_react_agent(
        model=llm,
        tools=NEWS_TOOLS,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    return agent


def run_news_agent(user_input: str, thread_id: str) -> str:
    """Kirim pesan ke news agent dan kembalikan balasan terakhirnya."""
    if not thread_id:
        logger.error("Value error: thread_id is missing for run_news_agent")
        raise ValueError("thread_id is required for the news agent")

    logger.info(f"Executing News Agent for thread_id '{thread_id}' | input: '{user_input[:60]}...'")
    agent = build_news_agent()
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
    )
    reply = result["messages"][-1].content
    logger.info(f"News Agent response generated for thread_id '{thread_id}' | length: {len(reply)}")
    return reply


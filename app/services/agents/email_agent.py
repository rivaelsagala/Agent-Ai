"""
email_agent.py
Agent LangGraph (ReAct-style) yang bisa mengirim, membaca, dan mencari
email lewat tools di email_tools.py.

Environment variables yang dibutuhkan (.env):
    OPENROUTER_API_KEY=sk-or-...
    OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS
    IMAP_HOST, IMAP_PORT, IMAP_USERNAME, IMAP_PASSWORD

    Agent ini menjadi satu-satunya agent yang dipakai oleh endpoint chat.
"""

from functools import lru_cache

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.llm import get_llm
from app.service.tools.email_tools import EMAIL_TOOLS

SYSTEM_PROMPT = """Kamu adalah asisten AI yang bertugas mengelola email pengguna melalui Gmail.

Tools yang kamu punya:
- send_email: mengirim email baru (to, subject, body, cc, bcc, is_html)
- read_emails: membaca email terbaru dari sebuah folder/mailbox
- get_email_detail: mengambil isi lengkap satu email berdasarkan ID
- search_emails: mencari email berdasarkan kata kunci di subjek/pengirim/penerima/isi
- mark_email_as_read: menandai email sebagai sudah dibaca

Aturan kerja:
1. Sebelum benar-benar mengirim email (memanggil tool send_email), tampilkan
   dulu draft-nya (penerima, subjek, isi) ke pengguna dan minta konfirmasi,
   kecuali pengguna sudah secara eksplisit menyuruh "langsung kirim".
2. Saat pengguna minta membaca atau mencari email, gunakan tool yang sesuai
   lalu rangkum hasilnya dengan rapi dan mudah dibaca (jangan tampilkan
   ID mentah IMAP kecuali relevan/diminta).
3. Jangan mengarang isi email atau status pengiriman. Kalau tool mengembalikan
   error, sampaikan error tersebut apa adanya ke pengguna beserta saran
   perbaikannya jika memungkinkan.
4. Gunakan bahasa yang sama dengan bahasa yang dipakai pengguna dalam percakapan.
"""


@lru_cache(maxsize=1)
def build_email_agent():
    """Membuat instance agent LangGraph yang siap dipakai (invoke/stream)."""
    llm = get_llm(temperature=0)

    # MemorySaver -> agent ingat riwayat percakapan selama proses berjalan.
    # Untuk persist ke disk/DB, ganti dengan checkpointer lain (mis. SqliteSaver).
    checkpointer = MemorySaver()

    agent = create_react_agent(
        model=llm,
        tools=EMAIL_TOOLS,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    return agent


def run_email_agent(user_input: str, thread_id: str) -> str:
    """Kirim pesan ke email agent dan kembalikan balasan terakhirnya."""
    if not thread_id:
        raise ValueError("thread_id is required for the email agent")

    agent = build_email_agent()
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
    )
    return result["messages"][-1].content

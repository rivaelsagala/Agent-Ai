"""LangChain tools for market news fetching, analysis, and alerting."""
import json
from typing import List, Optional, Dict, Any
from langchain_core.tools import tool

from app.collectors.registry import CollectorRegistry
from app.market_models import CollectedNews, NewsAnalysis
from app.llm import get_llm
from app.config import settings
from app.channels.telegram import TelegramChannel
from app.channels.whatsapp import WhatsAppChannel
from app.channels.email import EmailChannel

# Known official news sources configuration
OFFICIAL_SOURCES = [
    {
        "code": "idx_news",
        "name": "Bursa Efek Indonesia (Berita)",
        "source_type": "idx_news",
        "base_url": "https://www.idx.co.id/id/berita/berita-pengumuman",
    },
    {
        "code": "idx_disclosure",
        "name": "Bursa Efek Indonesia (Keterbukaan Informasi)",
        "source_type": "idx_disclosure",
        "base_url": "https://www.idx.co.id/id/berita/keterbukaan-informasi",
    },
    {
        "code": "bank_indonesia",
        "name": "Bank Indonesia (Siaran Pers)",
        "source_type": "bank_indonesia",
        "base_url": "https://www.bi.go.id/id/publikasi/ruang-media/news-release/default.aspx",
    },
    {
        "code": "ojk",
        "name": "Otoritas Jasa Keuangan (Siaran Pers)",
        "source_type": "ojk",
        "base_url": "https://www.ojk.go.id/id/berita-dan-kegiatan/siaran-pers/default.aspx",
    },
]


@tool
def fetch_market_news(source_type: str = "all") -> str:
    """Fetch latest market news from official sources (idx_news, idx_disclosure, bank_indonesia, ojk, or all).
    
    Args:
        source_type: The source category to fetch from ('idx_news', 'idx_disclosure', 'bank_indonesia', 'ojk', or 'all').
    """
    registry = CollectorRegistry()
    items: List[CollectedNews] = []
    sources = OFFICIAL_SOURCES
    if source_type != "all":
        sources = [s for s in OFFICIAL_SOURCES if s["source_type"] == source_type or s["code"] == source_type]

    for source in sources:
        try:
            collector = registry.create(source)
            collected = collector.collect()
            items.extend(collected)
        except Exception as e:
            continue

    if not items:
        return "Tidak ditemukan berita baru saat ini dari sumber yang diminta."

    formatted = []
    for idx, item in enumerate(items[:10], 1):
        date_str = item.published_at.strftime("%Y-%m-%d %H:%M") if item.published_at else "Terbaru"
        formatted.append(f"{idx}. [{date_str}] {item.title}\n   URL: {item.canonical_url}\n   Ringkasan: {item.source_excerpt[:200]}")

    return "\n\n".join(formatted)


@tool
def analyze_market_news(news_text: str) -> str:
    """Analyze a market news headline or excerpt using AI to assess its impact, sentiment, and affected stock tickers.
    
    Args:
        news_text: The news title or content to analyze.
    """
    llm = get_llm(temperature=0)
    prompt = f"""Analisis berita pasar saham/ekonomi berikut dan kembalikan respon JSON persis dengan format:
{{
  "summary": "ringkasan singkat 1-2 kalimat",
  "impact_reason": "alasan dampak berita terhadap pasar atau emiten",
  "category": "Makroekonomi | Emiten | Regulasi | Industri",
  "impact_level": 1-5 (1 sangat rendah, 5 sangat tinggi),
  "sentiment": -1.0 sampai 1.0 (-1.0 sangat negatif, 0 netral, 1.0 sangat positif),
  "confidence": 0.0 sampai 1.0,
  "tickers": ["BBCA", "TLKM"] (daftar ticker saham terkait yang relevan, kosongkan jika tidak ada)
}}

Teks Berita:
{news_text}
"""
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return content
    except Exception as e:
        return f"Error saat menganalisis berita: {str(e)}"


@tool
def send_market_alert(channel: str, destination: str, title: str, message: str) -> str:
    """Send a market news alert or digest to a user via email, telegram, or whatsapp.
    
    Args:
        channel: The target channel ('email', 'telegram', or 'whatsapp').
        destination: Target recipient (email address, telegram chat_id, or whatsapp phone number).
        title: Alert subject/header.
        message: The alert message body to send.
    """
    ch = channel.lower().strip()
    full_message = f"🚨 {title}\n\n{message}"
    dest = (destination or "").strip()
    try:
        if ch == "email":
            email_ch = EmailChannel()
            if not dest or "@" not in dest or dest.lower() in ["saya", "email saya", "me", "my email"]:
                dest = settings.NOTIFICATION_EMAIL_TO
            res = email_ch.send(destination=dest, message=full_message, config={"subject": title})
            return f"Notifikasi Email berhasil dikirim ke {dest}"
        elif ch == "telegram":
            tg_ch = TelegramChannel()
            if not dest or not dest.lstrip("-").isdigit() or dest.lower() in ["saya", "telegram saya", "me", "my telegram"]:
                dest = settings.NOTIFICATION_TELEGRAM_TO
            res = tg_ch.send(destination=dest, message=full_message)
            return f"Notifikasi Telegram berhasil dikirim ke {dest}"
        elif ch == "whatsapp":
            wa_ch = WhatsAppChannel()
            if not dest or dest.lower() in ["saya", "wa saya", "whatsapp saya", "me"]:
                dest = settings.NOTIFICATION_WA_TO
            res = wa_ch.send(destination=dest, message=full_message)
            return f"Notifikasi WhatsApp berhasil dikirim ke {dest}"
        else:
            return f"Kanal '{channel}' tidak dikenali. Pilih antara: email, telegram, atau whatsapp."
    except Exception as e:
        return f"Gagal mengirim notifikasi via {channel}: {str(e)}"


NEWS_TOOLS = [
    fetch_market_news,
    analyze_market_news,
    send_market_alert,
]

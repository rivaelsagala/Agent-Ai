"""LangChain tools for market news fetching, analysis, and alerting."""
import json
from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from loguru import logger

from app.collectors.registry import CollectorRegistry
from app.collectors.base import format_indonesian_datetime
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
    {
        "code": "bloomberg",
        "name": "Bloomberg (Markets & Economics)",
        "source_type": "bloomberg",
        "base_url": "https://feeds.bloomberg.com/markets/news.rss",
    },
]


def analyze_news_item_structured(title: str, excerpt: str = "") -> Dict[str, Any]:
    """Perform structured AI analysis on a news item to assess affected stock tickers, impact direction (baik/buruk/netral), impact reason, and summary."""
    logger.info(f"Starting AI structured analysis for article: '{title[:70]}...'")
    try:
        llm = get_llm(temperature=0)
        news_text = f"Judul: {title}\nExcerpt/Ringkasan: {excerpt}" if excerpt else f"Judul: {title}"
        prompt = f"""Analisis berita pasar saham dan ekonomi Indonesia berikut secara seksama.
Identifikasi kode saham/emiten (tickers) yang terdampak, tentukan apakah dampaknya BAIK (positif), BURUK (negatif), atau NETRAL, berikan alasan dampak, serta ringkasan singkat.

Kembalikan jawaban HANYA DALAM FORMAT JSON tanpa penjelasan/teks tambahan di luar JSON:
{{
  "summary": "ringkasan singkat 1-2 kalimat mengenai inti berita",
  "impact_reason": "penjelasan mendalam mengenai alasan dampak positif/negatif/netral terhadap emiten atau pasar saham",
  "category": "Emiten | Makroekonomi | Regulasi | Perbankan | Industri",
  "impact_level": 3,
  "sentiment_score": 0.5,
  "dampak": "Baik (Positif 📈)",
  "tickers": ["BBCA", "TLKM"]
}}

Catatan penting untuk field "dampak":
- Gunakan persis "Baik (Positif 📈)" jika berita berdampak positif bagi emiten/pasar.
- Gunakan persis "Buruk (Negatif 📉)" jika berita berdampak negatif/buruk bagi emiten/pasar.
- Gunakan persis "Netral ⚖️" jika berita berdampak netral atau informatif umum.
- "tickers": isi dengan array kode saham 4 huruf (misal ["BBCA", "ANTM"]). Jika tidak ada emiten spesifik atau berita makro umum, kosongkan array `[]`.

Berita untuk dianalisis:
{news_text}
"""
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Strip markdown codeblock if present
        clean_content = content.strip()
        if clean_content.startswith("```"):
            lines = clean_content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_content = "\n".join(lines).strip()

        data = json.loads(clean_content)

        tickers = data.get("tickers", [])
        if not isinstance(tickers, list):
            tickers = [str(tickers)] if tickers else []

        sentiment_score = float(data.get("sentiment_score", 0.0))
        dampak = data.get("dampak")
        if not dampak:
            if sentiment_score > 0.1:
                dampak = "Baik (Positif 📈)"
            elif sentiment_score < -0.1:
                dampak = "Buruk (Negatif 📉)"
            else:
                dampak = "Netral ⚖️"

        result = {
            "summary": str(data.get("summary", title)),
            "impact_reason": str(data.get("impact_reason", "Tidak ada alasan dampak spesifik.")),
            "category": str(data.get("category", "General")),
            "impact_level": int(data.get("impact_level", 3)),
            "sentiment_score": sentiment_score,
            "dampak": dampak,
            "tickers": [str(t).upper().strip() for t in tickers if t]
        }
        logger.info(f"AI Analysis Result | Tickers: {result['tickers']} | Dampak: {result['dampak']} | Level: {result['impact_level']}")
        return result
    except Exception as e:
        logger.exception(f"Error during AI analysis of news item '{title[:50]}': {e}")
        return {
            "summary": title,
            "impact_reason": f"Analisis AI tidak tersedia: {str(e)}",
            "category": "General",
            "impact_level": 1,
            "sentiment_score": 0.0,
            "dampak": "Netral ⚖️",
            "tickers": []
        }


@tool
def fetch_market_news(source_type: str = "all") -> str:
    """Fetch latest market news from official sources (idx_news, idx_disclosure, bank_indonesia, ojk, or all).
    
    Args:
        source_type: The source category to fetch from ('idx_news', 'idx_disclosure', 'bank_indonesia', 'ojk', or 'all').
    """
    logger.info(f"Tool 'fetch_market_news' invoked with source_type='{source_type}'")
    registry = CollectorRegistry()
    items: List[CollectedNews] = []
    sources = OFFICIAL_SOURCES
    if source_type != "all":
        sources = [s for s in OFFICIAL_SOURCES if s["source_type"] == source_type or s["code"] == source_type]

    for source in sources:
        try:
            logger.debug(f"Collecting from source: {source.get('name')} ({source.get('code')})")
            collector = registry.create(source)
            collected = collector.collect()
            items.extend(collected)
            logger.debug(f"Collected {len(collected)} item(s) from {source.get('code')}")
        except Exception as e:
            logger.warning(f"Failed collecting from source '{source.get('code')}': {e}")
            continue

    if not items:
        logger.warning(f"No news items returned for source_type='{source_type}'")
        return "Tidak ditemukan berita baru saat ini dari sumber yang diminta."

    # Deduplicate items across sources by canonical_url and title
    unique_items: List[CollectedNews] = []
    seen_urls = set()
    seen_titles = set()
    for item in items:
        url = item.canonical_url.strip() if item.canonical_url else ""
        t_key = item.title.strip().lower() if item.title else ""
        if (url and url in seen_urls) or (t_key and t_key in seen_titles):
            continue
        if url:
            seen_urls.add(url)
        if t_key:
            seen_titles.add(t_key)
        unique_items.append(item)

    logger.info(f"Total unique news items collected across sources: {len(unique_items)}")

    formatted = []
    for idx, item in enumerate(unique_items[:10], 1):
        date_str = format_indonesian_datetime(item.published_at) if item.published_at else "Terbaru"
        formatted.append(f"{idx}. [{date_str}] {item.title}\n   URL: {item.canonical_url}\n   Ringkasan: {item.source_excerpt[:200]}")

    return "\n\n".join(formatted)


@tool
def analyze_market_news(news_text: str) -> str:
    """Analyze a market news headline or excerpt using AI to assess its impact, sentiment, and affected stock tickers.
    
    Args:
        news_text: The news title or content to analyze.
    """
    logger.info(f"Tool 'analyze_market_news' invoked for text length: {len(news_text)}")
    analysis = analyze_news_item_structured(title=news_text)
    return json.dumps(analysis, ensure_ascii=False, indent=2)


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
    logger.info(f"Tool 'send_market_alert' invoked | channel: '{ch}' | destination: '{dest}' | title: '{title[:50]}...'")
    try:
        if ch == "email":
            email_ch = EmailChannel()
            if not dest or "@" not in dest or dest.lower() in ["saya", "email saya", "me", "my email"]:
                dest = settings.NOTIFICATION_EMAIL_TO
            res = email_ch.send(destination=dest, message=full_message, config={"subject": title})
            logger.info(f"Email alert delivered successfully to {dest}")
            return f"Notifikasi Email berhasil dikirim ke {dest}"
        elif ch == "telegram":
            tg_ch = TelegramChannel()
            if not dest or not dest.lstrip("-").isdigit() or dest.lower() in ["saya", "telegram saya", "me", "my telegram"]:
                dest = settings.NOTIFICATION_TELEGRAM_TO
            res = tg_ch.send(destination=dest, message=full_message)
            logger.info(f"Telegram alert delivered successfully to {dest}")
            return f"Notifikasi Telegram berhasil dikirim ke {dest}"
        elif ch == "whatsapp":
            wa_ch = WhatsAppChannel()
            if not dest or dest.lower() in ["saya", "wa saya", "whatsapp saya", "me"]:
                dest = settings.NOTIFICATION_WA_TO
            res = wa_ch.send(destination=dest, message=full_message)
            logger.info(f"WhatsApp alert delivered successfully to {dest}")
            return f"Notifikasi WhatsApp berhasil dikirim ke {dest}"
        else:
            logger.warning(f"Unrecognized notification channel: '{channel}'")
            return f"Kanal '{channel}' tidak dikenali. Pilih antara: email, telegram, atau whatsapp."
    except Exception as e:
        logger.exception(f"Failed sending alert via '{channel}' to '{dest}': {e}")
        return f"Gagal mengirim notifikasi via {channel}: {str(e)}"



NEWS_TOOLS = [
    fetch_market_news,
    analyze_market_news,
    send_market_alert,
]


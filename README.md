# Zimbo AI — Autonomous Multi-Agent Backend

Backend Python berbasis **FastAPI** dan **LangGraph** untuk asisten email dan intelijen berita keuangan. Agent dapat mengumpulkan berita pasar, menganalisis sentimen, dispatch alert multi-channel (Telegram & Email), serta mengelola email via SMTP/IMAP.

## Arsitektur

```text
HTTP request / Swagger UI
    |
    v
FastAPI APIRouter -> chat use case -> Multi-Agent System -> Tools (News/Email)
                                        |
                                        +-> MemorySaver per thread_id
```

## Tech stack

- **FastAPI & Uvicorn** untuk High-Performance Asynchronous HTTP API & Swagger Docs
- OpenRouter sebagai penyedia LLM
- LangGraph & LangChain untuk ReAct agent dan memori percakapan
- APScheduler untuk monitoring berita berkala (background worker 24/7)
- Telegram Bot API & SMTP untuk pengiriman notifikasi/email
- Loguru untuk structured logging

## Setup

```bash
pip install -r requirements.txt
copy .env.example .env
```

Isi kredensial OpenRouter, Telegram, SMTP, dan IMAP di `.env`.

## Menjalankan

```bash
python run.py
```

Server berjalan di `http://127.0.0.1:5000`.
Dokumentasi API Interaktif (Swagger UI) dapat diakses langsung di: **`http://127.0.0.1:5000/docs`**

## Endpoint API

| Method | Path | Deskripsi |
|--------|------|-----------|
| GET | `/` | Root info |
| GET | `/health` | Health check |
| GET | `/api/agent/status` | Status agent dan LLM model |
| POST | `/api/agent/chat` | Menjalankan multi-agent chat |
| POST | `/api/news/check-now` | Trigger manual monitoring berita & alert |
| GET | `/api/news/sent` | Riwayat berita yang telah dikirim |

Contoh request chat:

```bash
curl -X POST http://127.0.0.1:5000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Cari berita pasar saham terbaru hari ini"}'
```

## Struktur folder

```text
app/
  config.py, llm.py, logger.py # Konfigurasi, LLM client, & Loguru logger
  routes.py, __init__.py     # FastAPI app factory, lifespan, & APIRouter
  collectors/                # News Web Collectors (IDX, BI, OJK)
  channels/                  # Multi-channel Telegram & Email handlers
  handler/                   # Jembatan HTTP ke use cases
  usecases/                  # Orkestrasi aplikasi & Agent runner
  services/                  # Background APScheduler & Stores
```


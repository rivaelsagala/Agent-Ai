# Atlas AI — Email Agent Backend

Backend Python berbasis Flask dan LangGraph untuk asisten email. Agent dapat
membuat draft, mengirim, membaca, mencari, dan menandai email melalui SMTP/IMAP.

## Arsitektur

```text
HTTP request
    |
    v
Flask route -> chat use case -> Email agent -> SMTP/IMAP tools
                                  |
                                  +-> MemorySaver per thread_id
```

## Tech stack

- Flask untuk HTTP API
- OpenRouter sebagai penyedia LLM
- LangGraph untuk ReAct email agent dan memori percakapan
- SMTP untuk mengirim email
- IMAP untuk membaca dan mencari email
- JSON store untuk riwayat chat sederhana

## Setup

```bash
pip install -r requirements.txt
copy .env.example .env
```

Isi kredensial OpenRouter, SMTP, dan IMAP di `.env`. Untuk Gmail dengan 2FA,
gunakan App Password, bukan password akun biasa.

## Menjalankan

```bash
python run.py
```

Server berjalan di `http://127.0.0.1:5000` secara default.

## Endpoint API

| Method | Path | Deskripsi |
|--------|------|-----------|
| GET | `/health` | Health check |
| GET | `/api/agent/status` | Status agent dan model |
| POST | `/api/agent/chat` | Menjalankan email agent |

Contoh request pertama:

```bash
curl -X POST http://127.0.0.1:5000/api/agent/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Buatkan draft email untuk dosen saya\"}"
```

Respons mengandung `thread_id`. Kirim ID yang sama pada pesan berikutnya agar
agent mengingat draft dan dapat memproses konfirmasi:

```json
{
  "message": "Ya, kirim",
  "thread_id": "thread-id-dari-respons-sebelumnya"
}
```

## Testing

```bash
python -m pytest tests/ -q
```

Tes menggunakan mock sehingga tidak menghubungi OpenRouter, SMTP, atau IMAP.

## Struktur folder

```text
app/
  config.py, llm.py          # konfigurasi dan client LLM
  routes.py, __init__.py     # Flask app factory dan endpoint
  handler/                   # jembatan HTTP ke use case
  usecases/                  # orkestrasi aplikasi
  service/
    agents/                  # email agent
    tools/                   # SMTP/IMAP tools
    database/                # JSON chat history
data/
  chat_history.json
tests/
```

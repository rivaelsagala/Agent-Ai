"""
email_tools.py
Kumpulan LangChain Tools untuk mengirim email (SMTP) dan membaca/mencari
email (IMAP). Didesain untuk dipakai oleh agent LangGraph di email_agent.py.

Environment variables yang dibutuhkan (.env):
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS
    IMAP_HOST, IMAP_PORT, IMAP_USERNAME, IMAP_PASSWORD

PENTING (Gmail): SMTP_PASSWORD / IMAP_PASSWORD harus App Password
(bukan password akun biasa) jika akun memakai 2FA.
Buat di: https://myaccount.google.com/apppasswords
"""

import os
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header
from typing import Optional, List

from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()
NETWORK_TIMEOUT = float(os.getenv("EMAIL_NETWORK_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# Konfigurasi dari environment variables
# ---------------------------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USERNAME = os.getenv("IMAP_USERNAME")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")


# ---------------------------------------------------------------------------
# Helper functions (internal, bukan tools)
# ---------------------------------------------------------------------------
def _decode_mime_header(raw_header: Optional[str]) -> str:
    """Decode header email (Subject/From/To) yang mungkin ter-encode MIME."""
    if not raw_header:
        return ""
    decoded_parts = decode_header(raw_header)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(encoding or "utf-8", errors="ignore")
        else:
            result += part
    return result


def _get_email_body(msg: "email.message.Message") -> str:
    """Ambil isi (body) email, prioritas text/plain lalu fallback text/html."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                    break
                except Exception:
                    continue
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        body = part.get_payload(decode=True).decode(charset, errors="ignore")
                        break
                    except Exception:
                        continue
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="ignore")
        except Exception:
            body = str(msg.get_payload())
    return body


def _connect_imap() -> imaplib.IMAP4_SSL:
    if not IMAP_USERNAME or not IMAP_PASSWORD:
        raise ValueError(
            "IMAP_USERNAME atau IMAP_PASSWORD belum diset di environment variable."
        )
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=NETWORK_TIMEOUT)
    conn.login(IMAP_USERNAME, IMAP_PASSWORD)
    return conn


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------
@tool
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    is_html: bool = False,
) -> str:
    """
    Kirim email baru menggunakan SMTP (Gmail).

    Args:
        to: Alamat email tujuan. Pisahkan dengan koma untuk banyak penerima.
        subject: Subjek email.
        body: Isi email.
        cc: (opsional) alamat CC, pisahkan dengan koma.
        bcc: (opsional) alamat BCC, pisahkan dengan koma.
        is_html: Jika True, body dikirim sebagai HTML, jika False sebagai plain text.

    Returns:
        Pesan status pengiriman (berhasil atau error).
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return "Error: SMTP_USERNAME atau SMTP_PASSWORD belum diset di environment variable."

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc

        msg.attach(MIMEText(body, "html" if is_html else "plain"))

        recipients = [addr.strip() for addr in to.split(",")]
        if cc:
            recipients += [addr.strip() for addr in cc.split(",")]
        if bcc:
            recipients += [addr.strip() for addr in bcc.split(",")]

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=NETWORK_TIMEOUT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, recipients, msg.as_string())

        return f"Email berhasil dikirim ke {to}"

    except smtplib.SMTPAuthenticationError:
        return (
            "Error: Autentikasi SMTP gagal. Pastikan SMTP_PASSWORD adalah "
            "App Password Gmail (bukan password akun biasa)."
        )
    except Exception as e:
        return f"Error saat mengirim email: {str(e)}"


@tool
def read_emails(folder: str = "INBOX", limit: int = 10, unread_only: bool = False) -> str:
    """
    Baca email terbaru dari suatu folder/mailbox menggunakan IMAP.

    Args:
        folder: Nama folder/mailbox, default "INBOX".
        limit: Jumlah maksimal email yang diambil (yang terbaru dulu).
        unread_only: Jika True, hanya ambil email yang belum dibaca.

    Returns:
        Ringkasan setiap email (ID, dari, subjek, tanggal, cuplikan isi),
        dipisahkan oleh "---".
    """
    try:
        conn = _connect_imap()
        conn.select(folder)

        search_criteria = "UNSEEN" if unread_only else "ALL"
        status, data = conn.search(None, search_criteria)
        if status != "OK":
            conn.logout()
            return f"Gagal mencari email di folder {folder}"

        email_ids = data[0].split()
        if not email_ids:
            conn.logout()
            return f"Tidak ada email {'belum dibaca ' if unread_only else ''}di folder {folder}"

        email_ids = email_ids[-limit:]
        email_ids.reverse()  # terbaru dulu

        results: List[str] = []
        for eid in email_ids:
            status, msg_data = conn.fetch(eid, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_mime_header(msg.get("Subject"))
            from_ = _decode_mime_header(msg.get("From"))
            date_ = msg.get("Date")
            body = _get_email_body(msg)
            snippet = body.strip().replace("\n", " ")[:200]

            results.append(
                f"ID: {eid.decode()}\nDari: {from_}\nSubjek: {subject}\n"
                f"Tanggal: {date_}\nCuplikan: {snippet}"
            )

        conn.logout()
        return "\n---\n".join(results)

    except Exception as e:
        return f"Error saat membaca email: {str(e)}"


@tool
def get_email_detail(email_id: str, folder: str = "INBOX") -> str:
    """
    Ambil isi lengkap sebuah email berdasarkan ID.

    Args:
        email_id: ID email (didapat dari hasil read_emails atau search_emails).
        folder: Nama folder/mailbox, default "INBOX".

    Returns:
        Isi lengkap email (dari, kepada, subjek, tanggal, body lengkap).
    """
    try:
        conn = _connect_imap()
        conn.select(folder)

        status, msg_data = conn.fetch(email_id.encode(), "(RFC822)")
        if status != "OK" or not msg_data or msg_data[0] is None:
            conn.logout()
            return f"Email dengan ID {email_id} tidak ditemukan."

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = _decode_mime_header(msg.get("Subject"))
        from_ = _decode_mime_header(msg.get("From"))
        to_ = _decode_mime_header(msg.get("To"))
        date_ = msg.get("Date")
        body = _get_email_body(msg)

        conn.logout()
        return (
            f"Dari: {from_}\nKepada: {to_}\nSubjek: {subject}\nTanggal: {date_}\n\n"
            f"Isi:\n{body.strip()}"
        )

    except Exception as e:
        return f"Error saat mengambil detail email: {str(e)}"


@tool
def search_emails(query: str, field: str = "SUBJECT", folder: str = "INBOX", limit: int = 10) -> str:
    """
    Cari email berdasarkan kata kunci pada field tertentu.

    Args:
        query: Kata kunci pencarian.
        field: Field pencarian: "SUBJECT", "FROM", "TO", atau "BODY". Default "SUBJECT".
        folder: Nama folder/mailbox, default "INBOX".
        limit: Jumlah maksimal hasil yang dikembalikan.

    Returns:
        Daftar ringkas email yang cocok (ID, dari, subjek, tanggal).
    """
    valid_fields = {"SUBJECT", "FROM", "TO", "BODY"}
    field = field.upper()
    if field not in valid_fields:
        return f"Field tidak valid. Gunakan salah satu dari: {', '.join(valid_fields)}"

    try:
        conn = _connect_imap()
        conn.select(folder)

        status, data = conn.search(None, f'({field} "{query}")')
        if status != "OK":
            conn.logout()
            return "Pencarian gagal."

        email_ids = data[0].split()
        if not email_ids:
            conn.logout()
            return f"Tidak ada email yang cocok dengan '{query}' pada field {field}."

        email_ids = email_ids[-limit:]
        email_ids.reverse()

        results: List[str] = []
        for eid in email_ids:
            status, msg_data = conn.fetch(eid, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_mime_header(msg.get("Subject"))
            from_ = _decode_mime_header(msg.get("From"))
            date_ = msg.get("Date")

            results.append(f"ID: {eid.decode()} | Dari: {from_} | Subjek: {subject} | Tanggal: {date_}")

        conn.logout()
        return "\n".join(results)

    except Exception as e:
        return f"Error saat mencari email: {str(e)}"


@tool
def mark_email_as_read(email_id: str, folder: str = "INBOX") -> str:
    """
    Tandai sebuah email sebagai sudah dibaca.

    Args:
        email_id: ID email yang akan ditandai.
        folder: Nama folder/mailbox, default "INBOX".

    Returns:
        Pesan status operasi.
    """
    try:
        conn = _connect_imap()
        conn.select(folder)
        conn.store(email_id.encode(), "+FLAGS", "\\Seen")
        conn.logout()
        return f"Email {email_id} berhasil ditandai sudah dibaca."
    except Exception as e:
        return f"Error: {str(e)}"


# Daftar semua tools, siap di-import oleh email_agent.py
EMAIL_TOOLS = [
    send_email,
    read_emails,
    get_email_detail,
    search_emails,
    mark_email_as_read,
]

from __future__ import annotations

import imaplib
import os
import email
from email.message import Message
from email.header import decode_header
from typing import Optional
from html.parser import HTMLParser


IMAP_SERVER = os.getenv("IMAP_SERVER", "imappro.zoho.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
USERNAME = os.getenv("EMAIL_USER", "mgalarraga@tecnoav.com")
PASSWORD = os.getenv("EMAIL_PASS", "x3Pd5eR0Fadh")
MAILBOX = os.getenv("MAILBOX", "INBOX")


def decode_mime_words(value: str) -> str:
    parts = decode_header(value)
    out: list[str] = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(part))
    return "".join(out)


def extract_body_text(msg: Message) -> str:
    # 1) Preferimos text/plain
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if ctype == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")

        # 2) Si no hay text/plain, intentamos text/html
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if ctype == "text/html" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")

        return ""

    # No multipart
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


def fetch_raw_email_bytes(imap: imaplib.IMAP4_SSL, msg_id: str) -> bytes:
    status, msg_data = imap.fetch(msg_id, "(RFC822)")
    if status != "OK":
        raise RuntimeError("No se pudo obtener el correo (fetch RFC822).")

    for item in msg_data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])

    raise RuntimeError(
        "No se encontró contenido RFC822 en la respuesta de IMAP.")


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = None
        for k, v in attrs:
            if k.lower() == "href" and v:
                href = v.strip()
                break
        if href:
            self.links.append(href)


def extract_links_from_html(html_text: str) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html_text)

    # Quita duplicados manteniendo orden
    seen: set[str] = set()
    out: list[str] = []
    for link in parser.links:
        if link not in seen:
            out.append(link)
            seen.add(link)
    return out


def main() -> None:
    if not USERNAME or not PASSWORD:
        raise RuntimeError(
            "Faltan credenciales: define EMAIL_USER y EMAIL_PASS como variables de entorno.")

    imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)

    try:
        imap.login(USERNAME, PASSWORD)
        imap.select(MAILBOX)

        # Buscar correos por asunto
        status, data = imap.search(None, '(SUBJECT "Lumu Alert")')
        if status != "OK" or not data or not data[0]:
            print('No se encontraron correos con asunto "Lumu Alert".')
            return

        ids = data[0].split()
        last_id_bytes = ids[-1]
        last_id = last_id_bytes.decode("ascii")  # <- clave para fetch()

        raw_email = fetch_raw_email_bytes(imap, last_id)
        msg: Message = email.message_from_bytes(raw_email)

        subject = decode_mime_words(msg.get("Subject") or "")
        from_ = decode_mime_words(msg.get("From") or "")
        date_ = msg.get("Date") or ""

        body = extract_body_text(msg)

        # Extraer links si es HTML
        links: list[str] = []
        if "<html" in body.lower() or "<a " in body.lower():
            links = extract_links_from_html(body)

        print("===== ÚLTIMO CORREO =====")
        print(f"From: {from_}")
        print(f"Date: {date_}")
        print(f"Subject: {subject}")

        print("\nLinks encontrados:")
        if not links:
            print("(no se encontraron links en el body)")
        else:
            for i, link in enumerate(links, 1):
                print(f"{i}. {link}")

        # (Opcional) imprimir parte del body
        print("\n--- BODY (inicio) ---")
        print(body[:2000])
        print("--- BODY (fin) ---\n")

    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()

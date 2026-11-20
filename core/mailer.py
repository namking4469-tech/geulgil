"""메일 발송(SMTP). Secrets 에 SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD 가 있어야 한다."""
import smtplib
import ssl
import urllib.parse
from email.message import EmailMessage

from .config import secret


def smtp_ready() -> bool:
    return bool(secret("SMTP_HOST") and secret("SMTP_USER") and secret("SMTP_PASSWORD"))


def send_mail(to: str, subject: str, body: str, reply_to: str = "", sender_name: str = "",
              attachments: list[tuple[str, bytes, str]] | None = None) -> tuple[bool, str]:
    if not smtp_ready():
        return False, "SMTP 가 설정되지 않았습니다."
    user = str(secret("SMTP_USER"))
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{user}>" if sender_name else user
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    for name, data, mime in attachments or []:
        main, _, sub = mime.partition("/")
        msg.add_attachment(data, maintype=main, subtype=sub or "octet-stream", filename=name)
    host, port = str(secret("SMTP_HOST")), int(secret("SMTP_PORT", 587))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
                s.login(user, str(secret("SMTP_PASSWORD")))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, str(secret("SMTP_PASSWORD")))
                s.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


def mailto_link(to: str, subject: str, body: str) -> str:
    q = urllib.parse.urlencode({"subject": subject, "body": body[:1800]}, quote_via=urllib.parse.quote)
    return f"mailto:{urllib.parse.quote(to)}?{q}"

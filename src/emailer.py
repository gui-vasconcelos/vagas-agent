import os
import logging
import requests

log = logging.getLogger(__name__)


def send_email(subject, content_md, html_body=None):
    api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("EMAIL_TO")
    from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev")

    if not api_key or not to_email:
        log.error("RESEND_API_KEY ou EMAIL_TO não configurados. Email não enviado.")
        return False

    payload = {
        "from": from_email,
        "to": [to_email],  # API Resend exige lista
        "subject": subject,
        "html": html_body or content_md.replace("\n", "<br>"),
        "text": content_md,  # fallback texto-puro
    }
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        log.info("Email enviado (Resend id: %s)", r.json().get("id"))
        return True
    except Exception as e:
        body = getattr(getattr(e, "response", None), "text", "")
        log.error("Falha ao enviar email: %s — %s", e, body)
        return False

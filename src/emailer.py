import os
import requests

def send_email(subject, content_md, config):
    api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("EMAIL_TO")
    from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Converter markdown simples para HTML básico para o email
    html_content = content_md.replace("\n", "<br>")
    
    payload = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "html": html_content
    }
    
    requests.post(url, headers=headers, json=payload)

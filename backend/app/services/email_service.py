"""이메일 발송 서비스 — SMTP (Mailpit 로컬)."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


class EmailError(Exception):
    """이메일 발송 실패."""


def send_verification_email(to: str, token: str) -> None:
    """이메일 인증 링크 발송."""
    if os.getenv("TESTING") == "1":
        return

    verify_url = f"{settings.frontend_url}/auth/verify-email?token={token}"
    html = _verification_html(verify_url)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[FridgeChef] 이메일 인증을 완료해주세요"
        msg["From"] = "FridgeChef <noreply@fridgechef.local>"
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.mailpit_host, settings.mailpit_port) as smtp:
            smtp.sendmail(msg["From"], [to], msg.as_string())
    except Exception as exc:
        raise EmailError(f"이메일 발송 실패: {exc}") from exc


def _verification_html(verify_url: str) -> str:
    return f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto">
  <h2>FridgeChef 이메일 인증</h2>
  <p>아래 버튼을 클릭해 이메일 인증을 완료해주세요. 링크는 24시간 동안 유효합니다.</p>
  <a href="{verify_url}"
     style="display:inline-block;padding:12px 24px;background:#16a34a;color:#fff;
            border-radius:6px;text-decoration:none;font-weight:bold">
    이메일 인증하기
  </a>
  <p style="margin-top:16px;color:#6b7280;font-size:13px">
    본인이 요청하지 않은 경우 이 메일을 무시해주세요.
  </p>
</div>
"""

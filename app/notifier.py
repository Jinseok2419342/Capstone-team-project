from __future__ import annotations

import html
import logging
import smtplib
import ssl
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Callable

from .config import AppConfig


logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, config: AppConfig, settings_getter: Callable[[], dict[str, Any]]):
        self.config = config
        self.settings_getter = settings_getter

    def configured(self) -> bool:
        settings = self.settings_getter()
        return bool(
            settings.get("admin_email")
            and settings.get("smtp_host")
            and settings.get("smtp_username")
            and self.config.smtp_password
        )

    def send_due(self, item: dict[str, Any]) -> tuple[bool, str | None]:
        try:
            settings = self.settings_getter()
            if not self.configured():
                return False, "SMTP 설정이 없어 웹 알림만 생성했습니다."
            clean_name = str(item.get("name", "분실물")).replace("\r", " ").replace("\n", " ")
            recipient = str(settings["admin_email"]).replace("\r", "").replace("\n", "")
            sender = str(settings["smtp_username"]).replace("\r", "").replace("\n", "")
            name = html.escape(clean_name)
            message = EmailMessage()
            message["Subject"] = f"[분실물 보관소] {clean_name} 폐기 기한 도래"
            message["From"] = sender
            message["To"] = recipient
            message.set_content(
                f"{clean_name}의 보관 기한이 지났습니다. 관리자 웹에서 상태를 확인해 주세요."
            )
            message.add_alternative(
                f"""<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7;padding:28px;color:#1d1d1f">
                <div style="max-width:560px;margin:auto;background:#fff;border-radius:22px;padding:30px;border:1px solid #e5e5e7">
                <div style="font-size:13px;color:#6e6e73">AI 분실물 보관소</div>
                <h1 style="font-size:26px;margin:8px 0 14px">보관 기한이 도래했습니다</h1>
                <p style="line-height:1.6"><strong>{name}</strong> 물품을 확인하고 폐기 또는 보관 연장을 결정해 주세요.</p>
                <p style="color:#6e6e73;font-size:14px">물품 번호 #{item.get('id')} · 기한 {html.escape(str(item.get('expires_at', '')))}</p>
                </div></body></html>""",
                subtype="html",
            )
            host = str(settings["smtp_host"])
            port = int(settings.get("smtp_port", 587))
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as smtp:
                    smtp.login(sender, self.config.smtp_password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=20) as smtp:
                    smtp.ehlo()
                    if bool(settings.get("smtp_use_tls", True)):
                        smtp.starttls(context=ssl.create_default_context())
                        smtp.ehlo()
                    smtp.login(sender, self.config.smtp_password)
                    smtp.send_message(message)
            return True, None
        except Exception as exc:
            logger.exception("Due notification email failed")
            return False, str(exc)[:500]


class ExpirationScheduler:
    def __init__(
        self,
        store: Any,
        notifier: EmailNotifier,
        interval_seconds: float = 30.0,
        retry_after_seconds: float = 300.0,
    ):
        self.store = store
        self.notifier = notifier
        self.interval_seconds = interval_seconds
        self.retry_after_seconds = max(0.0, float(retry_after_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._run_lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="expiration-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def run_once(self) -> list[dict[str, Any]]:
        # The HTTP maintenance route and background loop may race. Holding one
        # process-local claim across delivery prevents duplicate SMTP sends.
        if not self._run_lock.acquire(blocking=False):
            return []
        try:
            now = datetime.now(timezone.utc)
            expired = self.store.process_expirations(now)
            for item in expired:
                self.store.create_activity(
                    "item_due",
                    f"{item['name']}의 보관 기한이 도래했습니다.",
                    item_id=item["id"],
                )
            # Snapshot retries before attempting any new delivery, otherwise a
            # fast retry interval could resend a failure from this same pass.
            retries = self.store.list_retryable_due_notifications(
                datetime.now(timezone.utc),
                retry_after_seconds=self.retry_after_seconds,
                limit=25,
            )
            for retry in retries:
                self._deliver(retry["notification"], retry["item"])

            candidates = self.store.get_due_notifications_candidates(now)
            for item in candidates:
                notification = self.store.create_notification(
                    item_id=item["id"],
                    notification_type="disposal_due",
                    status="pending",
                    scheduled_for=item["expires_at"],
                )
                self._deliver(notification, item)
            return expired
        finally:
            self._run_lock.release()

    def _deliver(self, notification: dict[str, Any], item: dict[str, Any]) -> None:
        sent, error = self.notifier.send_due(item)
        if sent:
            self.store.mark_notification_sent(notification["id"])
            self.store.create_activity(
                "email_sent",
                f"{item['name']} 기한 알림 메일을 발송했습니다.",
                item_id=item["id"],
            )
        else:
            self.store.mark_notification_failed(
                notification["id"], error or "알 수 없는 오류"
            )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Expiration scheduler iteration failed")
            self._stop.wait(self.interval_seconds)

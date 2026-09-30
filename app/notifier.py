from __future__ import annotations

import html
import logging
import smtplib
import ssl
import threading
import time
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
        return self._configured(self.settings_getter())

    def _configured(self, settings: dict[str, Any]) -> bool:
        return bool(
            settings.get("admin_email")
            and settings.get("smtp_host")
            and settings.get("smtp_username")
            and self.config.smtp_password
        )

    def send_due(self, item: dict[str, Any]) -> tuple[bool, str | None]:
        try:
            settings = self.settings_getter()
            if not self._configured(settings):
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
        self._lifecycle_lock = threading.Lock()

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread and self._thread.is_alive():
                return
            if self._stop.is_set() and self._run_lock.locked():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="expiration-scheduler", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 3.0) -> bool:
        """Request a stop and report whether all scheduled/manual work drained."""

        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._lifecycle_lock:
            self._stop.set()
            if self._thread and self._thread.is_alive():
                if self._thread is threading.current_thread():
                    return False
                self._thread.join(timeout=max(0.0, deadline - time.monotonic()))
                if self._thread.is_alive():
                    return False
            acquired = self._run_lock.acquire(timeout=max(0.0, deadline - time.monotonic()))
            if acquired:
                self._run_lock.release()
            return acquired

    def run_once(self) -> list[dict[str, Any]]:
        # The HTTP maintenance route and background loop may race. Holding one
        # process-local claim across delivery prevents duplicate SMTP sends.
        if not self._run_lock.acquire(blocking=False):
            return []
        try:
            if self._stop.is_set():
                return []
            now = datetime.now(timezone.utc)
            expired = self.store.process_expirations(now, log_activity=True)
            # Snapshot retries before attempting any new delivery, otherwise a
            # fast retry interval could resend a failure from this same pass.
            retries = self.store.list_retryable_due_notifications(
                datetime.now(timezone.utc),
                retry_after_seconds=self.retry_after_seconds,
                limit=25,
            )
            for retry in retries:
                if self._stop.is_set():
                    return expired
                self._deliver(retry["notification"])

            candidates = self.store.get_due_notifications_candidates(now)
            for item in candidates:
                if self._stop.is_set():
                    return expired
                notification = self.store.create_notification(
                    item_id=item["id"],
                    notification_type="disposal_due",
                    status="pending",
                    scheduled_for=item["expires_at"],
                )
                self._deliver(notification)
            return expired
        finally:
            self._run_lock.release()

    def _deliver(self, notification: dict[str, Any]) -> None:
        # The durable lease coordinates independent scheduler instances. The
        # item is re-read inside the claim transaction because it may have been
        # recovered or extended since the candidates/retry snapshot was taken.
        claim = self.store.claim_due_notification(
            notification["id"], retry_after_seconds=self.retry_after_seconds
        )
        if claim is None:
            return
        try:
            sent, error = self.notifier.send_due(claim["item"])
        except Exception as exc:
            logger.exception("Notification sender failed")
            sent, error = False, str(exc)[:500]
        if sent:
            self.store.mark_notification_sent(
                notification["id"], delivery_token=claim["token"], log_activity=True
            )
        else:
            self.store.mark_notification_failed(
                notification["id"], error or "알 수 없는 오류",
                delivery_token=claim["token"],
            )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Expiration scheduler iteration failed")
            self._stop.wait(self.interval_seconds)

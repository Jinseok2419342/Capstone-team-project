from __future__ import annotations

import math
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


CATEGORIES = ("음식물", "비음식물", "고가품")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def calc_dday(expires_at: str | None) -> int | None:
    dispose = _parse_datetime(expires_at)
    if dispose is None:
        return None
    if dispose.tzinfo is None:
        dispose = dispose.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return math.ceil((dispose - now).total_seconds() / 86400)


def _format_korean_datetime(iso: str | None) -> str:
    if not iso:
        return "-"
    parsed = _parse_datetime(iso)
    if parsed is None:
        return iso
    local = parsed.astimezone()
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _dday_label(dday: int | None) -> str:
    if dday is None:
        return "-"
    if dday < 0:
        return f"D+{abs(dday)} 초과"
    if dday == 0:
        return "D-Day"
    return f"D-{dday}"


def _status_label(dday: int | None) -> str:
    if dday is None:
        return "-"
    return "폐기 필요" if dday < 0 else "보관 중"


def build_status_report(items: list[dict[str, Any]]) -> tuple[str, str]:
    now = datetime.now().astimezone()
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")

    counts = {cat: 0 for cat in CATEGORIES}
    expired_counts = {cat: 0 for cat in CATEGORIES}
    for item in items:
        cat = item.get("category", "")
        if cat in counts:
            counts[cat] += 1
            dday = calc_dday(item.get("expires_at"))
            if dday is not None and dday < 0:
                expired_counts[cat] += 1

    total = len(items)
    total_expired = sum(expired_counts.values())

    lines = [
        "분실물 관리 대시보드 — 현황 보고",
        f"보고 시각: {generated_at}",
        "",
        "[요약]",
        f"전체: {total}",
        f"음식물 (1일): {counts['음식물']}",
        f"비음식물 (30일): {counts['비음식물']}",
        f"고가품 (6개월): {counts['고가품']}",
        "",
        "[카테고리별 현황]",
        "카테고리 | 전체 | 폐기 필요",
    ]
    for cat in CATEGORIES:
        lines.append(f"{cat} | {counts[cat]} | {expired_counts[cat]}")
    lines.append(f"합계 | {total} | {total_expired}")
    lines.extend(["", "[분실물 목록]"])

    if not items:
        lines.append("(등록된 분실물 없음)")
    else:
        lines.append("ID | 물건명 | 카테고리 | 감지 시각 | 폐기 기한 | D-Day | 상태")
        for item in items:
            dday = calc_dday(item.get("expires_at"))
            lines.append(
                " | ".join(
                    [
                        str(item.get("id", "")),
                        str(item.get("name", "")),
                        str(item.get("category", "")),
                        _format_korean_datetime(item.get("detected_at")),
                        _format_korean_datetime(item.get("expires_at")),
                        _dday_label(dday),
                        _status_label(dday),
                    ]
                )
            )

    plain = "\n".join(lines)

    html_rows = ""
    for item in items:
        dday = calc_dday(item.get("expires_at"))
        status = _status_label(dday)
        status_color = "#e74c3c" if status == "폐기 필요" else "#27ae60"
        html_rows += (
            "<tr>"
            f"<td>{item.get('id', '')}</td>"
            f"<td>{item.get('name', '')}</td>"
            f"<td>{item.get('category', '')}</td>"
            f"<td>{_format_korean_datetime(item.get('detected_at'))}</td>"
            f"<td>{_format_korean_datetime(item.get('expires_at'))}</td>"
            f"<td>{_dday_label(dday)}</td>"
            f'<td style="color:{status_color};font-weight:600;">{status}</td>'
            "</tr>"
        )

    if not html_rows:
        html_rows = '<tr><td colspan="7" style="text-align:center;color:#888;">등록된 분실물 없음</td></tr>'

    category_rows = "".join(
        f"<tr><td>{cat}</td><td>{counts[cat]}</td><td>{expired_counts[cat]}</td></tr>"
        for cat in CATEGORIES
    )

    html = f"""\
<html><body style="font-family:'Segoe UI',sans-serif;color:#222;">
  <h2>분실물 관리 대시보드 — 현황 보고</h2>
  <p>보고 시각: {generated_at}</p>
  <h3>요약</h3>
  <ul>
    <li>전체: <strong>{total}</strong></li>
    <li>음식물 (1일): <strong>{counts['음식물']}</strong></li>
    <li>비음식물 (30일): <strong>{counts['비음식물']}</strong></li>
    <li>고가품 (6개월): <strong>{counts['고가품']}</strong></li>
  </ul>
  <h3>카테고리별 현황</h3>
  <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
    <thead><tr><th>카테고리</th><th>전체</th><th>폐기 필요</th></tr></thead>
    <tbody>{category_rows}
      <tr style="font-weight:600;"><td>합계</td><td>{total}</td><td>{total_expired}</td></tr>
    </tbody>
  </table>
  <h3>분실물 목록</h3>
  <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
    <thead>
      <tr>
        <th>ID</th><th>물건명</th><th>카테고리</th>
        <th>감지 시각</th><th>폐기 기한</th><th>D-Day</th><th>상태</th>
      </tr>
    </thead>
    <tbody>{html_rows}</tbody>
  </table>
</body></html>"""

    return plain, html


def _smtp_config() -> dict[str, Any]:
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "to": os.getenv("ADMIN_EMAIL", "").strip(),
        "from_addr": os.getenv("SMTP_FROM", "").strip() or os.getenv("SMTP_USER", "").strip(),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() not in {"0", "false", "no", "off"},
    }


def smtp_configured() -> bool:
    cfg = _smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"] and cfg["to"])


def send_status_email(items: list[dict[str, Any]]) -> str:
    cfg = _smtp_config()
    missing = [
        name
        for name, key in [
            ("SMTP_HOST", "host"),
            ("SMTP_USER", "user"),
            ("SMTP_PASSWORD", "password"),
            ("ADMIN_EMAIL", "to"),
        ]
        if not cfg[key]
    ]
    if missing:
        raise ValueError(f"이메일 설정이 없습니다: {', '.join(missing)}")

    plain, html = build_status_report(items)
    subject = f"[분실물 관리] 현황 보고 ({datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')})"

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = cfg["from_addr"]
    message["To"] = cfg["to"]
    message.attach(MIMEText(plain, "plain", "utf-8"))
    message.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
        if cfg["use_tls"]:
            server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["from_addr"], [cfg["to"]], message.as_string())

    return cfg["to"]

"""Guided experiment session that records the paper's and the final report's
results in one sitting.

The operator only performs each physical action and presses Enter.  The
session reads the system's own reaction from the web API, so nobody has to
copy results from the screen, copy the database, or start separate loggers.
The same run also keeps the camera scene before and after every trial, the
time from the end of the hand motion to the database record (both on the Pi's
clock), a short demo rehearsal (backup video and same-ID evidence) and an
automatic check of the management functions on the real Pi.  Only the Python
standard library is used (it runs on the Windows laptop).

    python scripts/experiments/run_experiment.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from . import trial_report

HEALTH_FIELDS = (
    "timestamp_utc", "ok", "phase", "camera_connected", "fps", "processing_ms",
    "frame_sequence", "detected_changes", "pending_changes", "error",
)
TRIAL_FIELDS = (
    "번호", "조건", "행동", "물품", "결과", "AI이름", "AI분류", "메모", "item_id", "시작", "종료",
    "감지지연_s", "AI결과",
)
CATEGORY_LABELS = {"valuable": "귀중품", "general": "일반", "food": "음식"}
CATEGORY_KEYS = {"귀중품": "valuable", "일반": "general", "음식": "food"}
PENDING_NAME = "분석 중인 새 물품"
REMOTE_DIR = "/opt/refound/data/experiments"
RECORDER = "/opt/refound/scripts/experiments/monitor_pi_resources.py"
STREAM_PATH = "/camera/stream"
MAX_FRAME_BYTES = 4 * 1024 * 1024
CLASSIFICATION_DONE = ("item_classified", "classification_inconclusive")

# Minimum wait after Enter: settle 3.0 s + stable 1.2 s + analysis margin.
MIN_WAIT_S = 6.0
QUIET_S = 3.0
NO_EVENT_LIMIT_S = {"제거": 30.0}
DEFAULT_NO_EVENT_LIMIT_S = 18.0
EVENT_LIMIT_S = 40.0
# A motion-to-record delay longer than this belongs to an earlier motion.
MAX_LATENCY_S = 120.0

# Only vision/AI parameters go into env.json (Table 4); mail settings do not.
ENV_SETTING_KEYS = (
    "provider", "openai_model", "gemini_model", "ai_min_confidence", "camera_backend",
    "camera_width", "camera_height", "camera_fps", "monitor_fps", "accumulated_check_fps",
    "preview_stream_fps", "preview_max_width", "stabilization_analysis_width",
    "camera_mains_frequency_hz", "motion_threshold", "change_threshold", "min_change_area",
    "max_change_ratio", "settle_seconds", "stable_seconds", "hardware_profile",
)
ENV_QUESTIONS = (
    ("storage", "microSD 용량 (예: 32GB, 모르면 Enter)", ""),
    ("cooling", "냉각 (예: 방열판+팬, 케이스만, 없음 / 모르면 Enter)", ""),
    ("camera_geometry", "카메라 설치 (예: 책상 위 높이 60cm, 아래를 향함 / 모르면 Enter)", ""),
    ("place", "실험 장소 (예: 교내 실습실 / 모르면 Enter)", ""),
    ("network", "네트워크 (Enter = 학교 Wi-Fi에 연결된 노트북 핫스팟)", "학교 Wi-Fi에 연결된 노트북 핫스팟"),
    ("cold_boot", "오늘 Pi를 꺼진 상태에서 켜고 랜선 없이 바로 접속했나요? (y/n, 모르면 Enter)", ""),
)
REHEARSAL_TAGS = {"등록": "1_register", "이동": "2_move", "제거": "3_remove"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _epoch(value: Any) -> float | None:
    parsed = trial_report._parse_time(value)
    return parsed.timestamp() if parsed is not None else None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _json_or_none(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, ValueError):
        return None


def health_row(payload: dict[str, Any] | None, error: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"timestamp_utc": iso(now_utc())}
    if payload is None:
        row.update(ok=0, error=error[:200])
        return row
    camera = payload.get("camera") or {}
    row.update(
        ok=int(bool(payload.get("ok"))),
        phase=camera.get("phase", ""),
        camera_connected=int(bool(camera.get("camera_connected"))),
        fps=camera.get("fps", ""),
        processing_ms=camera.get("processing_ms", ""),
        frame_sequence=camera.get("frame_sequence", ""),
        detected_changes=camera.get("detected_changes", ""),
        pending_changes=camera.get("pending_changes", ""),
        error="",
    )
    return row


class ApiError(RuntimeError):
    pass


class Api:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=self.timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise ApiError(str(exc)) from exc

    def get_bytes(self, path: str) -> bytes:
        try:
            with urllib.request.urlopen(self.base + path, timeout=self.timeout) as response:
                return response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise ApiError(str(exc)) from exc

    def send(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
        """Send JSON and return ``(status, body)``; HTTP errors are results."""
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"} if data is not None else {}
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            # Test e-mail delivery can take a while on a slow SMTP server.
            with urllib.request.urlopen(request, timeout=self.timeout * 6) as response:
                return response.status, _json_or_none(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _json_or_none(exc.read())
        except (urllib.error.URLError, OSError) as exc:
            raise ApiError(str(exc)) from exc

    def grab_frame(self, path: str = STREAM_PATH) -> bytes:
        """Return one complete JPEG from the administrator's MJPEG preview."""
        buffer = b""
        try:
            with urllib.request.urlopen(self.base + path, timeout=self.timeout) as response:
                while len(buffer) < MAX_FRAME_BYTES:
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    buffer += chunk
                    start = buffer.find(b"\xff\xd8")
                    end = buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                    if end >= 0:
                        return buffer[start:end + 2]
        except (urllib.error.URLError, OSError) as exc:
            raise ApiError(str(exc)) from exc
        raise ApiError("카메라 영상에서 완전한 사진을 받지 못했습니다")


def event_kind(activity: dict[str, Any]) -> str | None:
    """Map one activity row to the trial-sheet result vocabulary."""
    kind = activity.get("type")
    meta = activity.get("metadata") or {}
    source = meta.get("source") if isinstance(meta, dict) else None
    if kind == "item_detected" and source == "camera":
        return "등록"
    if kind == "item_moved" and source == "camera":
        return "이동"
    if kind == "item_recovered" and source in ("camera", "camera_ai_verification"):
        return "제거"
    if kind == "recovery_check_inconclusive" and source == "camera_ai_verification":
        return "확인 필요"
    if kind == "recovery_check_deferred":
        return "확인 필요"
    return None


def decide_result(activities: Iterable[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Return the first camera event of a trial window and all events seen."""
    events = [a for a in sorted(activities, key=lambda a: a.get("id") or 0) if event_kind(a)]
    if not events:
        return "반응 없음", []
    return event_kind(events[0]) or "반응 없음", events


def motion_to_event_seconds(
    event: dict[str, Any], marks: Iterable[float], after: float | None,
) -> float | None:
    """Seconds from the last hand motion before ``event`` to its database record.

    Both values come from the Pi's clock: ``marks`` are the camera status
    ``last_motion_at`` values seen while polling and ``created_at`` is the
    activity row.  ``after`` is the last motion already seen before the trial
    started, so an earlier trial's motion is never used.
    """
    created = _epoch(event.get("created_at"))
    if created is None:
        return None
    candidates = [m for m in marks if m <= created and (after is None or m > after)]
    if not candidates:
        return None
    seconds = created - max(candidates)
    return round(seconds, 2) if 0.0 <= seconds <= MAX_LATENCY_S else None


@dataclass
class Collector:
    """Keeps every activity seen through /api/dashboard, deduplicated by id."""

    api: Any
    activities: dict[int, dict[str, Any]] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    motion_marks: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def poll(self) -> list[dict[str, Any]]:
        payload = self.api.get("/api/dashboard")
        fresh = []
        with self.lock:
            self.camera = payload.get("camera") or {}
            self.notifications = list(payload.get("notifications") or [])
            mark = _number(self.camera.get("last_motion_at"))
            if mark is not None and (not self.motion_marks or mark > self.motion_marks[-1]):
                self.motion_marks.append(mark)
            for activity in payload.get("activities") or []:
                key = activity.get("id")
                if isinstance(key, int) and key not in self.activities:
                    self.activities[key] = activity
                    fresh.append(activity)
        return fresh

    def last_id(self) -> int:
        with self.lock:
            return max(self.activities, default=0)

    def latest_motion(self) -> float | None:
        with self.lock:
            return self.motion_marks[-1] if self.motion_marks else None

    def marks(self) -> list[float]:
        with self.lock:
            return list(self.motion_marks)

    def since(self, activity_id: int) -> list[dict[str, Any]]:
        with self.lock:
            return [a for k, a in sorted(self.activities.items()) if k > activity_id]

    def dump(self) -> list[dict[str, Any]]:
        with self.lock:
            return [a for _, a in sorted(self.activities.items())]


class HealthLogger(threading.Thread):
    def __init__(self, api: Api, path: Path, interval: float = 1.0):
        super().__init__(daemon=True)
        self.api, self.path, self.interval = api, path, interval
        self.stop_event = threading.Event()

    def run(self) -> None:
        new = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEALTH_FIELDS)
            if new:
                writer.writeheader()
            while not self.stop_event.is_set():
                try:
                    row = health_row(self.api.get("/api/health"))
                except ApiError as exc:
                    row = health_row(None, str(exc))
                writer.writerow(row)
                handle.flush()
                self.stop_event.wait(self.interval)

    def stop(self) -> None:
        self.stop_event.set()
        self.join(timeout=5)


@dataclass
class Trial:
    no: int
    condition: str
    action: str
    item: str = ""


def build_plan(items: Sequence[str], rounds: int = 2, hand: int = 20, light: int = 10, shadow: int = 10) -> list[Trial]:
    plan: list[Trial] = []
    for _ in range(rounds):
        for action in ("등록", "이동", "제거"):
            plan.extend(Trial(len(plan) + 1, "일반", action, name) for name in items)
    for condition, count in (("손", hand), ("조명", light), ("그림자", shadow)):
        plan.extend(Trial(len(plan) + 1, condition, "무변화") for _ in range(count))
    return plan


INSTRUCTIONS = {
    "등록": "{item}을(를) 빈자리에 놓고 손을 뺀 뒤",
    "이동": "{item}을(를) 다른 빈자리로 옮기고 손을 뺀 뒤",
    "제거": "{item}을(를) 보관대에서 치운 뒤",
    "손": "물건을 건드리지 말고 손을 보관대 위로 넣었다 뺀 뒤",
    "조명": "조명을 끄고 약 10초 뒤 다시 켠 뒤",
    "그림자": "보관대 옆에 5초 이상 서서 그림자를 드리우고 비켜선 뒤",
}

CAPTURE_DASHBOARD = (
    "\n[캡처] 지금 화면 캡처 2장(Win+Shift+S, 주소창·개인 정보는 빼고 PNG로 저장):\n"
    "  ① 대시보드 — 실시간 카메라와 보관 물품이 한 화면에 보이게\n"
    "  ② 보관 물품 목록 — AI가 붙인 이름·분류·사진이 보이게\n"
    "  저장했으면"
)
CAPTURE_SETUP_PHOTO = (
    "\n[사진] 휴대폰으로 실험 장면 사진 1장: 카메라·Pi·보관대 전체가 보이게(사람 얼굴 없이).\n"
    "  찍었으면"
)
CAPTURE_ACTIVITY = (
    "\n[캡처] 관리자 화면의 활동 기록(또는 점검한 물품의 상세 이력)을 1장 캡처하세요.\n"
    "  수정·연장·폐기·복원 이력이 같은 물품에 이어져 보이면 됩니다. 저장했으면"
)


class FunctionChecker:
    """Exercise the management functions on the running system via its API.

    One stored camera item is edited, confirmed, extended, expired, disposed,
    restored, recovered, dismissed and finally put back to its original name
    and expiry.  Every step is recorded as passed, failed or not applicable
    (e-mail without SMTP settings), and a failing step never stops the rest.
    """

    EXPECTED_ACTIVITIES = (
        "item_edited", "item_reviewed", "item_extended", "item_disposed",
        "item_restored", "item_recovered", "item_dismissed",
    )

    def __init__(self, api: Any, *, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic, notification_wait: float = 30.0):
        self.api, self.sleep, self.clock = api, sleep, clock
        self.notification_wait = notification_wait
        self.results: list[dict[str, Any]] = []
        self.mail_sent = False

    def _record(self, step: str, outcome: str, detail: str = "") -> dict[str, Any]:
        row = {"점검": step, "결과": outcome, "내용": detail[:160]}
        self.results.append(row)
        return row

    def _call(self, step: str, check: Callable[[], tuple[str, str]]) -> str:
        try:
            outcome, detail = check()
        except ApiError as exc:
            outcome, detail = "실패", f"연결 오류: {exc}"
        except (KeyError, TypeError, ValueError) as exc:
            outcome, detail = "실패", f"응답 형식 오류: {exc}"
        self._record(step, outcome, detail)
        return outcome

    def _item_call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        status, body = self.api.send(method, path, payload)
        if status != 200 or not isinstance(body, dict):
            message = body.get("detail") if isinstance(body, dict) else body
            raise ValueError(f"HTTP {status} {message}")
        return body

    def pick_target(self) -> dict[str, Any] | None:
        page = self.api.get("/api/items?status=active&sort=newest&limit=100")
        candidates = [
            item for item in page.get("items") or []
            if item.get("source_kind") == "camera" and item.get("review_status") != "dismissed"
        ]
        candidates.sort(key=lambda item: item.get("status") != "stored")
        return candidates[0] if candidates else None

    def run(self) -> list[dict[str, Any]]:
        try:
            target = self.pick_target()
        except ApiError as exc:
            self._record("점검 대상 물품", "실패", f"연결 오류: {exc}")
            return self.results
        if target is None:
            self._record("점검 대상 물품", "실패", "보관 중인 카메라 등록 물품이 없습니다")
            return self.results
        item_id = target["id"]
        path = f"/api/items/{item_id}"
        original_name = str(target.get("name") or "")
        original_expiry = str(target.get("expires_at") or "")
        was_confirmed = target.get("review_status") == "confirmed"
        self._record("점검 대상 물품", "통과", f"ID {item_id} '{original_name}'")

        def edit() -> tuple[str, str]:
            body = self._item_call("PATCH", path, {"name": f"{original_name} (점검)"[:80]})
            ok = body.get("name", "").endswith("(점검)")
            return ("통과" if ok else "실패"), f"이름 → {body.get('name')}"

        def confirm() -> tuple[str, str]:
            body = self._item_call("PATCH", path, {"confirm_review": True})
            return ("통과" if body.get("review_status") == "confirmed" else "실패"), f"검토 상태 {body.get('review_status')}"

        def extend() -> tuple[str, str]:
            before = trial_report._parse_time(self.api.get(path).get("expires_at"))
            body = self._item_call("POST", f"{path}/extend", {"days": 7})
            after = trial_report._parse_time(body.get("expires_at"))
            days = (after - before).total_seconds() / 86400 if before and after else math.nan
            ok = abs(days - 7) < 0.01
            return ("통과" if ok else "실패"), f"기한 {days:.2f}일 연장"

        def expire() -> tuple[str, str]:
            server = trial_report._parse_time(self.api.get("/api/health").get("time")) or now_utc()
            past = iso(server - timedelta(hours=1))
            body = self._item_call("PATCH", path, {"expires_at": past})
            return ("통과" if body.get("status") == "due" else "실패"), f"상태 {body.get('status')}"

        mail: dict[str, Any] = {}

        def notify() -> tuple[str, str]:
            self.api.send("POST", "/api/maintenance/check-expirations")
            deadline = self.clock() + self.notification_wait
            while True:
                rows = [
                    n for n in self.api.get("/api/dashboard").get("notifications") or []
                    if n.get("item_id") == item_id and n.get("type") == "disposal_due"
                ]
                settled = [n for n in rows if n.get("status") in ("sent", "failed")]
                if settled or (rows and self.clock() >= deadline):
                    note = (settled or rows)[0]
                    mail["due"] = note.get("status")
                    label = {"sent": "발송됨", "failed": "발송 안 됨"}.get(note.get("status"), "발송 대기")
                    error = f" ({note.get('error')})" if note.get("error") else ""
                    return "통과", f"만료 알림 생성, 메일 {label}{error}"
                if self.clock() >= deadline:
                    return "실패", "만료 알림이 생성되지 않았습니다"
                self.sleep(2.0)

        def action(name: str, expect_status: Iterable[str] | None = None,
                   expect_review: str | None = None) -> Callable[[], tuple[str, str]]:
            def run_action() -> tuple[str, str]:
                body = self._item_call("POST", f"{path}/{name}")
                ok = (expect_status is None or body.get("status") in expect_status) and (
                    expect_review is None or body.get("review_status") == expect_review
                )
                return ("통과" if ok else "실패"), f"상태 {body.get('status')} · 검토 {body.get('review_status')}"
            return run_action

        def put_back() -> tuple[str, str]:
            payload: dict[str, Any] = {"name": original_name, "expires_at": original_expiry}
            if was_confirmed:
                payload["confirm_review"] = True
            body = self._item_call("PATCH", path, payload)
            ok = body.get("name") == original_name and body.get("expires_at") == original_expiry
            return ("통과" if ok else "실패"), f"이름·기한 원래대로, 상태 {body.get('status')}"

        def history() -> tuple[str, str]:
            seen = {
                a.get("type") for a in self.api.get("/api/dashboard").get("activities") or []
                if a.get("item_id") == item_id
            }
            missing = [t for t in self.EXPECTED_ACTIVITIES if t not in seen]
            return ("통과" if not missing else "실패"), (
                f"처리 이력 {len(self.EXPECTED_ACTIVITIES)}종이 같은 ID에 기록" if not missing
                else f"이력 누락: {', '.join(missing)}"
            )

        def test_mail() -> tuple[str, str]:
            status, body = self.api.send("POST", "/api/settings/test-email")
            detail = body.get("detail") if isinstance(body, dict) else ""
            if status == 200:
                mail["test"] = "sent"
                return "통과", "테스트 메일 발송 요청 성공"
            if status == 400:
                return "해당 없음", "메일(SMTP) 미설정"
            return "실패", f"HTTP {status} {detail}"

        active = ("stored", "due")
        steps: list[tuple[str, Callable[[], tuple[str, str]]]] = [
            ("물품 정보 수정", edit),
            ("검토 완료 확정", confirm),
            ("보관 기한 7일 연장", extend),
            ("기한 경과 → 처리 필요 전환", expire),
            ("만료 알림 생성·메일 발송", notify),
            ("폐기 처리", action("dispose", ("disposed",))),
            ("폐기 → 보관 복원", action("restore", active)),
            ("수동 회수", action("recover", ("recovered",))),
            ("회수 → 보관 복원", action("restore", active)),
            ("감지 제외", action("dismiss", expect_review="dismissed")),
            ("감지 제외 → 복원(재확인 필요)", action("restore", active, "needs_review")),
            ("원래 이름·기한으로 되돌리기", put_back),
            ("처리 이력 연결", history),
            ("관리자 테스트 메일", test_mail),
        ]
        for step, check in steps:
            self._call(step, check)
        self.mail_sent = mail.get("due") == "sent" or mail.get("test") == "sent"
        return self.results


class Session:
    def __init__(
        self, api: Any, out_dir: Path, *, ask: Callable[[str], str] | None = None,
        say: Callable[[str], None] = print, sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic, scenes: bool = True,
    ):
        self.api, self.out = api, out_dir
        # Look up input() at call time so a wrapper (or a test) can replace it.
        self.ask = ask or (lambda prompt: input(prompt))
        self.say, self.sleep, self.clock = say, sleep, clock
        self.collector = Collector(api)
        self.state_path = out_dir / "session.json"
        self.state: dict[str, Any] = {}
        self.scenes = scenes
        self.scene_failures = 0

    # -- persistence -------------------------------------------------
    def load_state(self) -> None:
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        saved = self.out / "activities.json"
        if saved.exists():
            # The dashboard only returns recent rows; keep what earlier runs saw.
            for activity in json.loads(saved.read_text(encoding="utf-8")):
                if isinstance(activity.get("id"), int):
                    self.collector.activities[activity["id"]] = activity

    def save_state(self) -> None:
        self.state["activities_seen"] = len(self.collector.activities)
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.out / "activities.json").write_text(
            json.dumps(self.collector.dump(), ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def done_numbers(self) -> set[int]:
        return {int(row["번호"]) for row in self.state.get("trials", [])}

    def write_trials(self) -> Path:
        path = self.out / "trials.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=TRIAL_FIELDS)
            writer.writeheader()
            for row in sorted(self.state.get("trials", []), key=lambda r: int(r["번호"])):
                writer.writerow({k: row.get(k, "") for k in TRIAL_FIELDS})
        return path

    def experiment_activities(self) -> list[dict[str, Any]]:
        """Activities of the measured run only (the rehearsal comes before it)."""
        first = int(self.state.get("first_activity_id") or 0)
        return [a for a in self.collector.dump() if int(a.get("id") or 0) > first]

    # -- environment -------------------------------------------------
    def ask_environment(self) -> None:
        if self.state.get("env_manual") is not None:
            return
        self.say("\n장비 메모(논문 표 4)를 지금 적어 둡니다. 모르는 항목은 Enter로 넘어가세요.")
        answers: dict[str, str] = {}
        for key, question, default in ENV_QUESTIONS:
            answers[key] = self.ask(f"  {question}: ").strip() or default
        self.state["env_manual"] = answers
        self.save_state()

    def record_environment(self, label: str) -> dict[str, Any]:
        """Keep the AI model, camera and vision settings actually in use."""
        snapshot: dict[str, Any] = {"laptop_time_utc": iso(now_utc())}
        try:
            health = self.api.get("/api/health")
        except ApiError as exc:
            health = {}
            snapshot["error"] = str(exc)[:200]
        camera = health.get("camera") or {}
        provider = health.get("provider") or {}
        server = trial_report._parse_time(health.get("time"))
        snapshot.update(
            server_time_utc=health.get("time"),
            clock_offset_s=round((server - now_utc()).total_seconds(), 1) if server else None,
            hardware_profile=health.get("hardware_profile"),
            app_version=health.get("version"),
            provider={k: provider.get(k) for k in ("requested", "active", "model")},
            camera={k: camera.get(k) for k in (
                "camera_connected", "using_fallback", "privacy_enabled", "phase",
                "frame_width", "frame_height", "preview_width", "preview_height",
            )},
        )
        if isinstance(camera.get("camera_diagnostics"), dict):
            snapshot["camera"]["diagnostics"] = {
                k: v for k, v in camera["camera_diagnostics"].items()
                if isinstance(v, (str, int, float, bool)) or v is None
            }
        try:
            settings = (self.api.get("/api/settings") or {}).get("settings") or {}
            snapshot["settings"] = {k: settings[k] for k in ENV_SETTING_KEYS if k in settings}
        except ApiError:
            pass
        if label == "start" and "service_started_at" not in self.state:
            try:
                self.collector.poll()
                started = [a for a in self.collector.dump() if a.get("type") == "system_started"]
                self.state["service_started_at"] = started[-1].get("created_at") if started else None
            except ApiError:
                pass
        environment = self.state.setdefault("environment", {})
        if label == "start" and "start" in environment:
            # A resumed run keeps the original start and adds its own snapshot.
            label = f"resume-{sum(key.startswith('resume') for key in environment) + 1}"
        environment[label] = snapshot
        self.save_state()
        self.write_environment()
        return snapshot

    def write_environment(self) -> None:
        env = {
            "manual": self.state.get("env_manual") or {},
            "items": self.state.get("items") or [],
            "experiment_started_local": self.state.get("started_local"),
            "service_started_at": self.state.get("service_started_at"),
            **(self.state.get("environment") or {}),
        }
        (self.out / "env.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- waiting for the system's reaction ---------------------------
    def poll_quietly(self) -> None:
        try:
            self.collector.poll()
        except ApiError as exc:
            self.say(f"  (연결 재시도 중: {exc})")

    def wait_for_reaction(self, baseline_id: int, action: str) -> list[dict[str, Any]]:
        started = self.clock()
        last_change = started
        seen = 0
        limit_without_event = NO_EVENT_LIMIT_S.get(action, DEFAULT_NO_EVENT_LIMIT_S)
        while True:
            self.sleep(1.0)
            self.poll_quietly()
            window = [a for a in self.collector.since(baseline_id) if event_kind(a)]
            now = self.clock()
            if len(window) != seen:
                seen, last_change = len(window), now
            camera = self.collector.camera
            settled = camera.get("phase") == "monitoring" and not camera.get("pending_changes")
            elapsed = now - started
            if window:
                if (elapsed >= MIN_WAIT_S and settled and now - last_change >= QUIET_S) or elapsed >= EVENT_LIMIT_S:
                    return window
            elif (elapsed >= limit_without_event and settled) or elapsed >= limit_without_event + 10:
                return window

    def save_scene(self, name: str) -> None:
        """Keep the live camera picture; a failure never interrupts the run."""
        if not self.scenes:
            return
        try:
            frame = self.api.grab_frame()
        except ApiError as exc:
            self.scene_failures += 1
            if self.scene_failures >= 3:
                self.scenes = False
                self.say(f"  (카메라 장면 저장을 끕니다. 실험 결과에는 영향 없음: {exc})")
            return
        self.scene_failures = 0
        folder = self.out / "scenes"
        folder.mkdir(exist_ok=True)
        (folder / f"{name}.jpg").write_bytes(frame)

    # -- interaction helpers -----------------------------------------
    def pause(self, message: str) -> str:
        return self.ask(f"{message} [Enter] ").strip().lower()

    def capture_once(self, key: str, message: str) -> None:
        captures = self.state.setdefault("captures", {})
        if captures.get(key):
            return
        captures[key] = "skipped" if self.pause(message + " (s=건너뛰기)") == "s" else "done"
        self.save_state()

    def ensure_items(self, preset: Sequence[str] | None) -> list[dict[str, str]]:
        if self.state.get("items"):
            return self.state["items"]
        items: list[dict[str, str]] = []
        if preset:
            for entry in preset:
                name, _, category = entry.partition("/")
                items.append({"name": name.strip(), "category": category.strip() or "일반"})
        else:
            self.say("물품 10개의 이름과 분류를 입력합니다. 예: 지갑/귀중품, 우산/일반, 과자/음식")
            while len(items) < 10:
                entry = self.ask(f"  물품 {len(items) + 1}: ").strip()
                name, _, category = entry.partition("/")
                category = category.strip()
                if not name.strip() or category not in CATEGORY_KEYS:
                    self.say("  '이름/분류' 형식으로, 분류는 귀중품·일반·음식 중 하나로 적어 주세요.")
                    continue
                items.append({"name": name.strip(), "category": category})
        self.state["items"] = items
        self.save_state()
        return items

    def classification_seconds(self, item_id: Any) -> float | None:
        """Pi-clock seconds from the provisional record to the AI result."""
        detected = classified = None
        for activity in self.collector.dump():
            if str(activity.get("item_id")) != str(item_id):
                continue
            if activity.get("type") == "item_detected" and detected is None:
                detected = _epoch(activity.get("created_at"))
            elif activity.get("type") in CLASSIFICATION_DONE and classified is None:
                classified = _epoch(activity.get("created_at"))
        if detected is None or classified is None:
            return None
        return round(classified - detected, 2)

    # -- demo rehearsal ----------------------------------------------
    def _rehearsal_step(self, action: str, name: str) -> dict[str, Any]:
        tag = f"rehearsal_{REHEARSAL_TAGS[action]}"
        for attempt in range(1, 4):
            self.poll_quietly()
            baseline = self.collector.last_id()
            motion_before = self.collector.latest_motion()
            self.save_scene(f"{tag}_before")
            self.ask(f"\n[리허설] {action} · {name} — {INSTRUCTIONS[action].format(item=name)} Enter ")
            self.poll_quietly()
            window = self.wait_for_reaction(baseline, action)
            result, events = decide_result(window)
            self.save_scene(f"{tag}_after")
            latency = motion_to_event_seconds(events[0], self.collector.marks(), motion_before) if events else None
            item_id = events[0].get("item_id") if events else None
            parts = [f"  → 시스템 결과: {result}"]
            if item_id is not None:
                parts.append(f"물품 ID {item_id}")
            if latency is not None:
                parts.append(f"움직임이 끝나고 {latency:.1f}초 뒤 기록")
            self.say(" · ".join(parts))
            step = {"action": action, "result": result, "item_id": item_id, "latency_s": latency, "attempt": attempt}
            if result == action or attempt == 3:
                return step
            again = self.ask("  예상과 다릅니다. 화면 상태를 맞춘 뒤 r=다시 시도, Enter=그대로 진행: ").strip().lower()
            if again != "r":
                return step
        return step

    def run_rehearsal(self, item: dict[str, str]) -> dict[str, Any]:
        saved = self.state.get("rehearsal") or {}
        if saved.get("done"):
            return saved
        name = item["name"]
        self.say("\n[시연 리허설] 발표 시연과 같은 흐름을 한 번 합니다(결과표에는 들어가지 않음).")
        self.say("  오류 대비 녹화 영상과, 같은 물품 ID로 등록→이동→회수가 이어지는 증거를 함께 남깁니다.")
        answer = self.pause("  [녹화] 노트북 화면 녹화(Win+Alt+R)와 휴대폰 동영상을 시작했으면 (s=리허설 건너뛰기)")
        if answer == "s":
            self.state["rehearsal"] = {"done": True, "skipped": True}
            self.save_state()
            return self.state["rehearsal"]
        steps: list[dict[str, Any]] = []
        registered_id = None
        ai: dict[str, Any] = {}
        for action in ("등록", "이동", "제거"):
            step = self._rehearsal_step(action, name)
            steps.append(step)
            if action != "등록" or step["result"] != "등록" or step["item_id"] is None:
                continue
            registered_id = step["item_id"]
            self.say("  AI 분석 결과를 기다립니다…")
            found = self.wait_classified(registered_id, limit=60.0)
            self.poll_quietly()
            if found and found.get("name") != PENDING_NAME:
                category = CATEGORY_LABELS.get(found.get("category", ""), found.get("category", ""))
                seconds = self.classification_seconds(registered_id)
                ai = {"name": found.get("name"), "category": category, "classification_s": seconds,
                      "review_status": found.get("review_status")}
                after = f" · 기록 후 {seconds:.1f}초 만에 반영" if seconds is not None else ""
                self.say(f"  → AI 결과: '{ai['name']}' ({category}){after}")
                self.save_item_image(found, f"rehearsal_item{registered_id}.jpg")
            else:
                ai = {"name": None, "error": "AI 결과를 60초 안에 받지 못함"}
                self.say("  → AI 결과를 60초 안에 받지 못했습니다(키·네트워크 확인). 리허설은 계속합니다.")
            self.pause("  [캡처] 물품 상세 화면(AI 이름·분류·사진·기한)을 캡처하세요(Win+Shift+S). 저장했으면")
        same = registered_id is not None and all(str(s.get("item_id")) == str(registered_id) for s in steps)
        if same:
            self.say(f"  → 같은 물품 ID {registered_id}로 등록→이동→회수가 기록되었습니다.")
        else:
            self.say(f"  → 세 단계의 물품 ID가 같지 않습니다: {[s.get('item_id') for s in steps]}")
        self.pause("  [녹화] 녹화를 끝내세요(Win+Alt+R 다시). 영상은 '동영상\\캡처' 폴더에 저장됩니다. 끝났으면")
        self.state["rehearsal"] = {
            "done": True, "item": name, "steps": steps, "ai": ai,
            "item_id": registered_id, "same_item_id": same, "finished_utc": iso(now_utc()),
        }
        self.save_state()
        return self.state["rehearsal"]

    def save_item_image(self, item: dict[str, Any], filename: str) -> None:
        if not item.get("image_url"):
            return
        images = self.out / "images"
        images.mkdir(exist_ok=True)
        try:
            (images / filename).write_bytes(self.api.get_bytes(item["image_url"]))
        except ApiError:
            pass

    def begin_measured_run(self) -> None:
        """Mark where the measured run starts (after the reset)."""
        self.poll_quietly()
        self.state["first_activity_id"] = self.collector.last_id()
        self.state["started_at"] = iso(now_utc())
        self.state["started_local"] = datetime.now().isoformat(timespec="seconds")
        self.save_state()
        self.write_environment()

    # -- experiment parts --------------------------------------------
    def run_trial(self, trial: Trial, total: int) -> None:
        label = trial.action if trial.action != "무변화" else trial.condition
        text = INSTRUCTIONS[label].format(item=trial.item)
        self.poll_quietly()
        baseline = self.collector.last_id()
        motion_before = self.collector.latest_motion()
        self.save_scene(f"trial{trial.no:03d}_before")
        target = trial.item or trial.condition
        answer = self.ask(f"\n[{trial.no}/{total}] {trial.action} · {target} — {text} Enter (s=건너뛰기) ").strip().lower()
        if answer == "s":
            self.say("  건너뜀(기록하지 않음)")
            return
        started = now_utc()
        self.poll_quietly()
        window = self.wait_for_reaction(baseline, trial.action)
        result, events = decide_result(window)
        self.save_scene(f"trial{trial.no:03d}_after")
        expected = "반응 없음" if trial.action == "무변화" else trial.action
        mark = "맞음" if result == expected else f"다름(정답: {expected})"
        extra = [event_kind(e) for e in events[1:]]
        memo = f"추가 사건: {', '.join(extra)}" if extra else ""
        item_id = events[0].get("item_id") if events and result == "등록" == trial.action else ""
        latency = motion_to_event_seconds(events[0], self.collector.marks(), motion_before) if events else None
        timing = f" · {latency:.1f}초" if latency is not None else ""
        self.say(f"  → 시스템 결과: {result} · {mark}{timing}{' · ' + memo if memo else ''}")
        self.state.setdefault("trials", []).append({
            "번호": trial.no, "조건": trial.condition, "행동": trial.action, "물품": trial.item,
            "결과": result, "AI이름": "", "AI분류": "", "메모": memo, "item_id": item_id or "",
            "시작": iso(started), "종료": iso(now_utc()),
            "감지지연_s": "" if latency is None else f"{latency:.2f}", "AI결과": "",
        })
        self.save_state()
        if result != expected:
            self.say(self.repair_hint(trial, result))
            self.pause("  상태를 맞췄으면")
            self.poll_quietly()

    @staticmethod
    def repair_hint(trial: Trial, result: str) -> str:
        if trial.action == "등록" and result != "등록":
            return "  도움말: 물품을 치웠다가 다시 놓아 화면에 등록되게 해 주세요(기록하지 않음)."
        if result == "등록" and trial.action != "등록":
            return "  도움말: 잘못 생긴 물품 카드는 관리자 화면에서 '감지 제외'로 정리해 주세요."
        if trial.action == "제거" and result in ("반응 없음", "확인 필요"):
            return "  도움말: 관리자 화면에서 해당 물품을 '회수'로 처리해 주세요."
        if trial.action == "이동":
            return "  도움말: 화면의 물품 위치가 실제와 다르면 물품을 원래 자리로 돌려놓고 기다려 주세요."
        return "  도움말: 화면 상태가 실제와 다르면 관리자 화면에서 정리해 주세요."

    def review_ai(self, items: list[dict[str, str]]) -> None:
        category_of = {i["name"]: i["category"] for i in items}
        rows = [
            r for r in self.state.get("trials", [])
            if r["행동"] == "등록" and r["결과"] == "등록" and r.get("item_id") and not r.get("AI이름")
        ]
        if not rows:
            return
        self.say("\nAI가 붙인 이름을 확인합니다. 분류는 자동으로 채점합니다.")
        for row in rows:
            item = self.wait_classified(row["item_id"])
            if item is None:
                row["메모"] = (row.get("메모", "") + " AI 결과 조회 실패").strip()
                continue
            name = item.get("name", "")
            ai_category = CATEGORY_LABELS.get(item.get("category", ""), item.get("category", ""))
            actual = row["물품"]
            if name == PENDING_NAME:
                row["AI이름"], row["AI분류"] = "X", "X"
                row["메모"] = (row.get("메모", "") + " AI 분석 미완료").strip()
            else:
                guess = "O" if actual and actual in name else "X"
                answer = self.ask(
                    f"  [{row['번호']}] 실제 '{actual}' → AI '{name}' ({ai_category}). "
                    f"이름 맞음? Enter={guess}, o/x 입력 가능: "
                ).strip().lower()
                row["AI이름"] = "O" if answer == "o" else "X" if answer == "x" else guess
                row["AI분류"] = "O" if ai_category == category_of.get(actual) else "X"
                row["AI결과"] = f"{name} ({ai_category})"
            self.save_item_image(item, f"trial{int(row['번호']):03d}_item{row['item_id']}.jpg")
            self.save_state()

    def wait_classified(self, item_id: Any, limit: float = 30.0) -> dict[str, Any] | None:
        started = self.clock()
        item = None
        while self.clock() - started < limit:
            try:
                item = self.api.get(f"/api/items/{item_id}")
            except ApiError:
                item = None
            if item and item.get("name") != PENDING_NAME:
                return item
            self.sleep(2.0)
        return item

    def run_function_checks(self) -> None:
        if self.state.get("function_checks") is not None:
            return
        answer = self.pause(
            "\n[관리 기능 점검] 보관 중인 물품 1개로 수정·검토·기한 연장·만료 알림·폐기·복원·회수·감지 제외를\n"
            "  실제 Pi에서 자동으로 확인하고 원래대로 돌려놓습니다(약 1–2분). 메일 설정이 되어 있으면\n"
            "  관리자 메일로 만료 알림·테스트 메일이 발송됩니다. 시작하려면 (s=건너뛰기)"
        )
        if answer == "s":
            self.state["function_checks"] = {"skipped": True, "results": []}
            self.save_state()
            return
        checker = FunctionChecker(self.api, sleep=self.sleep, clock=self.clock)
        results = checker.run()
        for row in results:
            self.say(f"  {row['결과']:>5} · {row['점검']} — {row['내용']}")
        record: dict[str, Any] = {"skipped": False, "results": results, "finished_utc": iso(now_utc())}
        if checker.mail_sent:
            received = self.ask("  관리자 메일함에 Re:Found 메일이 도착했나요? y=도착 / n=안 옴 / Enter=나중에 확인: ")
            record["mail_received"] = {"y": "도착", "n": "안 옴"}.get(received.strip().lower(), "미확인")
        self.state["function_checks"] = record
        self.save_state()
        self.write_function_checks()

    def write_function_checks(self) -> None:
        record = self.state.get("function_checks") or {}
        rows = record.get("results") or []
        if not rows:
            return
        with (self.out / "function_checks.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=("점검", "결과", "내용"))
            writer.writeheader()
            writer.writerows(rows)

    def run_idle(self, minutes: float) -> None:
        if self.state.get("idle_end"):
            return
        self.pause(f"\n무인 감시 {minutes:g}분을 시작합니다. 물품 5개는 그대로 두고 자리를 비워 주세요. 준비되면")
        start = now_utc()
        self.state["idle_start"] = iso(start)
        self.save_state()
        self.save_scene("idle_start")
        self.say("  진행 중… 일찍 끝내려면 Ctrl+C")
        deadline = self.clock() + minutes * 60
        try:
            while self.clock() < deadline:
                self.sleep(5.0)
                self.poll_quietly()
                remaining = int((deadline - self.clock()) // 60)
                if remaining and remaining % 10 == 0 and int(deadline - self.clock()) % 60 < 5:
                    self.say(f"  남은 시간 약 {remaining}분")
        except KeyboardInterrupt:
            self.say("  무인 감시를 일찍 끝냈습니다.")
        self.state["idle_end"] = iso(now_utc())
        self.save_state()
        self.save_scene("idle_end")

    def run(
        self, items_preset: Sequence[str] | None, idle_minutes: float, plan_kwargs: dict[str, int],
        *, function_checks: bool = False,
    ) -> None:
        items = self.ensure_items(items_preset)
        plan = build_plan([i["name"] for i in items], **plan_kwargs)
        done = self.done_numbers()
        first_none = next((t.no for t in plan if t.action == "무변화"), None)
        last_first_round_add = len(items) if plan_kwargs.get("rounds", 2) > 0 else None
        for trial in plan:
            if trial.no in done:
                continue
            if trial.no == first_none:
                self.review_ai(items)
                if not self.state.get("setup_b_done"):
                    self.pause("\n실험 B 준비: 물품 1–5번을 보관대에 올리고 모두 등록되면")
                    self.capture_once("setup_photo", CAPTURE_SETUP_PHOTO)
                    self.state["setup_b_done"] = True
                    self.save_state()
            self.run_trial(trial, len(plan))
            if trial.no == last_first_round_add:
                self.capture_once("dashboard", CAPTURE_DASHBOARD)
        self.review_ai(items)
        if function_checks:
            self.run_function_checks()
            if (self.state.get("function_checks") or {}).get("results"):
                self.capture_once("activity_log", CAPTURE_ACTIVITY)
        if idle_minutes > 0:
            self.run_idle(idle_minutes)


def start_pi_recorder(host: str, remote_csv: str) -> bool:
    command = (
        f"test -f {RECORDER} || {{ echo MISSING; exit 3; }}; mkdir -p {REMOTE_DIR} && "
        f"nohup /opt/refound/.venv/bin/python {RECORDER} --service refound.service "
        f"--output {remote_csv} --disk-path /opt/refound/data --trial-id paper --duration 21600 "
        f"</dev/null >/dev/null 2>&1 & echo STARTED"
    )
    result = subprocess.run(["ssh", "-o", "ConnectTimeout=10", host, command], stdout=subprocess.PIPE, text=True)
    return result.returncode == 0 and "STARTED" in (result.stdout or "")


def stop_pi_recorder(host: str, remote_csv: str, local_csv: Path) -> bool:
    command = f"pkill -TERM -f monitor_pi_resources.py; sleep 2; cat {remote_csv}"
    result = subprocess.run(["ssh", "-o", "ConnectTimeout=10", host, command], stdout=subprocess.PIPE)
    if result.returncode != 0 or not result.stdout:
        return False
    local_csv.write_bytes(result.stdout)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re:Found 논문·최종보고 실험 진행 도우미")
    parser.add_argument("--url", default="http://127.0.0.1:18000", help="웹 화면 주소(SSH 터널)")
    parser.add_argument("--out", type=Path, help="결과 폴더(기본: paper-run-날짜)")
    parser.add_argument("--resume", type=Path, help="중단한 결과 폴더에서 이어서 진행")
    parser.add_argument("--pi", default="refound@refound-pi.local", help="Pi SSH 주소(자원 기록용)")
    parser.add_argument("--no-pi", action="store_true", help="Pi 자원 기록(CPU·온도)을 생략")
    parser.add_argument("--items", help="'지갑/귀중품,우산/일반,…' 형식(생략하면 화면에서 입력)")
    parser.add_argument("--idle-minutes", type=float, default=60.0)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--hand", type=int, default=20)
    parser.add_argument("--light", type=int, default=10)
    parser.add_argument("--shadow", type=int, default=10)
    parser.add_argument("--no-rehearsal", action="store_true", help="시작 전 시연 리허설(녹화·같은 ID 확인) 생략")
    parser.add_argument("--no-function-checks", action="store_true", help="관리 기능 자동 점검 생략")
    parser.add_argument("--no-scenes", action="store_true", help="시도 전후 카메라 장면 저장 생략")
    parser.add_argument("--demo-check", action="store_true",
                        help="발표 직전 점검: 시연 리허설 1회만 하고 끝냄(결과표 없음)")
    parser.add_argument("--demo-item", default="", help="--demo-check에 쓸 물품 이름")
    return parser


def run_demo_check(session: Session, item_name: str) -> int:
    name = item_name.strip() or session.ask("시연에 쓸 물품 이름(예: 텀블러): ").strip() or "시연 물품"
    rehearsal = session.run_rehearsal({"name": name, "category": ""})
    session.record_environment("end")
    if rehearsal.get("skipped"):
        return 0
    ok = rehearsal.get("same_item_id") and all(s["result"] == s["action"] for s in rehearsal["steps"])
    model = ((session.state.get("environment") or {}).get("start") or {}).get("provider") or {}
    print(f"\n시연 점검 {'정상' if ok else '확인 필요'} · AI {model.get('active')} {model.get('model')}")
    print(f"사진·기록: {session.out}")
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prefix = "demo-check" if args.demo_check else "paper-run"
    out = args.resume or args.out or Path(f"{prefix}-{datetime.now():%Y%m%d-%H%M}")
    out.mkdir(parents=True, exist_ok=True)
    api = Api(args.url)
    try:
        api.get("/api/health")
    except ApiError as exc:
        print(f"웹 화면({args.url})에 연결할 수 없습니다. SSH 터널 창이 열려 있는지 확인하세요: {exc}")
        return 2
    session = Session(api, out, scenes=not args.no_scenes)
    session.load_state()
    session.record_environment("start")
    if args.demo_check:
        return run_demo_check(session, args.demo_item)

    items = session.ensure_items([s for s in (args.items or "").split(",") if s.strip()] or None)
    session.ask_environment()
    if not args.no_rehearsal:
        session.run_rehearsal(items[0])
    if not session.state.get("started_at"):
        print("\n본 실험 시작 전: 보관대를 비우고 관리자 화면에서 '시연 초기화'를 눌러 주세요.")
        session.pause("초기화가 끝났으면")
        session.begin_measured_run()

    remote_csv = session.state.get("remote_csv") or f"{REMOTE_DIR}/resources-{datetime.now():%Y%m%d-%H%M%S}.csv"
    if not args.no_pi and not session.state.get("recorder_started"):
        print(f"\nPi 자원 기록을 시작합니다. Pi 비밀번호를 물으면 입력하세요({args.pi}).")
        if start_pi_recorder(args.pi, remote_csv):
            session.state.update(recorder_started=True, remote_csv=remote_csv, pi=args.pi)
            print("  자원 기록 시작됨")
        else:
            print("  자원 기록을 시작하지 못했습니다(CPU·온도 표만 빠집니다). 계속 진행합니다.")
        session.save_state()

    health = HealthLogger(api, out / "health.csv")
    health.start()
    try:
        session.run(None, args.idle_minutes, {
            "rounds": args.rounds, "hand": args.hand, "light": args.light, "shadow": args.shadow,
        }, function_checks=not args.no_function_checks)
    except KeyboardInterrupt:
        print(f"\n중단했습니다. 이어서 하려면: python scripts\\experiments\\run_experiment.py --resume {out}")
        return 130
    finally:
        health.stop()
        session.save_state()
        session.write_trials()
    session.record_environment("end")

    resources = out / "resources.csv"
    if session.state.get("recorder_started") and not resources.exists():
        print("\nPi 자원 기록을 끝내고 가져옵니다. Pi 비밀번호를 물으면 입력하세요.")
        if not stop_pi_recorder(session.state.get("pi", args.pi), session.state["remote_csv"], resources):
            print("  가져오지 못했습니다. 나중에 Pi에서 파일을 복사해 make_paper_tables.py --resources로 다시 집계하세요.")
    idle_start = trial_report._parse_time(session.state.get("idle_start"))
    idle_end = trial_report._parse_time(session.state.get("idle_end"))
    env = json.loads((out / "env.json").read_text(encoding="utf-8"))
    summary = trial_report.build_summary(
        out / "trials.csv", activities=session.experiment_activities(), health=out / "health.csv",
        resources=resources, idle_start=idle_start, idle_end=idle_end, env=env,
        rehearsal=session.state.get("rehearsal"), function_checks=session.state.get("function_checks"),
    )
    target = trial_report.write_outputs(summary, out / "paper-results")
    print(f"\n끝났습니다. 결과표: {target}")
    print(f"발표용 수치: {target.with_name('final_report_values.md')}")
    print(f"이 폴더({out})를 통째로 Claude에게 주면 원고와 발표 자료에 반영합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

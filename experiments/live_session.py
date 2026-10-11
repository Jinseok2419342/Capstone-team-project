"""Guided paper experiment that records results by itself.

The operator only performs each physical action and presses Enter.  The
session reads the system's own reaction from the web API, so nobody has to
copy results from the screen, copy the database, or start separate loggers.
Only the Python standard library is used (it runs on the Windows laptop).

    python scripts/experiments/run_experiment.py
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from . import trial_report

HEALTH_FIELDS = (
    "timestamp_utc", "ok", "phase", "camera_connected", "fps", "processing_ms",
    "frame_sequence", "detected_changes", "pending_changes", "error",
)
TRIAL_FIELDS = ("번호", "조건", "행동", "물품", "결과", "AI이름", "AI분류", "메모", "item_id", "시작", "종료")
CATEGORY_LABELS = {"valuable": "귀중품", "general": "일반", "food": "음식"}
CATEGORY_KEYS = {"귀중품": "valuable", "일반": "general", "음식": "food"}
PENDING_NAME = "분석 중인 새 물품"
REMOTE_DIR = "/opt/refound/data/experiments"
RECORDER = "/opt/refound/scripts/experiments/monitor_pi_resources.py"

# Minimum wait after Enter: settle 3.0 s + stable 1.2 s + analysis margin.
MIN_WAIT_S = 6.0
QUIET_S = 3.0
NO_EVENT_LIMIT_S = {"제거": 30.0}
DEFAULT_NO_EVENT_LIMIT_S = 18.0
EVENT_LIMIT_S = 40.0


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


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


@dataclass
class Collector:
    """Keeps every activity seen through /api/dashboard, deduplicated by id."""

    api: Api
    activities: dict[int, dict[str, Any]] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def poll(self) -> list[dict[str, Any]]:
        payload = self.api.get("/api/dashboard")
        fresh = []
        with self.lock:
            self.camera = payload.get("camera") or {}
            for activity in payload.get("activities") or []:
                key = activity.get("id")
                if isinstance(key, int) and key not in self.activities:
                    self.activities[key] = activity
                    fresh.append(activity)
        return fresh

    def last_id(self) -> int:
        with self.lock:
            return max(self.activities, default=0)

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


class Session:
    def __init__(
        self, api: Api, out_dir: Path, *, ask: Callable[[str], str] = input,
        say: Callable[[str], None] = print, sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.api, self.out = api, out_dir
        self.ask, self.say, self.sleep, self.clock = ask, say, sleep, clock
        self.collector = Collector(api)
        self.state_path = out_dir / "session.json"
        self.state: dict[str, Any] = {}

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

    # -- interaction helpers -----------------------------------------
    def pause(self, message: str) -> str:
        return self.ask(f"{message} [Enter] ").strip().lower()

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

    # -- experiment parts --------------------------------------------
    def run_trial(self, trial: Trial, total: int) -> None:
        label = trial.action if trial.action != "무변화" else trial.condition
        text = INSTRUCTIONS[label].format(item=trial.item)
        self.poll_quietly()
        baseline = self.collector.last_id()
        target = trial.item or trial.condition
        answer = self.ask(f"\n[{trial.no}/{total}] {trial.action} · {target} — {text} Enter (s=건너뛰기) ").strip().lower()
        if answer == "s":
            self.say("  건너뜀(기록하지 않음)")
            return
        started = now_utc()
        self.poll_quietly()
        window = self.wait_for_reaction(baseline, trial.action)
        result, events = decide_result(window)
        expected = "반응 없음" if trial.action == "무변화" else trial.action
        mark = "맞음" if result == expected else f"다름(정답: {expected})"
        extra = [event_kind(e) for e in events[1:]]
        memo = f"추가 사건: {', '.join(extra)}" if extra else ""
        item_id = events[0].get("item_id") if events and result == "등록" == trial.action else ""
        self.say(f"  → 시스템 결과: {result} · {mark}{' · ' + memo if memo else ''}")
        self.state.setdefault("trials", []).append({
            "번호": trial.no, "조건": trial.condition, "행동": trial.action, "물품": trial.item,
            "결과": result, "AI이름": "", "AI분류": "", "메모": memo, "item_id": item_id or "",
            "시작": iso(started), "종료": iso(now_utc()),
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
        images = self.out / "images"
        images.mkdir(exist_ok=True)
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
            if item.get("image_url"):
                try:
                    (images / f"trial{int(row['번호']):03d}_item{row['item_id']}.jpg").write_bytes(
                        self.api.get_bytes(item["image_url"])
                    )
                except ApiError:
                    pass
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

    def run_idle(self, minutes: float) -> None:
        if self.state.get("idle_end"):
            return
        self.pause(f"\n무인 감시 {minutes:g}분을 시작합니다. 물품 5개는 그대로 두고 자리를 비워 주세요. 준비되면")
        start = now_utc()
        self.state["idle_start"] = iso(start)
        self.save_state()
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

    def run(self, items_preset: Sequence[str] | None, idle_minutes: float, plan_kwargs: dict[str, int]) -> None:
        items = self.ensure_items(items_preset)
        plan = build_plan([i["name"] for i in items], **plan_kwargs)
        done = self.done_numbers()
        first_none = next(t.no for t in plan if t.action == "무변화")
        for trial in plan:
            if trial.no in done:
                continue
            if trial.no == first_none:
                self.review_ai(items)
                if not self.state.get("setup_b_done"):
                    self.pause("\n실험 B 준비: 물품 1–5번을 보관대에 올리고 모두 등록되면")
                    self.state["setup_b_done"] = True
                    self.save_state()
            self.run_trial(trial, len(plan))
        self.review_ai(items)
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
    parser = argparse.ArgumentParser(description="Re:Found 논문 실험 진행 도우미")
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = args.resume or args.out or Path(f"paper-run-{datetime.now():%Y%m%d-%H%M}")
    out.mkdir(parents=True, exist_ok=True)
    api = Api(args.url)
    try:
        api.get("/api/health")
    except ApiError as exc:
        print(f"웹 화면({args.url})에 연결할 수 없습니다. SSH 터널 창이 열려 있는지 확인하세요: {exc}")
        return 2
    session = Session(api, out)
    session.load_state()
    if not session.state.get("started_at"):
        print("시작 전: 보관대를 비우고 관리자 화면에서 '시연 초기화'를 눌러 주세요.")
        session.pause("초기화가 끝났으면")
        session.state["started_at"] = iso(now_utc())
    session.save_state()

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
    items = [s for s in (args.items or "").split(",") if s.strip()] or None
    try:
        session.run(items, args.idle_minutes, {
            "rounds": args.rounds, "hand": args.hand, "light": args.light, "shadow": args.shadow,
        })
    except KeyboardInterrupt:
        print(f"\n중단했습니다. 이어서 하려면: python scripts\\experiments\\run_experiment.py --resume {out}")
        return 130
    finally:
        health.stop()
        session.save_state()
        session.write_trials()

    resources = out / "resources.csv"
    if session.state.get("recorder_started") and not resources.exists():
        print("\nPi 자원 기록을 끝내고 가져옵니다. Pi 비밀번호를 물으면 입력하세요.")
        if not stop_pi_recorder(session.state.get("pi", args.pi), session.state["remote_csv"], resources):
            print("  가져오지 못했습니다. 나중에 Pi에서 파일을 복사해 make_paper_tables.py --resources로 다시 집계하세요.")
    idle_start = trial_report._parse_time(session.state.get("idle_start"))
    idle_end = trial_report._parse_time(session.state.get("idle_end"))
    summary = trial_report.build_summary(
        out / "trials.csv", activities=session.collector.dump(), health=out / "health.csv",
        resources=resources, idle_start=idle_start, idle_end=idle_end,
    )
    target = trial_report.write_outputs(summary, out / "paper-results")
    print(f"\n끝났습니다. 결과표: {target}")
    print(f"이 폴더({out})를 통째로 Claude에게 주면 원고에 반영합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

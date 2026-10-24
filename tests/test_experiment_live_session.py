import csv
import json
import tempfile
import threading
import unittest
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from experiments import live_session, trial_report
from experiments.live_session import (
    FunctionChecker, Session, build_plan, decide_result, event_kind, motion_to_event_seconds,
)


JPEG = b"\xff\xd8fake-frame\xff\xd9"


class FakeApi:
    """In-memory stand-in for the Re:Found web API, with the Pi's clock."""

    def __init__(self):
        self.activities = []
        self.items = {}
        self.next_id = 1
        self.next_item = 1
        self.now = 1_792_000_000.0
        self.last_motion_at = None
        self.frames = 0

    def stamp(self):
        return datetime.fromtimestamp(self.now, timezone.utc).isoformat(timespec="microseconds")

    def act(self, seconds):
        """The hand leaves the shelf now; the system records ``seconds`` later."""
        self.last_motion_at = self.now
        self.now += seconds

    def add(self, kind, source, item_id=None):
        self.activities.append({
            "id": self.next_id, "type": kind, "item_id": item_id,
            "metadata": {"source": source} if source else {},
            "created_at": self.stamp(),
        })
        self.next_id += 1
        self.now += 0.5

    def register(self, name, category, ai_seconds=3.0):
        item_id = self.next_item
        self.next_item += 1
        self.items[item_id] = {"id": item_id, "name": name, "category": category, "image_url": None}
        self.add("item_detected", "camera", item_id)
        self.now += ai_seconds - 0.5
        self.add("item_classified", None, item_id)
        return item_id

    def get(self, path):
        if path == "/api/dashboard":
            camera = {"phase": "monitoring", "pending_changes": 0, "last_motion_at": self.last_motion_at}
            return {"camera": camera, "activities": self.activities[-30:][::-1], "notifications": []}
        if path.startswith("/api/items/"):
            return self.items[int(path.rsplit("/", 1)[1])]
        if path == "/api/settings":
            return {"settings": {"camera_width": 1280, "admin_email": "secret@example.com"}}
        return {"ok": True, "time": self.stamp(), "camera": {"frame_width": 1280},
                "provider": {"requested": "auto", "active": "openai", "model": "gpt-test"}}

    def get_bytes(self, path):
        return b""

    def grab_frame(self):
        self.frames += 1
        return JPEG


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class PureFunctionTests(unittest.TestCase):
    def test_event_kind_mapping(self):
        self.assertEqual(event_kind({"type": "item_detected", "metadata": {"source": "camera"}}), "등록")
        self.assertEqual(event_kind({"type": "item_detected", "metadata": {"source": "demo"}}), None)
        self.assertEqual(event_kind({"type": "item_recovered", "metadata": {"source": "camera_ai_verification"}}), "제거")
        self.assertEqual(event_kind({"type": "recovery_check_inconclusive", "metadata": {"source": "camera_ai_verification"}}), "확인 필요")
        self.assertEqual(event_kind({"type": "item_classified", "metadata": {}}), None)
        # A manual recovery from the function check is not a camera event.
        self.assertEqual(event_kind({"type": "item_recovered", "metadata": {}}), None)

    def test_decide_result_uses_first_event(self):
        rows = [
            {"id": 5, "type": "item_moved", "metadata": {"source": "camera"}},
            {"id": 4, "type": "item_detected", "metadata": {"source": "camera"}},
        ]
        result, events = decide_result(rows)
        self.assertEqual(result, "등록")
        self.assertEqual(len(events), 2)
        self.assertEqual(decide_result([])[0], "반응 없음")

    def test_plan_matches_trial_sheet(self):
        plan = build_plan([f"물품{i}" for i in range(1, 11)])
        self.assertEqual(len(plan), 100)
        self.assertEqual([t.action for t in plan[:3]], ["등록", "등록", "등록"])
        self.assertEqual(plan[30].action, "등록")
        self.assertEqual(plan[60].condition, "손")
        self.assertEqual(plan[99].condition, "그림자")

    def test_motion_latency_uses_only_this_trials_motion(self):
        event = {"created_at": "2026-10-25T05:00:10+00:00"}
        created = datetime(2026, 10, 25, 5, 0, 10, tzinfo=timezone.utc).timestamp()
        marks = [created - 30.0, created - 5.25, created + 2.0]
        # The newest motion before the record, not the later one.
        self.assertEqual(motion_to_event_seconds(event, marks, after=created - 30.0), 5.25)
        # Nothing new since the trial started: no latency rather than a wrong one.
        self.assertIsNone(motion_to_event_seconds(event, marks[:1], after=created - 30.0))
        self.assertIsNone(motion_to_event_seconds({"created_at": ""}, marks, after=None))
        # An implausibly old motion belongs to something else.
        self.assertIsNone(motion_to_event_seconds(event, [created - 500.0], after=None))


class SessionTests(unittest.TestCase):
    def test_guided_run_records_results_and_builds_tables(self):
        api = FakeApi()
        clock = FakeClock()
        names = {"지갑": "valuable", "우산": "general"}
        registered = {}
        prompts = []

        def ask(prompt):
            prompts.append(prompt)
            if "이름 맞음?" in prompt:
                return ""  # accept the automatic guess
            if "] 등록 · " in prompt:
                name = prompt.split("] 등록 · ")[1].split(" —")[0]
                api.act(5.2)
                # The umbrella is named oddly by the model, the wallet correctly.
                registered[name] = api.register("검은 지갑" if name == "지갑" else "막대", names[name])
            elif "] 이동 · 우산" in prompt:
                api.act(4.8)
                api.add("item_detected", "camera", 99)  # move mistaken for a new item
            elif "] 이동 · " in prompt:
                api.act(4.6)
                api.add("item_moved", "camera", registered["지갑"])
            elif "] 제거 · " in prompt:
                name = prompt.split("] 제거 · ")[1].split(" —")[0]
                api.act(4.4)
                api.add("item_recovered", "camera", registered[name])
            elif "] 무변화 · 조명" in prompt:
                api.now += 7.0  # no hand motion: a lighting change creates the record
                api.add("item_detected", "camera", 98)
            return ""

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            session = Session(api, out, ask=ask, say=lambda _: None, sleep=clock.sleep, clock=clock)
            session.run(["지갑/귀중품", "우산/일반"], idle_minutes=0,
                        plan_kwargs={"rounds": 1, "hand": 2, "light": 1, "shadow": 1})
            trials_path = session.write_trials()
            with trials_path.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r["결과"] for r in rows], [
                "등록", "등록", "이동", "등록", "제거", "제거", "반응 없음", "반응 없음", "등록", "반응 없음",
            ])
            wallet = rows[0]
            self.assertEqual((wallet["AI이름"], wallet["AI분류"]), ("O", "O"))
            self.assertEqual(wallet["AI결과"], "검은 지갑 (귀중품)")
            self.assertEqual(wallet["감지지연_s"], "5.20")
            umbrella = rows[1]
            self.assertEqual((umbrella["AI이름"], umbrella["AI분류"]), ("X", "O"))
            self.assertEqual(rows[2]["감지지연_s"], "4.60")
            # The lighting false positive had no hand motion of its own.
            self.assertEqual(rows[8]["감지지연_s"], "")
            # A mismatch asks the operator to repair the scene before moving on.
            self.assertTrue(any("상태를 맞췄으면" in p for p in prompts))
            # Screens are requested once at the right moments.
            self.assertEqual(sum("[캡처] 지금 화면 캡처" in p for p in prompts), 1)
            self.assertEqual(sum("[사진]" in p for p in prompts), 1)
            # Every trial keeps the camera scene before and after.
            self.assertEqual(len(list((out / "scenes").glob("trial*_before.jpg"))), 10)
            self.assertEqual((out / "scenes" / "trial001_after.jpg").read_bytes(), JPEG)

            summary = trial_report.build_summary(trials_path, activities=session.collector.dump())
            self.assertAlmostEqual(summary["trials"]["accuracy"], 8 / 10)
            self.assertEqual(summary["trials"]["none_false_events"]["조명"]["false_events"], 1)
            self.assertEqual(summary["database"]["added"], 4)
            latency = summary["latency"]
            self.assertEqual(latency["by_kind"]["등록"]["n"], 2)
            self.assertAlmostEqual(latency["by_kind"]["등록"]["median"], 5.2)
            # Motion end -> record (5.2 s) + record -> AI result (3.0 s).
            self.assertAlmostEqual(latency["motion_to_ai"]["median"], 8.2, places=2)
            self.assertEqual([f["no"] for f in summary["failed_trials"]], ["4", "9"])
            self.assertEqual([m["item"] for m in summary["ai_mistakes"]], ["우산"])
            saved = json.loads((out / "activities.json").read_text(encoding="utf-8"))
            self.assertEqual(len(saved), len(api.activities))

            target = trial_report.write_outputs(summary, out / "paper-results")
            final = (out / "paper-results" / "final_report_values.md").read_text(encoding="utf-8")
            self.assertIn("| 사건 판정 정확도 | 80.0%", final)
            self.assertIn("움직임 종료 → 화면에 AI 이름·분류 | 중앙값 8.2초", final)
            self.assertIn("scenes/trial009_after.jpg", final)
            self.assertIn("등록: 움직임 종료 → 사건 기록 중앙값 5.2 s", target.read_text(encoding="utf-8"))

            checks = {"results": [
                {"점검": "점검 대상 물품", "결과": "통과", "내용": "ID 1"},
                {"점검": "폐기 처리", "결과": "통과", "내용": ""},
                {"점검": "수동 회수", "결과": "실패", "내용": "HTTP 409"},
                {"점검": "관리자 테스트 메일", "결과": "해당 없음", "내용": "메일(SMTP) 미설정"},
            ]}
            summary = trial_report.build_summary(trials_path, function_checks=checks)
            # The target row and a not-applicable mail step are not counted.
            self.assertIn("통과 1 / 2항목", trial_report.render_final_report(summary))

    def test_resume_skips_completed_trials(self):
        api = FakeApi()
        clock = FakeClock()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = Session(api, out, ask=lambda p: "s" if "] " in p else "", say=lambda _: None,
                            sleep=clock.sleep, clock=clock)
            first.state["items"] = [{"name": "지갑", "category": "귀중품"}]
            first.state["trials"] = [{"번호": 1, "조건": "일반", "행동": "등록", "물품": "지갑", "결과": "등록"}]
            first.save_state()
            seen = []
            second = Session(api, out, ask=lambda p: seen.append(p) or "s", say=lambda _: None,
                             sleep=clock.sleep, clock=clock)
            second.load_state()
            second.run(None, idle_minutes=0, plan_kwargs={"rounds": 1, "hand": 0, "light": 0, "shadow": 1})
            trial_prompts = [p for p in seen if p.startswith("\n[")]
            self.assertTrue(trial_prompts[0].startswith("\n[2/"))

    def test_rehearsal_keeps_same_id_evidence_outside_the_measured_run(self):
        api = FakeApi()
        clock = FakeClock()
        prompts = []
        state = {}

        def ask(prompt):
            prompts.append(prompt)
            if "[리허설] 등록" in prompt:
                api.act(5.0)
                state["id"] = api.register("스테인리스 텀블러", "general", ai_seconds=4.0)
            elif "[리허설] 이동" in prompt:
                api.act(4.5)
                api.add("item_moved", "camera", state["id"])
            elif "[리허설] 제거" in prompt:
                api.act(4.0)
                api.add("item_recovered", "camera", state["id"])
            return ""

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            session = Session(api, out, ask=ask, say=lambda _: None, sleep=clock.sleep, clock=clock)
            rehearsal = session.run_rehearsal({"name": "텀블러", "category": "일반"})
            self.assertTrue(rehearsal["same_item_id"])
            self.assertEqual([s["result"] for s in rehearsal["steps"]], ["등록", "이동", "제거"])
            self.assertEqual([s["latency_s"] for s in rehearsal["steps"]], [5.0, 4.5, 4.0])
            self.assertEqual(rehearsal["ai"]["name"], "스테인리스 텀블러")
            self.assertEqual(rehearsal["ai"]["classification_s"], 4.0)
            self.assertTrue(any("[녹화]" in p for p in prompts))
            self.assertTrue((out / "scenes" / "rehearsal_2_move_after.jpg").exists())
            # Calling again on resume does not repeat the rehearsal.
            self.assertIs(session.run_rehearsal({"name": "텀블러"}), session.state["rehearsal"])

            session.begin_measured_run()
            api.act(5.0)
            api.register("지갑", "valuable")
            session.poll_quietly()
            measured = session.experiment_activities()
            self.assertEqual([a["type"] for a in measured], ["item_detected", "item_classified"])

    def test_environment_is_recorded_without_mail_settings(self):
        api = FakeApi()
        answers = iter(["32GB", "방열판", "책상 위 60cm", "실습실", "", "y"])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            session = Session(api, out, ask=lambda p: next(answers), say=lambda _: None)
            session.state["items"] = [{"name": "지갑", "category": "귀중품"}, {"name": "우산", "category": "일반"}]
            session.record_environment("start")
            session.ask_environment()
            session.state["started_local"] = "2026-10-25T14:00:00"
            session.write_environment()
            env = json.loads((out / "env.json").read_text(encoding="utf-8"))
            self.assertEqual(env["start"]["provider"]["model"], "gpt-test")
            self.assertNotIn("admin_email", env["start"]["settings"])
            values = trial_report.environment_values(env)
            self.assertEqual(values["EQUIP_STORAGE"], "microSD 32GB")
            self.assertEqual(values["VLM_MODEL_DATE"], "OpenAI gpt-test, 2026-10-25")
            self.assertEqual(values["EXPERIMENT_DATE_PLACE"], "2026년 10월 25일 실습실")
            self.assertEqual(values["NETWORK_CONDITION"], "학교 Wi-Fi에 연결된 노트북 핫스팟")
            self.assertEqual(values["OBJECT_LIST"], "지갑, 우산")


class ClientApi:
    """Adapts FastAPI's TestClient to the session's small API interface."""

    def __init__(self, client):
        self.client = client

    def get(self, path):
        response = self.client.get(path)
        response.raise_for_status()
        return response.json()

    def send(self, method, path, payload=None):
        response = self.client.request(method, path, json=payload)
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, body


class FunctionCheckerAppTests(unittest.TestCase):
    """Run the management check against the real routes and an isolated DB."""

    def setUp(self):
        from fastapi.testclient import TestClient

        from app import main
        from app.notifier import ExpirationScheduler
        from app.store import Store

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        (root / "captures").mkdir()
        self.store = Store(root / "isolated.sqlite3")
        self.store.initialize()
        self.stack.enter_context(patch.object(main, "store", self.store))
        self.stack.enter_context(patch.object(main, "config", replace(
            main.config, capture_dir=root / "captures", db_path=self.store.db_path,
        )))
        self.stack.enter_context(patch.object(
            main, "scheduler", ExpirationScheduler(self.store, main.notifier, interval_seconds=60),
        ))
        self.stack.enter_context(patch.object(main, "classification_slots", threading.BoundedSemaphore(1)))
        self.stack.enter_context(patch.object(main.vision, "get_status", return_value={}))
        self.client = TestClient(main.app)  # no lifespan: no camera, SMTP or AI
        self.stack.callback(self.client.close)
        now = datetime.now(timezone.utc)
        self.item = self.store.create_item({
            "name": "검은 카드지갑", "category": "valuable", "retention_days": 90,
            "detected_at": now, "expires_at": now + timedelta(days=90), "status": "stored",
            "source_kind": "camera", "review_status": "confirmed", "provider": "openai",
        })
        self.store.create_item({"name": "시연 물품", "status": "stored", "source_kind": "demo"})

    def test_every_management_step_passes_and_the_item_is_put_back(self):
        clock = FakeClock()
        checker = FunctionChecker(ClientApi(self.client), sleep=clock.sleep, clock=clock, notification_wait=5.0)
        results = checker.run()
        outcomes = {row["점검"]: row["결과"] for row in results}
        failed = {step: row["내용"] for row in results if row["결과"] == "실패" for step in [row["점검"]]}
        self.assertEqual(failed, {})
        self.assertEqual(outcomes["점검 대상 물품"], "통과")
        self.assertEqual(outcomes["만료 알림 생성·메일 발송"], "통과")
        self.assertEqual(outcomes["처리 이력 연결"], "통과")
        # Without SMTP settings the e-mail test is reported as not applicable.
        self.assertEqual(outcomes["관리자 테스트 메일"], "해당 없음")
        self.assertFalse(checker.mail_sent)
        item = self.store.get_item(self.item["id"])
        self.assertEqual(item["name"], "검은 카드지갑")
        self.assertEqual(item["expires_at"], self.item["expires_at"])
        self.assertEqual((item["status"], item["review_status"]), ("stored", "confirmed"))

    def test_missing_target_is_a_failure_not_a_crash(self):
        self.store.apply_item_action(self.item["id"], "dismiss")
        results = FunctionChecker(ClientApi(self.client), sleep=lambda _: None).run()
        self.assertEqual([(r["점검"], r["결과"]) for r in results], [("점검 대상 물품", "실패")])


class ApiFrameTests(unittest.TestCase):
    def test_grab_frame_reads_one_jpeg_from_the_mjpeg_stream(self):
        chunks = [b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8abc", b"def\xff\xd9\r\n--frame\r\n", b""]

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read1(self, size):
                return chunks.pop(0)

        with patch.object(live_session.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual(live_session.Api("http://pi").grab_frame(), b"\xff\xd8abcdef\xff\xd9")


if __name__ == "__main__":
    unittest.main()

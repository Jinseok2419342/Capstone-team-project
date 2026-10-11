import csv
import json
import tempfile
import unittest
from pathlib import Path

from experiments import live_session, trial_report
from experiments.live_session import Session, build_plan, decide_result, event_kind


class FakeApi:
    """In-memory stand-in for the Re:Found web API."""

    def __init__(self):
        self.activities = []
        self.items = {}
        self.next_id = 1
        self.next_item = 1

    def add(self, kind, source, item_id=None):
        self.activities.append({
            "id": self.next_id, "type": kind, "item_id": item_id,
            "metadata": {"source": source} if source else {},
            "created_at": f"2026-10-20T05:{self.next_id // 60:02d}:{self.next_id % 60:02d}+00:00",
        })
        self.next_id += 1

    def register(self, name, category):
        item_id = self.next_item
        self.next_item += 1
        self.items[item_id] = {"id": item_id, "name": name, "category": category, "image_url": None}
        self.add("item_detected", "camera", item_id)
        self.add("item_classified", None, item_id)
        return item_id

    def get(self, path):
        if path == "/api/dashboard":
            return {"camera": {"phase": "monitoring", "pending_changes": 0}, "activities": self.activities[-30:][::-1]}
        if path.startswith("/api/items/"):
            return self.items[int(path.rsplit("/", 1)[1])]
        return {"ok": True, "camera": {}}

    def get_bytes(self, path):
        return b""


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
                # The umbrella is named oddly by the model, the wallet correctly.
                registered[name] = api.register("검은 지갑" if name == "지갑" else "막대", names[name])
            elif "] 이동 · 우산" in prompt:
                api.add("item_detected", "camera", 99)  # move mistaken for a new item
            elif "] 이동 · " in prompt:
                api.add("item_moved", "camera", registered["지갑"])
            elif "] 제거 · " in prompt:
                name = prompt.split("] 제거 · ")[1].split(" —")[0]
                api.add("item_recovered", "camera", registered[name])
            elif "] 무변화 · 조명" in prompt:
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
            umbrella = rows[1]
            self.assertEqual((umbrella["AI이름"], umbrella["AI분류"]), ("X", "O"))
            # A mismatch asks the operator to repair the scene before moving on.
            self.assertTrue(any("상태를 맞췄으면" in p for p in prompts))

            summary = trial_report.build_summary(trials_path, activities=session.collector.dump())
            self.assertAlmostEqual(summary["trials"]["accuracy"], 8 / 10)
            self.assertEqual(summary["trials"]["none_false_events"]["조명"]["false_events"], 1)
            self.assertEqual(summary["database"]["added"], 4)
            saved = json.loads((out / "activities.json").read_text(encoding="utf-8"))
            self.assertEqual(len(saved), len(api.activities))

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


if __name__ == "__main__":
    unittest.main()

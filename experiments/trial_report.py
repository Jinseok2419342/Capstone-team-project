"""Turn the simple paper trial sheet and run logs into the paper's result tables (Tables 5-8).

Only the Python standard library is used so the script also runs on the
Windows laptop without installing the application dependencies.

Inputs (all but the trial sheet are optional):

* trial sheet CSV  - one row per trial, filled in by hand while watching the
  administrator screen (see ``docs/paper/TRIAL_SHEET_TEMPLATE.csv``)
* SQLite database  - a copy of the Pi's ``lost_items.db`` taken after the run
* health CSV       - ``scripts/experiments/poll_health.py`` output
* resources CSV    - ``scripts/experiments/monitor_pi_resources.py`` output
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


EVENT_KINDS = ("등록", "이동", "제거")
GT_KINDS = EVENT_KINDS + ("무변화",)
RESULT_KINDS = EVENT_KINDS + ("확인 필요", "반응 없음")
NONE_CONDITIONS = ("손", "조명", "그림자")

_ACTION_ALIASES = {
    "등록": "등록", "추가": "등록", "add": "등록", "added": "등록",
    "이동": "이동", "move": "이동", "moved": "이동",
    "제거": "제거", "회수": "제거", "remove": "제거", "removed": "제거",
    "무변화": "무변화", "없음": "무변화", "none": "무변화",
}
_RESULT_ALIASES = {
    **{k: v for k, v in _ACTION_ALIASES.items() if v != "무변화"},
    "확인필요": "확인 필요", "확인 필요": "확인 필요", "review": "확인 필요",
    "반응없음": "반응 없음", "반응 없음": "반응 없음", "없음": "반응 없음",
    "무반응": "반응 없음", "none": "반응 없음",
}
_CONDITION_ALIASES = {
    "": "일반", "일반": "일반", "normal": "일반",
    "손": "손", "hand": "손",
    "조명": "조명", "light": "조명",
    "그림자": "그림자", "shadow": "그림자",
}
_COLUMN_ALIASES = {
    "번호": "no", "no": "no",
    "조건": "condition", "condition": "condition",
    "행동": "action", "action": "action",
    "결과": "result", "result": "result",
    "ai이름": "ai_name", "ai_name": "ai_name",
    "ai분류": "ai_category", "ai_category": "ai_category",
    "메모": "note", "note": "note",
}

# Activities written by app/main.py and app/classification.py.
_VERIFY_SOURCE = "camera_ai_verification"
_CLASSIFICATION_DONE = ("item_classified", "classification_inconclusive")


class TrialSheetError(ValueError):
    """Raised with a row number when the hand-filled sheet is malformed."""


@dataclass(frozen=True)
class Trial:
    no: str
    condition: str
    action: str
    result: str
    ai_name: bool | None
    ai_category: bool | None


def _key(text: str) -> str:
    return "".join(str(text).split()).lower()


def _mark(value: str, row: int, column: str) -> bool | None:
    text = _key(value)
    if text in ("", "-", "해당없음", "na"):
        return None
    if text in ("o", "ㅇ", "맞음", "y", "yes", "1", "true"):
        return True
    if text in ("x", "틀림", "n", "no", "0", "false"):
        return False
    raise TrialSheetError(f"{row}행 {column}: O 또는 X로 적어 주세요 (입력값: {value!r})")


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise TrialSheetError(f"{path}: UTF-8 또는 CP949 CSV로 저장해 주세요")


def read_trials(path: Path) -> list[Trial]:
    reader = csv.DictReader(_read_text(Path(path)).splitlines())
    columns = {name: _COLUMN_ALIASES.get(_key(name)) for name in reader.fieldnames or ()}
    missing = {"action", "result"} - set(columns.values())
    if missing:
        raise TrialSheetError("기록지에 '행동'과 '결과' 열이 필요합니다")
    trials: list[Trial] = []
    for row_number, raw in enumerate(reader, start=2):
        row = {columns[k]: (v or "").strip() for k, v in raw.items() if k in columns and columns[k]}
        if not row.get("action") and not row.get("result"):
            continue  # blank line left in the spreadsheet
        action = _ACTION_ALIASES.get(_key(row.get("action", "")))
        if action is None:
            raise TrialSheetError(f"{row_number}행 행동: 등록/이동/제거/무변화 중 하나여야 합니다")
        result_key = _key(row.get("result", ""))
        result = _RESULT_ALIASES.get(result_key)
        if result is None:
            raise TrialSheetError(
                f"{row_number}행 결과: 등록/이동/제거/확인 필요/반응 없음 중 하나여야 합니다"
            )
        condition = _CONDITION_ALIASES.get(_key(row.get("condition", "")))
        if condition is None:
            raise TrialSheetError(f"{row_number}행 조건: 일반/손/조명/그림자 중 하나여야 합니다")
        if action == "무변화" and condition == "일반":
            condition = "손"
        trials.append(
            Trial(
                no=row.get("no", str(len(trials) + 1)),
                condition=condition,
                action=action,
                result=result,
                ai_name=_mark(row.get("ai_name", ""), row_number, "AI이름"),
                ai_category=_mark(row.get("ai_category", ""), row_number, "AI분류"),
            )
        )
    if not trials:
        raise TrialSheetError("기록된 시도가 없습니다")
    return trials


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (math.nan, math.nan)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def is_correct(trial: Trial) -> bool:
    if trial.action == "무변화":
        return trial.result == "반응 없음"
    return trial.result == trial.action


def summarize_trials(trials: Sequence[Trial]) -> dict[str, Any]:
    confusion = {gt: {res: 0 for res in RESULT_KINDS} for gt in GT_KINDS}
    for trial in trials:
        confusion[trial.action][trial.result] += 1
    per_kind: dict[str, dict[str, Any]] = {}
    for kind in EVENT_KINDS:
        tp = confusion[kind][kind]
        fp = sum(confusion[gt][kind] for gt in GT_KINDS if gt != kind)
        fn = sum(confusion[kind].values()) - tp
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        f1 = _ratio(2 * tp, 2 * tp + fp + fn)
        per_kind[kind] = {
            "support": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1,
        }
    macro = {
        metric: statistics.fmean(v for v in (per_kind[k][metric] for k in EVENT_KINDS) if v is not None)
        if any(per_kind[k][metric] is not None for k in EVENT_KINDS) else None
        for metric in ("precision", "recall", "f1")
    }
    correct = sum(is_correct(t) for t in trials)
    low, high = wilson_interval(correct, len(trials))
    none_fp: dict[str, dict[str, int]] = {}
    for condition in NONE_CONDITIONS:
        group = [t for t in trials if t.action == "무변화" and t.condition == condition]
        none_fp[condition] = {
            "trials": len(group),
            "false_events": sum(t.result in EVENT_KINDS for t in group),
            "review_requests": sum(t.result == "확인 필요" for t in group),
        }
    registered = [t for t in trials if t.action == "등록" and t.result == "등록"]
    name_marks = [t.ai_name for t in registered if t.ai_name is not None]
    category_marks = [t.ai_category for t in registered if t.ai_category is not None]
    return {
        "trials": len(trials),
        "counts": {gt: sum(confusion[gt].values()) for gt in GT_KINDS},
        "confusion": confusion,
        "accuracy": correct / len(trials),
        "accuracy_ci95": [low, high],
        "per_kind": per_kind,
        "macro": macro,
        "none_false_events": none_fp,
        "nuisance_false_events": none_fp["조명"]["false_events"] + none_fp["그림자"]["false_events"],
        "ai_name_accuracy": _ratio(sum(name_marks), len(name_marks)),
        "ai_name_judged": len(name_marks),
        "ai_category_accuracy": _ratio(sum(category_marks), len(category_marks)),
        "ai_category_judged": len(category_marks),
    }


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # Times typed by the user without an offset are local (KST on the laptop).
    return parsed if parsed.tzinfo is not None else parsed.astimezone()


def _metadata(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _activity_tuples(
    rows: Iterable[dict[str, Any]], since: datetime | None, until: datetime | None,
) -> list[tuple[str, Any, dict[str, Any], datetime]]:
    activities = []
    for row in rows:
        created = _parse_time(row.get("created_at"))
        if created is None:
            continue
        if since is not None and created < since:
            continue
        if until is not None and created > until:
            continue
        meta = row.get("metadata")
        if not isinstance(meta, dict):
            meta = _metadata(row.get("metadata_json"))
        activities.append((row.get("type"), row.get("item_id"), meta, created))
    activities.sort(key=lambda a: a[3])
    return activities


def summarize_database(
    path: Path, *, since: datetime | None = None, until: datetime | None = None,
) -> dict[str, Any]:
    """Summarize the activities table of a copied ``lost_items.db``."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT id, type, item_id, metadata_json, created_at FROM activities ORDER BY created_at, id"
        ).fetchall()
    finally:
        connection.close()
    return summarize_activities([dict(row) for row in rows], since=since, until=until)


def load_activities(path: Path) -> list[dict[str, Any]]:
    """Read ``activities.json`` written by the live experiment session."""
    data = json.loads(_read_text(Path(path)))
    return data if isinstance(data, list) else data.get("activities", [])


def summarize_activities(
    rows: Iterable[dict[str, Any]], *, since: datetime | None = None, until: datetime | None = None,
) -> dict[str, Any]:
    activities = _activity_tuples(rows, since, until)

    def count(kind: str, source: str | None = None) -> int:
        return sum(
            1 for a_type, _, meta, _ in activities
            if a_type == kind and (source is None or meta.get("source") == source)
        )

    added = count("item_detected", "camera")
    moved = count("item_moved", "camera")
    removed_local = count("item_recovered", "camera")
    verify_recovered = count("item_recovered", _VERIFY_SOURCE)
    verify_inconclusive = count("recovery_check_inconclusive", _VERIFY_SOURCE)
    verify_deferred = count("recovery_check_deferred")
    verify_calls = verify_recovered + verify_inconclusive
    detected = added + moved + removed_local + verify_calls + verify_deferred
    ai_calls = added + verify_calls

    started: dict[Any, datetime] = {}
    durations: list[float] = []
    inconclusive = 0
    finished = 0
    for a_type, item_id, meta, created in activities:
        if a_type == "item_detected" and meta.get("source") == "camera":
            started[item_id] = created
        elif a_type in _CLASSIFICATION_DONE and item_id in started:
            durations.append((created - started.pop(item_id)).total_seconds())
            finished += 1
            inconclusive += a_type == "classification_inconclusive"
    review_needed = inconclusive + verify_inconclusive
    review_base = finished + verify_calls
    return {
        "detected_events": detected,
        "added": added,
        "moved": moved,
        "removed_local": removed_local,
        "verify_calls": verify_calls,
        "verify_deferred": verify_deferred,
        "ai_calls": ai_calls,
        "ai_call_ratio": _ratio(ai_calls, detected),
        "classification_seconds": durations,
        "classification_median_s": statistics.median(durations) if durations else None,
        "classification_max_s": max(durations) if durations else None,
        "review_ratio": _ratio(review_needed, review_base),
    }


def _floats(rows: Iterable[dict[str, str]], column: str) -> list[float]:
    values = []
    for row in rows:
        try:
            value = float(row.get(column, "") or "nan")
        except ValueError:
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def _read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(_read_text(Path(path)).splitlines()))


def _mean_max(values: Sequence[float]) -> dict[str, float | None]:
    return {
        "mean": statistics.fmean(values) if values else None,
        "max": max(values) if values else None,
        "n": len(values),
    }


def summarize_health(path: Path) -> dict[str, Any]:
    rows = [
        row for row in _read_csv(path)
        if row.get("camera_connected") in ("1", "true", "True")
        and row.get("phase") not in ("stopped", "privacy", "")
    ]
    sequence = _floats(rows, "frame_sequence")
    processing = [v for v in _floats(rows, "processing_ms") if v > 0]
    return {
        "fps": _mean_max([v for v in _floats(rows, "fps") if v > 0]),
        "processing_ms": _mean_max(processing),
        "frames_processed": int(max(sequence) - min(sequence)) if len(sequence) >= 2 else None,
    }


def summarize_resources(path: Path) -> dict[str, Any]:
    rows = [row for row in _read_csv(path) if row.get("process_alive") in ("1", "true", "True")]
    return {
        "system_cpu_percent": _mean_max(_floats(rows, "system_cpu_percent")),
        "rss_mib": _mean_max(_floats(rows, "rss_mib")),
        "temperature_c": _mean_max(_floats(rows, "temperature_c")),
    }


def _pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}"


def _num(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_markdown(summary: dict[str, Any]) -> str:
    trials = summary["trials"]
    lines = ["# Re:Found 논문 결과표 (자동 생성)", ""]
    lines += ["아래 표를 `PAPER_DRAFT_JDCS.md`의 같은 번호 표에 그대로 붙여넣고, 마지막 목록의 값을 이중 대괄호 자리에 넣는다.", ""]

    lines += ["**표 5. 사건 판정 혼동행렬 / Table 5. Confusion matrix of event decisions**", ""]
    lines += ["| 정답＼결과 | " + " | ".join(RESULT_KINDS) + " |", "|---" * (len(RESULT_KINDS) + 1) + "|"]
    for gt in GT_KINDS:
        row = trials["confusion"][gt]
        lines.append(f"| {gt}({trials['counts'][gt]}) | " + " | ".join(str(row[r]) for r in RESULT_KINDS) + " |")
    lines.append("")

    lines += ["**표 6. 사건 종류별 성능 / Table 6. Performance by event type**", ""]
    lines += ["| 사건 | 정밀도 | 재현율 | F1 |", "|---|---|---|---|"]
    for kind in EVENT_KINDS:
        m = trials["per_kind"][kind]
        lines.append(f"| {kind} | {_num(m['precision'], 3)} | {_num(m['recall'], 3)} | {_num(m['f1'], 3)} |")
    macro = trials["macro"]
    lines.append(f"| 평균 | {_num(macro['precision'], 3)} | {_num(macro['recall'], 3)} | {_num(macro['f1'], 3)} |")
    lines.append("")

    db = summary.get("database")
    lines += ["**표 7. 외부 모델 호출과 인식 결과 / Table 7. External model calls and recognition results**", ""]
    lines += ["| 항목 | 값 |", "|---|---|"]
    if db:
        lines.append(f"| 전체 감지 사건 / 외부 호출(등록·제거 검증) | {db['detected_events']} / {db['ai_calls']} ({db['added']}·{db['verify_calls']}) |")
        lines.append(f"| 호출 비율 | {_pct(db['ai_call_ratio'])}% |")
    else:
        lines.append("| 전체 감지 사건 / 외부 호출(등록·제거 검증) | DB 미입력 |")
        lines.append("| 호출 비율 | DB 미입력 |")
    lines.append(
        f"| 이름 / 분류 정확도 | {_pct(trials['ai_name_accuracy'])}% / {_pct(trials['ai_category_accuracy'])}% "
        f"(n={trials['ai_name_judged']}/{trials['ai_category_judged']}) |"
    )
    if db:
        lines.append(f"| 관리자 확인 필요 비율 | {_pct(db['review_ratio'])}% |")
        lines.append(f"| 처리 시간 중앙값 / 최대 | {_num(db['classification_median_s'])} s / {_num(db['classification_max_s'])} s |")
    else:
        lines += ["| 관리자 확인 필요 비율 | DB 미입력 |", "| 처리 시간 중앙값 / 최대 | DB 미입력 |"]
    lines.append("")

    res = summary.get("resources") or {}
    health = summary.get("health") or {}

    def stat(group: dict[str, Any], key: str) -> tuple[str, str]:
        values = group.get(key) or {}
        return _num(values.get("mean")), _num(values.get("max"))

    lines += ["**표 8. Raspberry Pi 자원 사용량 / Table 8. Resource usage on Raspberry Pi**", ""]
    lines += ["| 항목 | 평균 | 최대 |", "|---|---|---|"]
    for label, group, key in (
        ("장치 CPU 사용률(%)", res, "system_cpu_percent"),
        ("서비스 메모리(MiB)", res, "rss_mib"),
        ("SoC 온도(°C)", res, "temperature_c"),
        ("분석 프레임률(fps)", health, "fps"),
        ("프레임 처리 시간(ms)", health, "processing_ms"),
    ):
        mean, peak = stat(group, key)
        lines.append(f"| {label} | {mean} | {peak} |")
    lines.append("")

    none = trials["none_false_events"]
    values = {
        "N_TRIALS": str(trials["trials"]),
        "ACC_OVERALL": _pct(trials["accuracy"]),
        "ACC_CI": f"{_pct(trials['accuracy_ci95'][0])}–{_pct(trials['accuracy_ci95'][1])}%",
        "MACRO_F1": _num(macro["f1"], 3),
        "HAND_FP": str(none["손"]["false_events"]),
        "LIGHT_FP": str(none["조명"]["false_events"]),
        "SHADOW_FP": str(none["그림자"]["false_events"]),
        "NUISANCE_FP": str(trials["nuisance_false_events"]),
        "AI_NAME_ACC": _pct(trials["ai_name_accuracy"]),
        "AI_CATEGORY_ACC": _pct(trials["ai_category_accuracy"]),
    }
    if db:
        values["AI_CALL_RATIO"] = _pct(db["ai_call_ratio"])
    if res:
        values["CPU_MEAN"] = _num((res["system_cpu_percent"] or {}).get("mean"))
        values["RSS_MAX"] = _num((res["rss_mib"] or {}).get("max"))
        values["TEMP_MAX"] = _num((res["temperature_c"] or {}).get("max"))
    if health:
        values["FPS_MEAN"] = _num((health["fps"] or {}).get("mean"))
        values["PROC_MS_MEAN"] = _num((health["processing_ms"] or {}).get("mean"))
        if health.get("frames_processed") is not None:
            values["FRAMES_PROCESSED"] = f"{health['frames_processed']:,}"
    idle = summary.get("idle")
    if idle:
        values["IDLE_HOURS"] = _num(idle["hours"])
        values["IDLE_FP"] = str(idle["false_events"])
    lines += ["## 본문 자리표시자 값", ""]
    lines += [f"- `[[{key}]]` = {value}" for key, value in values.items()]
    lines += [
        "",
        "직접 채울 항목: `[[MAIN_ERROR]]`, `[[FAIL_CASES]]`, 장비·환경 항목"
        "(무인 감시 시각을 넣지 않았다면 `[[IDLE_HOURS]]`, `[[IDLE_FP]]`도).",
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re:Found 논문 결과표 생성")
    parser.add_argument("--trials", required=True, type=Path, help="실험 기록지 CSV")
    parser.add_argument("--db", type=Path, help="Pi에서 복사한 lost_items.db")
    parser.add_argument("--activities", type=Path, help="실험 진행 도우미가 저장한 activities.json(--db 대신)")
    parser.add_argument("--health", type=Path, help="poll_health.py 출력 CSV")
    parser.add_argument("--resources", type=Path, help="monitor_pi_resources.py 출력 CSV")
    parser.add_argument("--since", help="DB 집계 시작 시각(ISO, 선택)")
    parser.add_argument("--until", help="DB 집계 종료 시각(ISO, 선택)")
    parser.add_argument("--idle-start", help="무인 감시 시작 시각(예: 2026-10-20T14:30)")
    parser.add_argument("--idle-end", help="무인 감시 종료 시각")
    parser.add_argument("--output-dir", type=Path, default=Path("paper-results"))
    return parser


def build_summary(
    trials_path: Path, *, activities: list[dict[str, Any]] | None = None,
    health: Path | None = None, resources: Path | None = None,
    idle_start: datetime | None = None, idle_end: datetime | None = None,
) -> dict[str, Any]:
    """Library entry used by the live experiment session."""
    summary: dict[str, Any] = {"trials": summarize_trials(read_trials(trials_path))}
    if activities is not None:
        summary["database"] = summarize_activities(activities, until=idle_start)
        if idle_start and idle_end and idle_end > idle_start:
            summary["idle"] = {
                "hours": (idle_end - idle_start).total_seconds() / 3600,
                "false_events": summarize_activities(activities, since=idle_start, until=idle_end)["detected_events"],
            }
    if health is not None and Path(health).exists():
        summary["health"] = summarize_health(health)
    if resources is not None and Path(resources).exists():
        summary["resources"] = summarize_resources(resources)
    return summary


def write_outputs(summary: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "paper_tables.md"
    target.write_text(render_markdown(summary), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary: dict[str, Any] = {"trials": summarize_trials(read_trials(args.trials))}
    except TrialSheetError as exc:
        print(f"기록지 오류: {exc}", file=sys.stderr)
        return 2
    idle_start, idle_end = _parse_time(args.idle_start), _parse_time(args.idle_end)
    if (args.idle_start and idle_start is None) or (args.idle_end and idle_end is None):
        print("시각 형식 오류: 예) 2026-10-20T14:30", file=sys.stderr)
        return 2
    if args.db or args.activities:
        rows = load_activities(args.activities) if args.activities else None

        def summarize(since, until):
            if rows is not None:
                return summarize_activities(rows, since=since, until=until)
            return summarize_database(args.db, since=since, until=until)

        until = _parse_time(args.until) or idle_start
        summary["database"] = summarize(_parse_time(args.since), until)
        if idle_start and idle_end and idle_end > idle_start:
            summary["idle"] = {
                "hours": (idle_end - idle_start).total_seconds() / 3600,
                "false_events": summarize(idle_start, idle_end)["detected_events"],
            }
    if args.health:
        summary["health"] = summarize_health(args.health)
    if args.resources:
        summary["resources"] = summarize_resources(args.resources)
    target = write_outputs(summary, args.output_dir)
    print(f"결과표를 만들었습니다: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

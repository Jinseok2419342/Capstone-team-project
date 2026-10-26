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


def _optional_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    ordered = sorted(values)
    # Nearest-rank percentile: honest for the small samples of this study.
    p90 = ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]
    return {"n": len(ordered), "median": statistics.median(ordered), "p90": p90, "max": ordered[-1]}


def _sheet_rows(path: Path) -> list[dict[str, str]]:
    rows = []
    for raw in _read_csv(path):
        row = {(_COLUMN_ALIASES.get(_key(k)) or k): (v or "").strip() for k, v in raw.items() if k}
        row["action"] = _ACTION_ALIASES.get(_key(row.get("action", "")), "")
        row["result"] = _RESULT_ALIASES.get(_key(row.get("result", "")), "")
        if row["action"] or row["result"]:
            rows.append(row)
    return rows


def summarize_latency(trials_path: Path, activities: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Motion end → event record (live session column) and → AI result.

    ``감지지연_s`` is measured on the Pi's clock by the live session.  For
    correct registrations the AI time (provisional record → classification
    activity, also the Pi's clock) is added to get the time until the name and
    category appear on the administrator screen.
    """
    detected: dict[str, datetime] = {}
    classified: dict[str, datetime] = {}
    for a_type, item_id, meta, created in _activity_tuples(activities, None, None):
        key = str(item_id)
        if a_type == "item_detected" and meta.get("source") == "camera":
            detected.setdefault(key, created)
        elif a_type in _CLASSIFICATION_DONE and key in detected:
            classified.setdefault(key, created)
    by_kind: dict[str, list[float]] = {kind: [] for kind in EVENT_KINDS}
    until_ai: list[float] = []
    for row in _sheet_rows(trials_path):
        value = _optional_float(row.get("감지지연_s"))
        action = row["action"]
        if value is None or action not in EVENT_KINDS or row["result"] != action:
            continue
        by_kind[action].append(value)
        item = str(row.get("item_id", "")).strip()
        if action == "등록" and item in detected and item in classified:
            until_ai.append(value + (classified[item] - detected[item]).total_seconds())
    return {
        "by_kind": {kind: _distribution(values) for kind, values in by_kind.items()},
        "events": _distribution([v for values in by_kind.values() for v in values]),
        "motion_to_ai": _distribution(until_ai),
    }


def failed_trials(trials_path: Path) -> list[dict[str, str]]:
    failed = []
    for row in _sheet_rows(trials_path):
        expected = "반응 없음" if row["action"] == "무변화" else row["action"]
        if row["result"] != expected:
            failed.append({
                "no": row.get("no", ""), "condition": row.get("condition", ""), "action": row["action"],
                "item": row.get("물품", ""), "result": row["result"], "note": row.get("note", ""),
            })
    return failed


def ai_mistakes(trials_path: Path) -> list[dict[str, str]]:
    mistakes = []
    for row in _sheet_rows(trials_path):
        if row["action"] != "등록" or row["result"] != "등록":
            continue
        name, category = _key(row.get("ai_name", "")), _key(row.get("ai_category", ""))
        if name == "x" or category == "x":
            mistakes.append({
                "no": row.get("no", ""), "item": row.get("물품", ""), "ai": row.get("AI결과", ""),
                "name": "O" if name == "o" else "X", "category": "O" if category == "o" else "X",
            })
    return mistakes


def _pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}"


def _num(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


_PROVIDER_LABELS = {"openai": "OpenAI", "gemini": "Google Gemini", "offline": "외부 모델 없음(로컬 폴백)"}


def environment_values(env: dict[str, Any] | None) -> dict[str, str]:
    """Placeholders that the live session can fill from env.json."""
    if not env:
        return {}
    manual = env.get("manual") or {}
    start = env.get("start") or {}
    provider = start.get("provider") or {}
    started = str(env.get("experiment_started_local") or start.get("laptop_time_utc") or "")[:10]
    values: dict[str, str] = {}
    storage = str(manual.get("storage") or "").strip()
    if storage:
        values["EQUIP_STORAGE"] = storage if "sd" in storage.lower() else f"microSD {storage}"
    for key, placeholder in (
        ("cooling", "EQUIP_COOLING"), ("camera_geometry", "EQUIP_CAMERA_GEOMETRY"),
        ("network", "NETWORK_CONDITION"),
    ):
        if str(manual.get(key) or "").strip():
            values[placeholder] = str(manual[key]).strip()
    if provider.get("active"):
        label = _PROVIDER_LABELS.get(provider["active"], provider["active"])
        model = provider.get("model") if provider.get("active") != "offline" else ""
        values["VLM_MODEL_DATE"] = ", ".join(part for part in (f"{label} {model}".strip(), started) if part)
    if len(started) == 10:
        year, month, day = started.split("-")
        place = str(manual.get("place") or "").strip()
        values["EXPERIMENT_DATE_PLACE"] = f"{int(year)}년 {int(month)}월 {int(day)}일 {place}".strip()
    names = [str(item.get("name")) for item in env.get("items") or [] if item.get("name")]
    if names:
        values["OBJECT_LIST"] = ", ".join(names)
    return values


def render_markdown(summary: dict[str, Any]) -> str:
    trials = summary["trials"]
    lines = ["# Re:Found 논문 결과표 (자동 생성)", ""]
    lines += ["실험 도우미의 자동 집계다. 2026-10-26 원고는 10/25 손 기록 결과(`docs/paper/RESULTS_2026-10-25.md`)로 작성했으므로, 다시 실험한 경우 이 값을 원고의 표 형식(표 5–8)에 맞춰 옮긴다.", ""]

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
    env_values = environment_values(summary.get("environment"))
    values.update(env_values)
    lines += ["## 본문 자리표시자 값", ""]
    lines += [f"- `[[{key}]]` = {value}" for key, value in values.items()]
    manual_left = ["`[[MAIN_ERROR]]`", "`[[FAIL_CASES]]`"]
    manual_left += [
        f"`[[{key}]]`" for key in (
            "EQUIP_STORAGE", "EQUIP_COOLING", "EQUIP_CAMERA_GEOMETRY", "VLM_MODEL_DATE",
            "NETWORK_CONDITION", "EXPERIMENT_DATE_PLACE", "OBJECT_LIST",
        ) if key not in env_values
    ]
    lines += [
        "",
        "직접 채울 항목: " + ", ".join(manual_left)
        + "(무인 감시 시각을 넣지 않았다면 `[[IDLE_HOURS]]`, `[[IDLE_FP]]`도).",
        "",
    ]
    latency = summary.get("latency")
    if latency and latency["events"]["n"]:
        lines += ["## 본문 보강용 추가 값(선택 — 원고 6-3절의 대기 시간 설명에 쓸 수 있음)", ""]
        for kind in EVENT_KINDS:
            dist = latency["by_kind"][kind]
            if dist["n"]:
                lines.append(
                    f"- {kind}: 움직임 종료 → 사건 기록 중앙값 {_num(dist['median'])} s, "
                    f"최대 {_num(dist['max'])} s (n={dist['n']})"
                )
        ai = latency["motion_to_ai"]
        if ai["n"]:
            lines.append(
                f"- 등록: 움직임 종료 → AI 이름·분류 반영 중앙값 {_num(ai['median'])} s, "
                f"최대 {_num(ai['max'])} s (n={ai['n']})"
            )
        lines.append("")
    return "\n".join(lines)


def _goal(ok: bool | None) -> str:
    return "미측정" if ok is None else ("달성" if ok else "미달")


def render_final_report(summary: dict[str, Any]) -> str:
    """Numbers for the final presentation, the same ones the paper uses."""
    trials = summary["trials"]
    db = summary.get("database") or {}
    latency = summary.get("latency") or {}
    env = summary.get("environment") or {}
    res = summary.get("resources") or {}
    health = summary.get("health") or {}
    idle = summary.get("idle")
    env_values = environment_values(env)
    start = env.get("start") or {}
    provider = start.get("provider") or {}
    none = trials["none_false_events"]
    events = latency.get("events") or {"n": 0}
    to_ai = latency.get("motion_to_ai") or {"n": 0}

    def stat(group: dict[str, Any], key: str) -> dict[str, Any]:
        return group.get(key) or {}

    lines = ["# Re:Found 최종보고·논문 공통 수치 (자동 생성)", ""]
    lines += [
        f"> 실험: {env_values.get('EXPERIMENT_DATE_PLACE', '날짜 미기록')} · Raspberry Pi 4 2GB · "
        f"AI {env_values.get('VLM_MODEL_DATE', '미기록')} · 시도 {trials['trials']}회. "
        "같은 원시 기록에서 계산했으므로 발표와 논문에 같은 숫자를 씁니다.",
        "",
        "## 1. 발표에 쓸 핵심 숫자",
        "",
        "| 항목 | 값 | 표본 |",
        "|---|---|---|",
        f"| 사건 판정 정확도 | {_pct(trials['accuracy'])}% (95% 신뢰구간 {_pct(trials['accuracy_ci95'][0])}–"
        f"{_pct(trials['accuracy_ci95'][1])}%) | {trials['trials']}회 |",
        f"| 등록·이동·제거 평균 F1 | {_num(trials['macro']['f1'], 3)} | "
        f"{sum(trials['counts'][k] for k in EVENT_KINDS)}회 |",
        f"| 무변화 오탐 (손 / 조명 / 그림자) | {none['손']['false_events']}/{none['손']['trials']} · "
        f"{none['조명']['false_events']}/{none['조명']['trials']} · "
        f"{none['그림자']['false_events']}/{none['그림자']['trials']} | {trials['counts']['무변화']}회 |",
    ]
    if idle:
        lines.append(f"| 무인 감시 중 잘못된 사건 | {idle['false_events']}건 | {_num(idle['hours'])}시간 |")
    lines.append(
        f"| AI 이름 / 분류 정확도 | {_pct(trials['ai_name_accuracy'])}% / {_pct(trials['ai_category_accuracy'])}% | "
        f"n={trials['ai_name_judged']}/{trials['ai_category_judged']} |"
    )
    if db:
        lines.append(
            f"| AI 호출 비율 | {_pct(db['ai_call_ratio'])}% (등록 {db['added']} + 제거 검증 {db['verify_calls']}"
            f" / 감지 사건 {db['detected_events']}) | 실험 중 전체 |"
        )
        lines.append(
            f"| AI 처리 시간 (임시 기록 → 이름·분류) | 중앙값 {_num(db['classification_median_s'])}초 · "
            f"최대 {_num(db['classification_max_s'])}초 | n={len(db['classification_seconds'])} |"
        )
    if events.get("n"):
        lines.append(
            f"| 움직임 종료 → 사건 기록 | 중앙값 {_num(events['median'])}초 · 최대 {_num(events['max'])}초 | "
            f"n={events['n']} |"
        )
    if to_ai.get("n"):
        lines.append(
            f"| 움직임 종료 → 화면에 AI 이름·분류 | 중앙값 {_num(to_ai['median'])}초 · 최대 {_num(to_ai['max'])}초 | "
            f"n={to_ai['n']} |"
        )
    if res:
        lines.append(
            f"| Pi 평균 CPU / 최고 온도 | {_num(stat(res, 'system_cpu_percent').get('mean'))}% / "
            f"{_num(stat(res, 'temperature_c').get('max'))}°C | 1초 간격 {stat(res, 'temperature_c').get('n', 0)}회 |"
        )
        lines.append(f"| 서비스 최대 메모리 | {_num(stat(res, 'rss_mib').get('max'))} MiB | |")
    if health:
        lines.append(
            f"| 분석 프레임률 / 프레임 처리 시간 | {_num(stat(health, 'fps').get('mean'))} fps / "
            f"{_num(stat(health, 'processing_ms').get('mean'))} ms | 분석 {health.get('frames_processed') or '—'}프레임 |"
        )
    lines.append("")

    category = trials["ai_category_accuracy"]
    ratio = db.get("ai_call_ratio") if db else None
    median_record = events.get("median") if events.get("n") else None
    median_ai = to_ai.get("median") if to_ai.get("n") else None
    lines += [
        "## 2. 1학기 기획 목표 대비 (팀 프로젝트기획서 2026-05-12의 정량 목표)",
        "",
        "| 1학기 목표 | 이번 측정 | 판정 기준 | 판정 |",
        "|---|---|---|---|",
        f"| 물체 감지~DB 저장 10초 이내 | 움직임 종료→사건 기록 중앙값 {_num(median_record)}초, "
        f"→AI 이름·분류 반영 중앙값 {_num(median_ai)}초 | AI 반영까지 중앙값 ≤ 10초 | "
        f"{_goal(None if median_ai is None else median_ai <= 10)} |",
        f"| 분류 정확도 85% 이상 | 3분류(귀중품·일반·음식) {_pct(category)}% (n={trials['ai_category_judged']}) | ≥ 85% | "
        f"{_goal(None if category is None else category >= 0.85)} |",
        f"| 멀티모달 API 호출 30% 이상 절감 | 감지 사건 대비 호출 {_pct(ratio)}% → 사건마다 호출하는 방식 대비 "
        f"{_pct(None if ratio is None else 1 - ratio)}% 절감 | 절감 ≥ 30% | "
        f"{_goal(None if ratio is None else 1 - ratio >= 0.30)} |",
        "",
        "1학기 계획의 수단(YOLOv8 탐지, 로컬 LLM, 임베딩 캐시)은 바뀌었으므로, 같은 목표를 현재 구현"
        "(안정 장면 사건 감지 + 사건별 선택 호출)으로 측정한 결과라고 설명한다.",
        "",
    ]

    checks = summary.get("function_checks") or {}
    rows = checks.get("results") or []
    if rows:
        counted = [r for r in rows if r["결과"] != "해당 없음" and r["점검"] != "점검 대상 물품"]
        passed = sum(r["결과"] == "통과" for r in counted)
        lines += ["## 3. 실제 Pi 관리 기능 점검 (자동)", "", "| 점검 | 결과 | 내용 |", "|---|---|---|"]
        lines += [f"| {r['점검']} | {r['결과']} | {r['내용']} |" for r in rows]
        lines += ["", f"통과 {passed} / {len(counted)}항목"
                  + (f", 메일 수신(사용자 확인): {checks['mail_received']}" if checks.get("mail_received") else ""), ""]
    elif checks.get("skipped"):
        lines += ["## 3. 실제 Pi 관리 기능 점검", "", "이번 실행에서는 건너뜀.", ""]

    rehearsal = summary.get("rehearsal") or {}
    if rehearsal.get("steps"):
        lines += [
            "## 4. 시연 리허설 (같은 물품의 등록 → 이동 → 회수)", "",
            "| 단계 | 시스템 결과 | 물품 ID | 움직임 종료→기록 |", "|---|---|---|---|",
        ]
        for step in rehearsal["steps"]:
            seconds = step.get("latency_s")
            lines.append(
                f"| {step['action']} | {step['result']} | {step.get('item_id') or '—'} | "
                f"{'—' if seconds is None else f'{seconds:.1f}초'} |"
            )
        ai = rehearsal.get("ai") or {}
        lines.append("")
        if ai.get("name"):
            lines.append(f"AI 결과: '{ai['name']}' ({ai.get('category', '')}), 기록 후 {_num(ai.get('classification_s'))}초.")
        lines.append(
            "같은 물품 ID로 세 단계가 이어짐: " + ("예" if rehearsal.get("same_item_id") else "아니요")
            + ". 장면 사진은 `scenes/rehearsal_*_after.jpg`(최종보고의 등록·이동·회수 화면)."
        )
        lines.append("")

    failures = summary.get("failed_trials") or []
    mistakes = summary.get("ai_mistakes") or []
    lines += ["## 5. 오류 사례 후보 (발표 '오류가 난 사례'·논문 `[[FAIL_CASES]]`)", ""]
    if failures:
        lines += ["| 번호 | 조건 | 정답 | 시스템 결과 | 메모 | 장면 사진 |", "|---|---|---|---|---|---|"]
        for row in failures:
            number = int(row["no"]) if str(row["no"]).isdigit() else row["no"]
            scene = f"scenes/trial{number:03d}_after.jpg" if isinstance(number, int) else ""
            lines.append(
                f"| {row['no']} | {row['condition']} | {row['action']} {row['item']} | {row['result']} | "
                f"{row['note']} | {scene} |"
            )
    else:
        lines.append("사건 판정이 틀린 시도 없음.")
    if mistakes:
        lines += ["", "| 번호 | 실제 물품 | AI 결과 | 이름 | 분류 |", "|---|---|---|---|---|"]
        lines += [f"| {m['no']} | {m['item']} | {m['ai']} | {m['name']} | {m['category']} |" for m in mistakes]
    lines.append("")

    manual = env.get("manual") or {}
    settings = start.get("settings") or {}
    lines += ["## 6. 실험 환경 (논문 표 4·발표 시연 환경)", ""]
    if provider:
        lines.append(f"- AI: {_PROVIDER_LABELS.get(provider.get('active'), provider.get('active'))} "
                     f"{provider.get('model') or ''} (설정 {provider.get('requested')})")
    if settings:
        lines.append(
            f"- 영상: {settings.get('camera_width')}×{settings.get('camera_height')}, 입력 {settings.get('camera_fps')} fps, "
            f"분석 최대 {settings.get('monitor_fps')} fps, 대기·안정 {settings.get('settle_seconds')}/"
            f"{settings.get('stable_seconds')} s, 정합 폭 {settings.get('stabilization_analysis_width')} px"
        )
    for key, label in (("storage", "저장장치"), ("cooling", "냉각"), ("camera_geometry", "카메라 설치"),
                       ("network", "네트워크"), ("place", "장소")):
        if manual.get(key):
            lines.append(f"- {label}: {manual[key]}")
    cold = str(manual.get("cold_boot") or "").strip().lower()
    if cold in ("y", "n"):
        lines.append(
            "- 전원을 새로 켠 뒤 랜선 없이 무선 자동 접속·서비스 자동 시작: "
            + ("확인(사용자 응답 y" if cold == "y" else "아님(사용자 응답 n")
            + (f", 서비스 시작 기록 {env.get('service_started_at')})" if env.get("service_started_at") else ")")
        )
    lines.append("")
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
    env: dict[str, Any] | None = None, rehearsal: dict[str, Any] | None = None,
    function_checks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Library entry used by the live experiment session."""
    summary: dict[str, Any] = {"trials": summarize_trials(read_trials(trials_path))}
    summary["failed_trials"] = failed_trials(trials_path)
    summary["ai_mistakes"] = ai_mistakes(trials_path)
    if activities is not None:
        summary["database"] = summarize_activities(activities, until=idle_start)
        summary["latency"] = summarize_latency(trials_path, activities)
        if idle_start and idle_end and idle_end > idle_start:
            summary["idle"] = {
                "hours": (idle_end - idle_start).total_seconds() / 3600,
                "false_events": summarize_activities(activities, since=idle_start, until=idle_end)["detected_events"],
            }
    if health is not None and Path(health).exists():
        summary["health"] = summarize_health(health)
    if resources is not None and Path(resources).exists():
        summary["resources"] = summarize_resources(resources)
    if env:
        summary["environment"] = env
    if rehearsal:
        summary["rehearsal"] = rehearsal
    if function_checks:
        summary["function_checks"] = function_checks
    return summary


def write_outputs(summary: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "paper_tables.md"
    target.write_text(render_markdown(summary), encoding="utf-8")
    (output_dir / "final_report_values.md").write_text(render_final_report(summary), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary: dict[str, Any] = {"trials": summarize_trials(read_trials(args.trials))}
        summary["failed_trials"] = failed_trials(args.trials)
        summary["ai_mistakes"] = ai_mistakes(args.trials)
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

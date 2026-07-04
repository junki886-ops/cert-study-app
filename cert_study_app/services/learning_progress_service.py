from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Optional

from cert_study_app.config import DATA_DIR


PROGRESS_PATH = DATA_DIR / "learning_progress.json"
STUDY_UNIT_POINTS = 3.0
ACTIVITY_POINTS = {
    "lesson": 1.0,
    "quiz": 0.35,
    "review": 1.0,
    "practice": 2.0,
    "cert_question": 0.5,
    "docs": 1.0,
}
STEP_ACTIVITY_DEFAULTS = {
    "lesson": ("lesson", 1),
    "quiz": ("quiz", 3),
    "apply": ("practice", 1),
    "review": ("review", 1),
}
DEFAULT_TRACK_ID = "linux"

# 간격 반복 복습: 틀린 후 1→3→7→14→30일 간격으로 재출제
_SPACED_INTERVALS = [1, 3, 7, 14, 30]


def load_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {"activity": {}}
    try:
        payload = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"activity": {}}
    if not isinstance(payload, dict):
        return {"activity": {}}
    return _normalize_progress(payload)


def _normalize_progress(progress: dict[str, Any]) -> dict[str, Any]:
    """Keep old progress files readable while storing ongoing study as activity."""
    activity = progress.get("activity")
    legacy_daily = progress.get("daily")
    if not isinstance(activity, dict):
        activity = legacy_daily if isinstance(legacy_daily, dict) else {}
        progress["activity"] = activity
    return progress


def _activity_days(progress: dict[str, Any]) -> dict[str, Any]:
    activity = progress.setdefault("activity", {})
    if isinstance(activity, dict):
        return activity
    progress["activity"] = {}
    return progress["activity"]


def save_progress(payload: dict[str, Any]) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def preferred_track() -> str:
    progress = load_progress()
    preferences = progress.get("preferences", {})
    track_id = preferences.get("preferred_track") if isinstance(preferences, dict) else None
    return str(track_id or DEFAULT_TRACK_ID)


def save_preferred_track(track_id: str) -> str:
    normalized = str(track_id or DEFAULT_TRACK_ID)
    progress = load_progress()
    preferences = progress.setdefault("preferences", {})
    preferences["preferred_track"] = normalized
    save_progress(progress)
    return normalized


def completed_steps(track_id: str, target_date: Optional[date] = None) -> set[str]:
    target = (target_date or date.today()).isoformat()
    progress = load_progress()
    steps = (
        _activity_days(progress)
        .get(target, {})
        .get("tracks", {})
        .get(track_id, {})
        .get("steps", [])
    )
    return set(steps if isinstance(steps, list) else [])


def mark_learning_step(track_id: str, step_id: str, target_date: Optional[date] = None) -> set[str]:
    target = (target_date or date.today()).isoformat()
    progress = load_progress()
    activity_days = _activity_days(progress)
    day_record = activity_days.setdefault(target, {"tracks": {}})
    tracks = day_record.setdefault("tracks", {})
    track_record = tracks.setdefault(track_id, {"steps": []})
    steps = set(track_record.get("steps") or [])
    steps.add(step_id)
    track_record["steps"] = sorted(steps)
    track_record["updated_at"] = date.today().isoformat()
    save_progress(progress)
    if step_id in STEP_ACTIVITY_DEFAULTS:
        activity, amount = STEP_ACTIVITY_DEFAULTS[step_id]
        record_activity(track_id, activity, amount, target_date=target_date)
    return steps


def record_activity(track_id: str, activity: str, amount: int = 1, target_date: Optional[date] = None) -> dict[str, Any]:
    target = (target_date or date.today()).isoformat()
    progress = load_progress()
    activity_days = _activity_days(progress)
    day_record = activity_days.setdefault(target, {"tracks": {}})
    tracks = day_record.setdefault("tracks", {})
    track_record = tracks.setdefault(track_id, {"steps": [], "counts": {}})
    counts = track_record.setdefault("counts", {})
    counts[activity] = int(counts.get(activity, 0)) + int(amount)
    track_record["updated_at"] = date.today().isoformat()
    save_progress(progress)
    return track_record


def track_counts_points(track: dict[str, Any]) -> float:
    counts = track.get("counts", {}) if isinstance(track, dict) else {}
    points = 0.0
    for activity, count in counts.items():
        points += ACTIVITY_POINTS.get(activity, 0.0) * int(count or 0)
    return points


def tracks_points(tracks: dict[str, Any]) -> float:
    return sum(track_counts_points(track) for track in tracks.values())


def tracks_step_count(tracks: dict[str, Any]) -> int:
    return sum(len(track.get("steps") or []) for track in tracks.values() if isinstance(track, dict))


def study_points(track_id: Optional[str] = None, target_date: Optional[date] = None) -> float:
    target = (target_date or date.today()).isoformat()
    progress = load_progress()
    tracks = _activity_days(progress).get(target, {}).get("tracks", {})
    selected_tracks = {track_id: tracks.get(track_id, {})} if track_id else tracks
    return round(tracks_points(selected_tracks), 2)


def study_units(track_id: Optional[str] = None, target_date: Optional[date] = None) -> float:
    return round(study_points(track_id, target_date) / STUDY_UNIT_POINTS, 1)


def weekly_summary(days: int = 7) -> dict[str, Any]:
    progress = load_progress()
    activity_days = _activity_days(progress)
    today = date.today()
    active_days = 0
    completed_steps_count = 0
    points = 0.0
    for offset in range(days):
        key = (today - timedelta(days=offset)).isoformat()
        tracks = activity_days.get(key, {}).get("tracks", {})
        day_steps = tracks_step_count(tracks)
        day_points = tracks_points(tracks)
        if day_steps or day_points:
            active_days += 1
            completed_steps_count += day_steps
        points += day_points
    return {
        "active_days": active_days,
        "completed_steps": completed_steps_count,
        "study_units": round(points / STUDY_UNIT_POINTS, 1),
        "activity_units": round(points / STUDY_UNIT_POINTS, 1),
        "daily_units": round(points / STUDY_UNIT_POINTS, 1),
    }


def streak_days() -> int:
    progress = load_progress()
    activity_days = _activity_days(progress)
    today = date.today()
    streak = 0
    for offset in range(365):
        key = (today - timedelta(days=offset)).isoformat()
        tracks = activity_days.get(key, {}).get("tracks", {})
        day_steps = tracks_step_count(tracks)
        day_points = tracks_points(tracks)
        if not day_steps and not day_points:
            break
        streak += 1
    return streak


def next_day_recommendation(track_id: str) -> str:
    steps = completed_steps(track_id)
    if "lesson" not in steps:
        return "이론 카드 1개부터 시작하면 부담이 가장 적습니다."
    if "quiz" not in steps:
        return "오늘 본 이론을 확인 퀴즈로 바로 점검해 보세요."
    if "apply" not in steps:
        return "개념을 봤다면 실습이나 문제풀이로 한 번 적용해 보세요."
    if "review" not in steps:
        return "오답 1개를 복습한 뒤 계속 이어서 풀면 학습량이 누적됩니다."
    units = study_units(track_id)
    if units >= 1:
        return f"Focus 진도 흐름을 지나왔습니다. 지금까지 {units}단위만큼 공부했고, 계속 이어갈 수 있습니다."
    return "Focus 진도 흐름을 거의 지나왔습니다. 부담 없이 한 단계 더 이어가면 됩니다."


def daily_points(track_id: Optional[str] = None, target_date: Optional[date] = None) -> float:
    return study_points(track_id, target_date)


def daily_units(track_id: Optional[str] = None, target_date: Optional[date] = None) -> float:
    return study_units(track_id, target_date)


# ── Lab 완료 항목 영속 ────────────────────────────────────────────────────────

def save_completed_items(
    lessons: set[str],
    quizzes: set[str],
    practices: set[str],
) -> None:
    progress = load_progress()
    progress["completed"] = {
        "lessons": sorted(lessons),
        "quizzes": sorted(quizzes),
        "practices": sorted(practices),
    }
    save_progress(progress)


def load_completed_items() -> tuple[set[str], set[str], set[str]]:
    progress = load_progress()
    completed = progress.get("completed", {})
    return (
        set(completed.get("lessons", [])),
        set(completed.get("quizzes", [])),
        set(completed.get("practices", [])),
    )


def save_wrong_notes(notes: list[dict]) -> None:
    progress = load_progress()
    progress["wrong_notes"] = notes
    save_progress(progress)


def load_wrong_notes() -> list[dict]:
    progress = load_progress()
    return progress.get("wrong_notes", [])


# ── 개념 퀴즈 간격 반복 (string ID 기반) ─────────────────────────────────────

def update_lab_spaced_review(quiz_id: str, correct: bool) -> None:
    """개념/command 퀴즈 오답은 1→3→7→14→30일 간격으로 재출제 스케줄에 등록."""
    progress = load_progress()
    spaced: dict = progress.setdefault("lab_spaced_review", {})
    key = str(quiz_id)
    today = date.today()

    if not correct:
        spaced[key] = {
            "interval": 1,
            "next_review": (today + timedelta(days=1)).isoformat(),
            "correct_streak": 0,
        }
    elif key in spaced:
        record = spaced[key]
        streak = int(record.get("correct_streak", 0)) + 1
        if streak >= 3:
            del spaced[key]
        else:
            cur_interval = int(record.get("interval", 1))
            cur_idx = _SPACED_INTERVALS.index(cur_interval) if cur_interval in _SPACED_INTERVALS else 0
            next_interval = _SPACED_INTERVALS[min(cur_idx + 1, len(_SPACED_INTERVALS) - 1)]
            spaced[key] = {
                "interval": next_interval,
                "next_review": (today + timedelta(days=next_interval)).isoformat(),
                "correct_streak": streak,
            }

    save_progress(progress)


def lab_spaced_review_due_today(limit: int = 30) -> list[str]:
    """오늘 복습 기한이 된 개념 퀴즈 ID 목록."""
    progress = load_progress()
    spaced: dict = progress.get("lab_spaced_review", {})
    today = date.today().isoformat()
    due: list[str] = []
    for qid, record in spaced.items():
        if isinstance(record, dict) and record.get("next_review", "") <= today:
            due.append(qid)
    return due[:limit]


def lab_spaced_review_count() -> int:
    return len(lab_spaced_review_due_today(limit=200))


# ── 간격 반복 복습 (Spaced Repetition) ──────────────────────────────────────

def update_spaced_review(question_id: int, correct: bool) -> None:
    """틀린 문제는 1→3→7→14→30일 간격으로 재출제 스케줄에 등록한다.
    3연속 정답이면 스케줄에서 제거한다."""
    progress = load_progress()
    spaced: dict = progress.setdefault("spaced_review", {})
    key = str(question_id)
    today = date.today()

    if not correct:
        spaced[key] = {
            "interval": 1,
            "next_review": (today + timedelta(days=1)).isoformat(),
            "correct_streak": 0,
        }
    elif key in spaced:
        record = spaced[key]
        streak = int(record.get("correct_streak", 0)) + 1
        if streak >= 3:
            del spaced[key]
        else:
            cur_interval = int(record.get("interval", 1))
            cur_idx = _SPACED_INTERVALS.index(cur_interval) if cur_interval in _SPACED_INTERVALS else 0
            next_interval = _SPACED_INTERVALS[min(cur_idx + 1, len(_SPACED_INTERVALS) - 1)]
            spaced[key] = {
                "interval": next_interval,
                "next_review": (today + timedelta(days=next_interval)).isoformat(),
                "correct_streak": streak,
            }

    save_progress(progress)


def spaced_review_due_today(limit: int = 10) -> list[int]:
    """오늘 복습 기한이 된 question_id 목록을 반환한다."""
    progress = load_progress()
    spaced: dict = progress.get("spaced_review", {})
    today = date.today().isoformat()
    due: list[int] = []
    for qid_str, record in spaced.items():
        if isinstance(record, dict) and record.get("next_review", "") <= today:
            try:
                due.append(int(qid_str))
            except ValueError:
                pass
    return due[:limit]


def spaced_review_count() -> int:
    """오늘 복습 기한이 된 문제 수."""
    return len(spaced_review_due_today(limit=200))

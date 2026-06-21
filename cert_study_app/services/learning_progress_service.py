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
    "review": ("review", 1),
}
DEFAULT_TRACK_ID = "linux"


def load_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {"daily": {}}
    try:
        payload = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"daily": {}}
    return payload if isinstance(payload, dict) else {"daily": {}}


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
        progress.get("daily", {})
        .get(target, {})
        .get("tracks", {})
        .get(track_id, {})
        .get("steps", [])
    )
    return set(steps if isinstance(steps, list) else [])


def mark_learning_step(track_id: str, step_id: str, target_date: Optional[date] = None) -> set[str]:
    target = (target_date or date.today()).isoformat()
    progress = load_progress()
    daily = progress.setdefault("daily", {})
    day_record = daily.setdefault(target, {"tracks": {}})
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
    daily = progress.setdefault("daily", {})
    day_record = daily.setdefault(target, {"tracks": {}})
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
    tracks = progress.get("daily", {}).get(target, {}).get("tracks", {})
    selected_tracks = {track_id: tracks.get(track_id, {})} if track_id else tracks
    return round(tracks_points(selected_tracks), 2)


def study_units(track_id: Optional[str] = None, target_date: Optional[date] = None) -> float:
    return round(study_points(track_id, target_date) / STUDY_UNIT_POINTS, 1)


def weekly_summary(days: int = 7) -> dict[str, Any]:
    progress = load_progress()
    daily = progress.get("daily", {})
    today = date.today()
    active_days = 0
    completed_steps_count = 0
    points = 0.0
    for offset in range(days):
        key = (today - timedelta(days=offset)).isoformat()
        tracks = daily.get(key, {}).get("tracks", {})
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
        "daily_units": round(points / STUDY_UNIT_POINTS, 1),
    }


def streak_days() -> int:
    progress = load_progress()
    daily = progress.get("daily", {})
    today = date.today()
    streak = 0
    for offset in range(365):
        key = (today - timedelta(days=offset)).isoformat()
        tracks = daily.get(key, {}).get("tracks", {})
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
    if "review" not in steps:
        return "오답 1개를 복습한 뒤 계속 이어서 풀면 학습량이 누적됩니다."
    units = study_units(track_id)
    if units >= 1:
        return f"기본 흐름을 지나왔습니다. 지금까지 {units}단위만큼 공부했고, 계속 이어갈 수 있습니다."
    return "기본 흐름을 거의 지나왔습니다. 부담 없이 한 단계 더 이어가면 됩니다."


def daily_points(track_id: Optional[str] = None, target_date: Optional[date] = None) -> float:
    return study_points(track_id, target_date)


def daily_units(track_id: Optional[str] = None, target_date: Optional[date] = None) -> float:
    return study_units(track_id, target_date)

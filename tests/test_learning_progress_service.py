from datetime import date

from cert_study_app.services import learning_progress_service as progress_service


def test_learning_progress_migrates_legacy_daily_key(tmp_path, monkeypatch):
    progress_path = tmp_path / "learning_progress.json"
    progress_path.write_text(
        '{"daily": {"2026-06-21": {"tracks": {"linux": {"steps": ["lesson"], "counts": {"lesson": 1}}}}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(progress_service, "PROGRESS_PATH", progress_path)

    assert progress_service.completed_steps("linux", date(2026, 6, 21)) == {"lesson"}
    assert progress_service.study_units("linux", date(2026, 6, 21)) == 0.3


def test_learning_progress_writes_activity_key(tmp_path, monkeypatch):
    progress_path = tmp_path / "learning_progress.json"
    monkeypatch.setattr(progress_service, "PROGRESS_PATH", progress_path)

    progress_service.record_activity("linux", "practice", amount=1, target_date=date(2026, 6, 21))
    payload = progress_path.read_text(encoding="utf-8")

    assert '"activity"' in payload
    assert '"daily"' not in payload

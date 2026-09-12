from datetime import datetime, timedelta, timezone

from peptron_watch.heartbeat import is_fresh

KST = timezone(timedelta(hours=9))


def test_none_heartbeat_is_not_fresh():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=KST)
    assert is_fresh(None, now, threshold_minutes=10) is False


def test_heartbeat_missing_last_run_is_not_fresh():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=KST)
    assert is_fresh({}, now, threshold_minutes=10) is False


def test_recent_heartbeat_is_fresh():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=KST)
    last_run = now - timedelta(minutes=3)
    heartbeat = {"last_run": last_run.isoformat()}
    assert is_fresh(heartbeat, now, threshold_minutes=10) is True


def test_heartbeat_exactly_at_threshold_is_fresh():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=KST)
    last_run = now - timedelta(minutes=10)
    heartbeat = {"last_run": last_run.isoformat()}
    assert is_fresh(heartbeat, now, threshold_minutes=10) is True


def test_stale_heartbeat_is_not_fresh():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=KST)
    last_run = now - timedelta(minutes=11)
    heartbeat = {"last_run": last_run.isoformat()}
    assert is_fresh(heartbeat, now, threshold_minutes=10) is False

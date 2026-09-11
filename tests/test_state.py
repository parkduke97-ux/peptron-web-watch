from peptron_watch.state import (load_snapshot, save_snapshot,
                                  load_health, save_health)


def test_missing_snapshot_returns_none(tmp_path):
    assert load_snapshot(str(tmp_path), "ir_faq") is None


def test_save_then_load_roundtrip(tmp_path):
    items = [{"key": "a", "title": "t", "date": "", "text": "x",
              "url": "u", "extra": {}}]
    save_snapshot(str(tmp_path), "ir_faq", items)
    assert load_snapshot(str(tmp_path), "ir_faq") == items


def test_health_defaults_and_roundtrip(tmp_path):
    assert load_health(str(tmp_path)) == {"consecutive_failures": 0, "alerted": False}
    save_health(str(tmp_path), {"consecutive_failures": 3, "alerted": True})
    assert load_health(str(tmp_path))["consecutive_failures"] == 3

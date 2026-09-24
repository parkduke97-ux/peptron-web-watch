from datetime import date, datetime, timedelta, timezone

from peptron_watch.hours import is_watch_time

KST = timezone(timedelta(hours=9))
HOURS = {"start": "07:50", "end": "19:00"}


def _at(h, m, s=0, day=(2026, 9, 30)):  # 2026-09-30 = 평범한 수요일
    return datetime(*day, h, m, s, tzinfo=KST)


def test_weekday_inside_window():
    assert is_watch_time(_at(12, 0), HOURS) is True


def test_start_is_inclusive_end_is_exclusive():
    assert is_watch_time(_at(7, 49, 59), HOURS) is False
    assert is_watch_time(_at(7, 50), HOURS) is True
    assert is_watch_time(_at(18, 59, 59), HOURS) is True
    assert is_watch_time(_at(19, 0), HOURS) is False


def test_night_is_outside():
    assert is_watch_time(_at(2, 0), HOURS) is False


def test_weekend_is_outside():
    assert is_watch_time(_at(12, 0, day=(2026, 10, 10)), HOURS) is False  # 토요일


def test_public_and_substitute_holidays_are_outside():
    assert is_watch_time(_at(12, 0, day=(2026, 9, 25)), HOURS) is False  # 추석
    assert is_watch_time(_at(12, 0, day=(2026, 10, 5)), HOURS) is False  # 개천절 대체휴일


def test_extra_holidays_accept_string_or_yaml_date():
    assert is_watch_time(_at(12, 0), {**HOURS, "extra_holidays": ["2026-09-30"]}) is False
    assert is_watch_time(_at(12, 0), {**HOURS, "extra_holidays": [date(2026, 9, 30)]}) is False


def test_no_setting_means_always():
    assert is_watch_time(_at(2, 0, day=(2026, 10, 10)), None) is True

from datetime import time

import holidays

_KR_HOLIDAYS = holidays.country_holidays("KR")


def is_watch_time(now, hours):
    """평일(주말·공휴일 제외)의 감시 시간(start 포함, end 미포함)인지. hours 설정이 없으면 항상 감시한다."""
    if not hours:
        return True
    today = now.date()
    if today.weekday() >= 5 or today in _KR_HOLIDAYS:
        return False
    # YAML은 따옴표 없는 날짜를 date로 읽으므로 문자열로 맞춰 비교한다
    if today.isoformat() in {str(d) for d in hours.get("extra_holidays") or []}:
        return False
    return time.fromisoformat(hours["start"]) <= now.time() < time.fromisoformat(hours["end"])

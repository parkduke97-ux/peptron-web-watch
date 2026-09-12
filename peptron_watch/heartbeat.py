from datetime import datetime, timedelta


def is_fresh(heartbeat, now, threshold_minutes):
    """PC의 로컬 감시가 최근에 살아있었는지 판단한다.

    heartbeat: state.load_heartbeat()의 반환값 (None 또는 {"last_run": iso문자열})
    now: timezone-aware datetime (heartbeat 기록 시각과 같은 tz 기준이어야 함)
    """
    if not heartbeat or not heartbeat.get("last_run"):
        return False
    last_run = datetime.fromisoformat(heartbeat["last_run"])
    return (now - last_run) <= timedelta(minutes=threshold_minutes)

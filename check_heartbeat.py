import os
from datetime import datetime, timedelta, timezone

from peptron_watch import state
from peptron_watch.heartbeat import is_fresh

KST = timezone(timedelta(hours=9))
HEARTBEAT_FRESH_MINUTES = 10


def main():
    state_dir = os.path.join(os.path.dirname(__file__), "state")
    heartbeat = state.load_heartbeat(state_dir)
    now = datetime.now(KST)
    alive = is_fresh(heartbeat, now, HEARTBEAT_FRESH_MINUTES)

    if heartbeat and heartbeat.get("last_run"):
        print(f"마지막 PC 하트비트: {heartbeat['last_run']} (신선함: {alive})")
    else:
        print("하트비트 기록 없음 (PC 감시가 아직 한 번도 실행되지 않음)")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"pc_alive={'true' if alive else 'false'}\n")


if __name__ == "__main__":
    main()

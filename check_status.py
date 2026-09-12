import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from peptron_watch import state
from peptron_watch.heartbeat import is_fresh

KST = timezone(timedelta(hours=9))
HEARTBEAT_FRESH_MINUTES = 10
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

_PS_FIND_PROCESS = (
    "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
    "| Where-Object { $_.CommandLine -like '*local_loop.py*' } "
    "| Select-Object -First 1; "
    "if ($p) { Write-Output ('RUNNING:' + $p.ProcessId) } else { Write-Output 'NOT_RUNNING' }"
)


def check_process():
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PS_FIND_PROCESS],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[프로세스] 확인 실패 (PowerShell 실행 불가: {e})")
        return
    output = result.stdout.strip()
    if output.startswith("RUNNING:"):
        pid = output.split(":", 1)[1]
        print(f"[프로세스] local_loop.py 실행 중 (PID {pid})")
    else:
        print("[프로세스] local_loop.py 실행 중이 아님 - 이 PC에서 감시가 꺼져 있습니다")


def check_heartbeat_status():
    state_dir = os.path.join(REPO_DIR, "state")
    heartbeat = state.load_heartbeat(state_dir)
    now = datetime.now(KST)
    alive = is_fresh(heartbeat, now, HEARTBEAT_FRESH_MINUTES)
    if heartbeat and heartbeat.get("last_run"):
        freshness = "예" if alive else "아니오 (오래됨)"
        print(f"[하트비트] 마지막 기록: {heartbeat['last_run']} (신선함: {freshness})")
    else:
        print("[하트비트] 기록 없음 (아직 한 번도 실행되지 않음)")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    print("=== peptron-ir-watch 상태 확인 ===")
    check_process()
    check_heartbeat_status()


if __name__ == "__main__":
    main()

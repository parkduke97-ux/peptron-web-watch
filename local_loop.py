import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from main import load_config, run
from peptron_watch import fetch, notify, state

KST = timezone(timedelta(hours=9))
LOOP_INTERVAL_SECONDS = 180  # 3분마다 감시 (GitHub의 하트비트 판단 기준 10분보다 훨씬 촘촘함)
REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """.env 파일이 있으면 아직 설정 안 된 환경변수만 채워넣는다 (외부 패키지 불필요)."""
    env_path = os.path.join(REPO_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=REPO_DIR, capture_output=True, text=True, encoding="utf-8"
    )


def sync_before_run():
    result = _git("pull", "--rebase", "origin", "HEAD")
    if result.returncode != 0:
        print(f"[동기화] pull --rebase 실패, 이번 주기는 건너뜀: {result.stderr.strip()}",
              file=sys.stderr)
        return False
    return True


def push_state_changes(now_str):
    _git("add", "state/")
    diff = _git("diff", "--cached", "--quiet")
    if diff.returncode == 0:
        return  # 변경 없음
    commit = _git("commit", "-m", f"state: 로컬 감시 스냅샷 갱신 ({now_str}) [skip ci]")
    if commit.returncode != 0:
        print(f"[동기화] commit 실패: {commit.stderr.strip()}", file=sys.stderr)
        return
    push = _git("push")
    if push.returncode != 0:
        print(f"[동기화] push 실패 (다음 주기에 재시도됨): {push.stderr.strip()}", file=sys.stderr)


def _cli():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    _load_dotenv()

    config = load_config(os.path.join(REPO_DIR, "watch_config.yaml"))
    state_dir = os.path.join(REPO_DIR, "state")
    token = os.environ[config["telegram"]["token_env"]]
    chat_id = os.environ[config["telegram"]["chat_id_env"]]

    def sender(text):
        return notify.send_message(token, chat_id, text)

    print(f"로컬 24시간 감시 시작 (주기: {LOOP_INTERVAL_SECONDS}초). 종료하려면 Ctrl+C.")
    while True:
        if sync_before_run():
            now = datetime.now(KST)
            try:
                run(config, state_dir, fetch.fetch_text, sender, now=now)
            except Exception as e:
                print(f"[루프] 실행 중 오류: {e}", file=sys.stderr)
            state.save_heartbeat(state_dir, now.isoformat())
            push_state_changes(now.strftime("%Y-%m-%d %H:%M KST"))
        time.sleep(LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    _cli()

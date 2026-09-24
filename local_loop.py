import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from main import load_config, run
from peptron_watch import fetch, notify, state
from peptron_watch.hours import is_watch_time

KST = timezone(timedelta(hours=9))
LOOP_INTERVAL_SECONDS = 30
# GitHub의 하트비트 판단 기준(10분)의 절반. 매 주기 push하면 하루 수천 개 커밋이 쌓인다.
HEARTBEAT_PUSH_SECONDS = 300
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


def has_unsynced_changes():
    dirty = _git("status", "--porcelain", "state/").stdout.strip()
    ahead = _git("rev-list", "--count", "@{u}..HEAD").stdout.strip()
    return bool(dirty) or ahead not in ("", "0")


def sync(now_str):
    """state/ 변경을 커밋하고 원격을 받아 합친 뒤, 밀린 커밋이 있으면 push한다."""
    _git("add", "state/")
    if _git("diff", "--cached", "--quiet").returncode != 0:
        commit = _git("commit", "-m", f"state: 로컬 감시 스냅샷 갱신 ({now_str}) [skip ci]")
        if commit.returncode != 0:
            print(f"[동기화] commit 실패: {commit.stderr.strip()}", file=sys.stderr)
            return
    # --autostash: 커밋 안 한 코드 수정이 있어도 pull이 막히지 않게 한다.
    # -X theirs: 충돌 시 이 감시기의 state를 우선한다 (rebase에서 theirs = 다시 얹는 로컬 커밋).
    pull = _git("pull", "--rebase", "--autostash", "-X", "theirs")
    if pull.returncode != 0:
        _git("rebase", "--abort")
        print(f"[동기화] pull 실패 (다음 동기화 때 재시도): {pull.stderr.strip()}", file=sys.stderr)
        return
    if _git("rev-list", "--count", "@{u}..HEAD").stdout.strip() in ("", "0"):
        return
    push = _git("push")
    if push.returncode != 0:
        print(f"[동기화] push 실패 (다음 동기화 때 재시도): {push.stderr.strip()}", file=sys.stderr)


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
        print("\n===== 변경 감지 =====\n" + text + "\n=====================\n")
        return notify.send_message(token, chat_id, text)

    session = requests.Session()

    def fetcher(url):
        return fetch.fetch_text(url, session=session)

    hours = config.get("watch_hours")
    window = f"평일 {hours['start']}~{hours['end']}, 주말·공휴일 제외" if hours else "24시간"
    print(f"감시 시작 (감시 시간: {window}, 주기: {LOOP_INTERVAL_SECONDS}초). 종료하려면 Ctrl+C.")
    sync(datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"))  # 시작 시 최신 state 받기
    last_heartbeat = None
    active = None
    while True:
        now = datetime.now(KST)
        now_active = is_watch_time(now, hours)
        if now_active != active:
            active = now_active
            print(f"[{now:%Y-%m-%d %H:%M}] " + ("감시 시간 - 감시 중" if active else "감시 시간 외 - 대기"))
        if not active:
            time.sleep(LOOP_INTERVAL_SECONDS)
            continue
        try:
            run(config, state_dir, fetcher, sender, now=now)
        except Exception as e:
            print(f"[루프] 실행 중 오류: {e}", file=sys.stderr)
        if last_heartbeat is None or (now - last_heartbeat).total_seconds() >= HEARTBEAT_PUSH_SECONDS:
            state.save_heartbeat(state_dir, now.isoformat())
            last_heartbeat = now
        if has_unsynced_changes():
            sync(now.strftime("%Y-%m-%d %H:%M KST"))
        time.sleep(LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    _cli()

import os
import shutil
import subprocess
import sys

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    env_path = os.path.join(REPO_DIR, ".env")
    example_path = os.path.join(REPO_DIR, ".env.example")

    if os.path.exists(env_path):
        return 0

    shutil.copyfile(example_path, env_path)
    print(".env 파일을 새로 만들었습니다.")
    print("메모장이 열리면 텔레그램 봇 토큰과 chat_id를 채운 뒤 저장하고 닫으세요.")
    subprocess.run(["notepad.exe", env_path])
    print()
    print("값을 다 채우셨다면 이 파일을 다시 더블클릭해서 실행하세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

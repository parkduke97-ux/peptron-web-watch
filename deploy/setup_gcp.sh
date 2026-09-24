#!/usr/bin/env bash
# Google Cloud VM(Debian/Ubuntu)에서 한 번 실행: 설치 → .env → GitHub push 키 → 상시 실행 서비스 등록
# 다시 실행해도 안전하다 (이미 된 단계는 건너뜀).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
KEY="$HOME/.ssh/peptron_deploy"
SERVICE=peptron-watch

echo "[1/5] 패키지 설치"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-venv >/dev/null

echo "[2/5] 파이썬 가상환경"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "[3/5] 텔레그램 설정 (.env)"
if [ ! -f .env ]; then
  read -rp "TELEGRAM_BOT_TOKEN: " token
  read -rp "TELEGRAM_CHAT_ID: " chat
  printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n' "$token" "$chat" > .env
  chmod 600 .env
else
  echo ".env 이미 있음 - 건너뜀"
fi

echo "[4/5] GitHub push 권한 (이 저장소 전용 배포 키)"
git config user.name "peptron-watch-vm"
git config user.email "peptron-watch-vm@users.noreply.github.com"
if [ ! -f "$KEY" ]; then
  mkdir -p "$HOME/.ssh"
  ssh-keygen -q -t ed25519 -N "" -C "peptron-watch-vm" -f "$KEY"
fi
git config core.sshCommand "ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
slug="$(git remote get-url origin | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')"
git remote set-url origin "git@github.com:${slug}.git"
until git push --dry-run -q origin HEAD 2>/dev/null; do
  echo
  echo "아래 공개키 한 줄을 GitHub에 등록하세요 ('Allow write access' 체크 필수):"
  echo "  https://github.com/${slug}/settings/keys/new"
  echo
  cat "$KEY.pub"
  echo
  read -rp "등록을 마쳤으면 Enter를 누르세요..."
done
echo "GitHub push 권한 확인됨"

echo "[5/5] 상시 실행 서비스 등록"
sudo tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<EOF
[Unit]
Description=Peptron web watch
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$REPO_DIR
# 재시작할 때마다 GitHub의 최신 코드를 받아서 실행한다
ExecStartPre=-/usr/bin/git pull --rebase --autostash
ExecStart=$REPO_DIR/.venv/bin/python local_loop.py
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE"
sudo systemctl restart "$SERVICE"

echo
echo "완료. 감시가 백그라운드에서 돌고 있습니다 (VM 재부팅 시 자동 시작)."
echo "  실시간 로그:   journalctl -u $SERVICE -f"
echo "  상태 확인:     systemctl status $SERVICE"
echo "  코드 업데이트: sudo systemctl restart $SERVICE"

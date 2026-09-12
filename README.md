# 펩트론 웹사이트 변경 감지 → 텔레그램 알림

펩트론 IR 사이트와 본사 뉴스의 신규/수정/삭제를 감지해 텔레그램으로 알립니다.

## 준비물

### 1. 텔레그램 봇 만들기
1. 텔레그램에서 `@BotFather` 검색 → 대화 시작
2. `/newbot` 입력 → 봇 이름·사용자명 지정
3. 발급된 **토큰**(예: `12345:AAxxxx`) 복사

### 2. chat_id 확인
1. 만든 봇을 검색해 아무 메시지나 전송
2. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates` 접속
3. 응답의 `"chat":{"id": ...}` 값이 **chat_id**

### 3. GitHub에 배포
1. 이 저장소를 본인 GitHub 계정에 push (public 권장 — Actions 무료)
2. 저장소 → Settings → Secrets and variables → Actions → New repository secret
   - `TELEGRAM_BOT_TOKEN` = 위 토큰
   - `TELEGRAM_CHAT_ID` = 위 chat_id
3. Actions 탭 → `peptron-web-watch` → **Run workflow**로 즉시 테스트
   - 첫 실행은 "감시 시작" 알림 1회만 오고 기준선을 저장합니다
   - 이후 **24시간 내내 5분마다** 자동 실행을 시도합니다 — 단, PC 로컬 감시(아래 "PC 상시 감시" 참고)가 최근에 살아있었으면 GitHub은 바로 건너뛰고, PC가 꺼져있을 때만 실제로 감시+알림을 수행합니다
   - PC 상시 감시를 쓰지 않는다면 이 워크플로만으로도 24시간 감시가 됩니다

## PC 상시 감시 + GitHub 대체 실행 (하이브리드 모드)

PC를 켜두는 동안은 PC가 직접 몇 분마다 감시하고, PC가 꺼지면 자동으로 GitHub Actions가 이어받는 구조입니다. 별도 설정 없이 그냥 켜고 끄면 됩니다 — 두 쪽이 서로의 상태를 "하트비트"로 판단합니다.

### 동작 원리
1. PC의 `local_loop.py`가 몇 분(기본 1분)마다 감시를 돌리고, 끝날 때마다 `state/heartbeat.json`에 현재 시각을 기록해 GitHub에 push합니다.
2. GitHub Actions는 5분마다 깨어나서 이 하트비트 파일을 확인합니다. **10분 이내**에 기록된 하트비트가 있으면 "PC가 감시 중"으로 보고 아무 것도 안 하고 종료합니다. 하트비트가 오래됐거나 없으면(PC 꺼짐) 평소처럼 감시+알림+상태 저장을 수행합니다.
3. 둘 다 감시 결과를 `state/`에 저장하고 git에 push하기 때문에, 어느 쪽이 감시했든 다음 실행에서 최신 상태를 이어받습니다.

### PC에서 실행하기 (원클릭)
새 PC에도 Python과 git만 미리 설치돼 있으면 됩니다.
1. 저장소를 git clone 합니다
2. `run_local_watch.bat`을 더블클릭합니다
   - `.env`가 없으면 자동으로 `.env.example`을 복사해 메모장으로 열어줍니다. 텔레그램 토큰/chat_id를 채우고 저장한 뒤 메모장을 닫으세요
   - 안내에 따라 **다시 한번 더블클릭**하면, 이번엔 필요한 패키지를 자동 설치하고 바로 감시를 시작합니다
3. 창을 켜둔 채로 두면 계속 감시합니다. 종료하려면 창을 닫거나 Ctrl+C

터미널을 직접 쓰고 싶다면 `python -m pip install -r requirements.txt` 후 `python local_loop.py`를 실행해도 동일합니다.

### 실행 상태 바로 확인하기
`check_status.bat`을 더블클릭하면 그 PC에서:
- `local_loop.py` 프로세스가 실제로 떠 있는지(PID)
- 마지막 하트비트 기록 시각과 신선도(10분 이내인지)

를 즉시 보여줍니다. 감시가 잘 돌고 있는지 매번 콘솔 로그를 눈으로 훑을 필요 없이 이 배치파일 하나로 확인할 수 있습니다.

### 주의할 점
- `local_loop.py`는 매 주기마다 `git pull --rebase` 후 `git push`를 시도합니다. PC의 git 자격증명(예: `gh auth login` 또는 credential helper)이 이 저장소에 push할 수 있게 미리 설정되어 있어야 합니다.
- 하트비트 신선도 기준(10분)은 `check_heartbeat.py`의 `HEARTBEAT_FRESH_MINUTES`, 로컬 실행 주기(1분)는 `local_loop.py`의 `LOOP_INTERVAL_SECONDS`에서 바꿀 수 있습니다. 로컬 주기를 늘릴 경우 하트비트 기준도 그에 맞춰 여유 있게 늘리세요 (기준이 로컬 주기보다 최소 2~3배는 커야 정상 동작 중에 GitHub이 오판하지 않습니다).
- PC 인터넷이 끊기거나 스크립트만 죽고 PC는 켜져 있는 경우에도, 하트비트가 10분 넘게 갱신 안 되면 GitHub이 자동으로 이어받습니다.

## public vs private 저장소 — 실행 비용 트레이드오프

GitHub 쪽 워크플로는 24시간 5분 간격으로 트리거됩니다(하루 288회, 월 약 8,760회) — 다만 PC가 감시 중이면 대부분 즉시 건너뛰고 종료되므로 실제 크롤링은 PC가 꺼져있는 시간만큼만 일어납니다. 저장소 공개 여부에 따라 GitHub Actions 사용 조건이 달라집니다.

- **public 저장소(기본값, 권장)**: Actions 실행이 무료·무제한입니다. 하트비트만 확인하고 건너뛰는 실행이 대부분이라도 비용 문제가 전혀 없습니다. 단, 코드 전체와 "이 사이트를 감시하고 있다"는 사실이 누구에게나 공개됩니다.
- **private 저장소**: 저장소 내용은 비공개로 유지되지만, 예약 실행(scheduled Actions)은 매월 무료 2,000분을 소진하며 GitHub은 실행 시간을 **분 단위로 올림 과금**합니다. 하트비트 확인만 하고 끝나는 실행도 최소 1분으로 과금되므로, 월 8,760회 실행은 PC를 거의 항상 켜두더라도 무료 한도(2,000분)를 훌쩍 넘깁니다. private로 유지하려면 `.github/workflows/watch.yml`의 `schedule` 간격을 늘리세요(예: `*/15 * * * *`로 바꾸면 월 약 2,920회).

> 참고: GitHub의 예약 실행은 러너가 혼잡하면 수 분 지연되거나 건너뛸 수 있습니다. 정시 실행이 보장되지는 않습니다.

## 로컬 테스트
```bash
python -m pip install -r requirements.txt
python main.py --dry-run   # 텔레그램 전송 없이 콘솔 출력만
python -m pytest -v        # 전체 테스트
```

## 감시 대상 바꾸기
`watch_config.yaml`의 `targets`에 URL을 추가/삭제하고, `keywords`로 중요 키워드를 조정하세요.

## 하지 않는 것
공개된 콘텐츠의 변화·삭제만 감지합니다. 비공개/미공개 항목을 서버에서 꺼내오지 않습니다.

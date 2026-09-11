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
   - 이후 5분마다 자동 실행되며 변경이 있을 때만 알림합니다

## public vs private 저장소 — 실행 비용 트레이드오프

이 워크플로는 `*/5 * * * *` (5분 간격) cron으로 동작합니다. 저장소 공개 여부에 따라 GitHub Actions 사용 조건이 달라집니다.

- **public 저장소**: Actions 실행이 무료·무제한입니다. `*/5` cron을 그대로 써도 비용 문제가 없습니다. 단, 코드 전체와 "이 사이트를 감시하고 있다"는 사실이 누구에게나 공개됩니다.
- **private 저장소**: 저장소 내용(코드, 커밋된 상태 스냅샷 등)은 비공개로 유지됩니다. 다만 예약 실행(scheduled Actions)은 매월 무료 2,000분을 소진하며, `*/5` cron은 한 달에 약 8,600회 실행되어 무료 한도를 초과합니다. private로 유지하려면:
  - `.github/workflows/watch.yml`의 `cron: '*/5 * * * *'` 줄(현재 5번째 줄)을 더 긴 간격(예: `*/30 * * * *`)으로 바꾸거나,
  - 초과분에 대한 Actions 분당 과금을 감수하세요.

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

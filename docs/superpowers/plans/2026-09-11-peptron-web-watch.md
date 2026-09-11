# 펩트론 웹사이트 변경 감지 → 텔레그램 알림 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 펩트론 IR 사이트와 본사 사이트의 공개 콘텐츠가 신규 등록·수정·삭제될 때를 감지해 텔레그램으로 알림한다.

**Architecture:** 설정 파일(`watch_config.yaml`)에 감시 대상 URL과 페이지 유형을 정의한다. 각 회차마다 `fetch`(HTTP) → `extract`(유형별로 항목 리스트 추출) → `compare`(이전 스냅샷과 비교해 이벤트 생성) → `enrich`(중요도·변경비율·키워드·사건ID 부여) → `render`(텔레그램 메시지) → `notify`(전송) → `state`(스냅샷 저장) 순으로 흐른다. 각 모듈은 순수 함수 위주로 짜여 네트워크 없이 픽스처만으로 테스트된다. GitHub Actions cron(5분)으로 실행하며 스냅샷을 리포지토리에 커밋해 변경 이력을 남긴다.

**Tech Stack:** Python 3.11, `requests`(HTTP), `beautifulsoup4`(HTML 파싱, stdlib `html.parser` 백엔드), `PyYAML`(설정), `pytest`(테스트). 표준 라이브러리 `difflib`(변경 비율·diff), `hashlib`(사건 ID).

**Spec:** `docs/superpowers/specs/2026-09-11-peptron-ir-watch-design.md`

## Global Constraints

- Python 3.11 이상. 의존성은 `requests`, `beautifulsoup4`, `PyYAML`, `pytest`만 사용(추가 시 명시).
- HTML 파싱은 BeautifulSoup + `html.parser`(stdlib 백엔드) 사용 — lxml 빌드 의존성 회피.
- 모든 시각 표기는 KST(UTC+9). `datetime.timezone(timedelta(hours=9))`.
- 대상 사이트 응답 인코딩은 UTF-8. HTTP 요청 시 `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)` 헤더를 붙인다.
- 텔레그램 봇 토큰·chat_id는 코드에 두지 않고 환경변수 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`(로컬은 `.env` 아님, GitHub는 Secrets)에서 읽는다.
- **미공개/숨김 항목 탐침 기능은 만들지 않는다**(스펙 §13). 공개 목록에 있는 항목만 처리한다.
- git 커밋 메시지 말미:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg
  ```
- 픽스처는 이미 저장됨: `tests/fixtures/ir_default2.html`, `ir_activity_246.json`, `ir_activity_244.json`, `corp_news_list.html`.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `requirements.txt` | 의존성 목록 |
| `watch_config.yaml` | 감시 대상 URL·유형·분류, 워치리스트 키워드 |
| `peptron_watch/__init__.py` | 패키지 초기화 (빈 파일) |
| `peptron_watch/normalize.py` | HTML/텍스트 정규화 (오탐 방지 핵심) |
| `peptron_watch/extract.py` | 페이지 유형별 항목 추출 (IR_FAQ, IR_TABLE, IR_ACTIVITY, LINK_LIST, GENERIC_TEXT) |
| `peptron_watch/compare.py` | 이전/현재 스냅샷 비교 → 이벤트 생성 |
| `peptron_watch/enrich.py` | 이벤트에 중요도·변경비율·키워드·사건ID·시각 부여 |
| `peptron_watch/render.py` | 이벤트 → 텔레그램 메시지 문자열 |
| `peptron_watch/fetch.py` | HTTP GET (재시도·백오프) |
| `peptron_watch/notify.py` | 텔레그램 전송 |
| `peptron_watch/state.py` | 스냅샷·health 읽기/쓰기 |
| `main.py` | 전체 흐름 조율, baseline 처리, 설정 로드 |
| `.github/workflows/watch.yml` | 5분 cron 실행 및 스냅샷 커밋 |
| `README.md` | 봇 토큰 발급~배포 단계별 안내 |

## 공통 데이터 모델

모든 추출기는 **항목(item) dict의 리스트**를 반환한다:

```python
{
    "key": str,      # 대상 내 안정적 식별자 (FAQ: 제목, IR자료: IRActivityID, 링크: "no=115")
    "title": str,    # 표시용 제목
    "date": str,     # 표시용 날짜, 없으면 ""
    "text": str,     # 비교 대상 정규화 텍스트 (변경 감지의 핵심 필드)
    "url": str,      # 이 항목의 딥링크
    "extra": dict,   # 부가 표시 필드 (IR자료: {"DeleteFlag": "N", ...}), 없으면 {}
}
```

`compare`가 만드는 **이벤트(event) dict**:

```python
{
    "target_key": str, "target_label": str, "page_class": str, "url": str,
    "kind": str,                 # "NEW" | "MODIFIED" | "REMOVED"
    "item_key": str, "title": str, "date": str,
    "title_before": str, "title_after": str,   # MODIFIED에서 제목 변경 시
    "date_before": str, "date_after": str,      # MODIFIED에서 날짜 변경 시
    "added_lines": list[str], "removed_lines": list[str],
    "text_before": str, "text_after": str,      # 변경 비율 계산용
}
```

`enrich`가 추가하는 키: `importance`(str), `change_ratio`(float), `keywords`(list[str]), `event_id`(str), `event_type_label`(str), `detected_at`(str, "YYYY-MM-DD HH:MM:SS KST").

---

### Task 1: 프로젝트 스캐폴딩 + 텍스트 정규화

정규화는 오탐(가짜 알림) 방지의 토대이므로 가장 먼저, 가장 촘촘히 테스트한다.

**Files:**
- Create: `requirements.txt`
- Create: `peptron_watch/__init__.py` (빈 파일)
- Create: `peptron_watch/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `normalize_text(text: str) -> str` — 줄 단위 좌우 공백 제거, 연속 공백 1칸, 빈 줄 최대 1개, 앞뒤 공백 제거
  - `html_to_text(html: str) -> str` — script/style 제거, `<br>`/`</p>`/`</li>` → 줄바꿈, 나머지 태그 제거, HTML 엔티티 디코드 후 `normalize_text` 적용

- [ ] **Step 1: `requirements.txt` 작성 및 의존성 설치**

`requirements.txt`:
```
requests>=2.31
beautifulsoup4>=4.12
PyYAML>=6.0
pytest>=8.0
```

Run: `python -m pip install -r requirements.txt`
Expected: 설치 성공

- [ ] **Step 2: 빈 패키지 초기화 파일 생성**

`peptron_watch/__init__.py`는 빈 파일로 생성.

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_normalize.py`:
```python
from peptron_watch.normalize import normalize_text, html_to_text


def test_normalize_collapses_whitespace_and_blank_lines():
    raw = "  Q1.  질문   내용  \n\n\n\n  A1. 답변 \n"
    assert normalize_text(raw) == "Q1. 질문 내용\n\nA1. 답변"


def test_html_to_text_strips_tags_and_editor_attrs():
    html = (
        '<h3 data-start="128" data-section-id="4ybbmx">제목</h3>'
        '<p>첫 문장.</p><p>둘째 문장.</p>'
    )
    assert html_to_text(html) == "제목\n첫 문장.\n둘째 문장."


def test_html_to_text_removes_scripts_and_decodes_entities():
    html = "<script>var x=1;</script><p>A&nbsp;B &amp; C</p>"
    assert html_to_text(html) == "A B & C"


def test_only_editor_attr_change_yields_identical_text():
    # 편집기가 data-start 값만 바꿔 저장한 경우 → 동일 텍스트여야 함(오탐 방지)
    a = '<p data-start="10" data-end="20">동일한 문장입니다.</p>'
    b = '<p data-start="99" data-end="105">동일한 문장입니다.</p>'
    assert html_to_text(a) == html_to_text(b)
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL (`ModuleNotFoundError: peptron_watch.normalize`)

- [ ] **Step 5: 최소 구현 작성**

`peptron_watch/normalize.py`:
```python
import re
import html as _html


def normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t　]+", " ", ln).strip() for ln in text.split("\n")]
    # 연속 빈 줄을 최대 1개로 압축
    out = []
    for ln in lines:
        if ln == "" and out and out[-1] == "":
            continue
        out.append(ln)
    return "\n".join(out).strip()


def html_to_text(html: str) -> str:
    # script/style 제거
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", html)
    # 블록 경계 → 줄바꿈
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|li|div|h[1-6]|tr)>", "\n", html)
    # 나머지 태그 제거
    html = re.sub(r"(?s)<[^>]+>", "", html)
    # 엔티티 디코드
    html = _html.unescape(html)
    return normalize_text(html)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt peptron_watch/__init__.py peptron_watch/normalize.py tests/test_normalize.py
git commit -m "feat: 텍스트 정규화 모듈 (오탐 방지 토대)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 2: IR 페이지 추출기 — FAQ + 표(공시/경영공시)

**Files:**
- Create: `peptron_watch/extract.py`
- Test: `tests/test_extract_ir_page.py`

**Interfaces:**
- Consumes: `normalize.html_to_text`, `normalize.normalize_text`
- Produces:
  - `extract_ir_faq(page_html: str, base_url: str) -> list[dict]` — `#section007 .faq-list li` 각각을 항목으로. `key`=제목, `text`=제목+본문 정규화, `url`=`base_url + "#section007"`
  - `extract_ir_table(page_html: str, section_id: str, base_url: str) -> list[dict]` — `#<section_id>` 내 `tbody tr`. `key`=`"제목|제출인|날짜"` 또는 공시 접수번호(있으면), `title`=제목, `date`=마지막 셀, `text`=행 전체 텍스트, `url`=`base_url + "#" + section_id`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_ir_page.py`:
```python
from pathlib import Path
from peptron_watch.extract import extract_ir_faq, extract_ir_table

FIX = Path(__file__).parent / "fixtures"
BASE = "https://peptron.irupsite.co.kr/Default2.aspx"


def _page():
    return (FIX / "ir_default2.html").read_text(encoding="utf-8")


def test_extract_ir_faq_returns_items_with_body():
    items = extract_ir_faq(_page(), BASE)
    assert len(items) >= 1
    faq = items[0]
    assert faq["key"] == "자주묻는질문(FAQ)"
    assert faq["date"] == "2026-09-11"
    # 본문에 실제 Q 문항이 들어 있어야 함
    assert "일라이 릴리" in faq["text"]
    assert faq["url"].endswith("#section007")


def test_extract_ir_table_disclosure_has_rows():
    items = extract_ir_table(_page(), "section004", BASE)
    assert len(items) >= 1
    assert all(it["key"] for it in items)
    assert items[0]["url"].endswith("#section004")


def test_extract_ir_faq_stable_across_calls():
    # 같은 입력 두 번 → 완전히 동일한 결과(오탐 방지)
    assert extract_ir_faq(_page(), BASE) == extract_ir_faq(_page(), BASE)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract_ir_page.py -v`
Expected: FAIL (`ImportError` / `cannot import name 'extract_ir_faq'`)

- [ ] **Step 3: 최소 구현 작성**

`peptron_watch/extract.py`:
```python
from bs4 import BeautifulSoup
from .normalize import html_to_text, normalize_text


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def extract_ir_faq(page_html: str, base_url: str) -> list[dict]:
    soup = _soup(page_html)
    section = soup.select_one("#section007")
    items = []
    if not section:
        return items
    for li in section.select(".faq-list li"):
        tit_el = li.select_one(".tit")
        date_el = li.select_one(".date")
        body_el = li.select_one(".target")
        title = normalize_text(tit_el.get_text()) if tit_el else ""
        date = normalize_text(date_el.get_text()) if date_el else ""
        body = html_to_text(str(body_el)) if body_el else ""
        text = normalize_text(f"{title}\n{body}")
        items.append({
            "key": title, "title": title, "date": date,
            "text": text, "url": base_url + "#section007", "extra": {},
        })
    return items


def extract_ir_table(page_html: str, section_id: str, base_url: str) -> list[dict]:
    soup = _soup(page_html)
    section = soup.select_one(f"#{section_id}")
    items = []
    if not section:
        return items
    for tr in section.select("tbody tr"):
        cells = [normalize_text(td.get_text()) for td in tr.find_all("td")]
        if not cells:
            continue
        title = cells[0]
        date = cells[-1] if len(cells) > 1 else ""
        text = " | ".join(cells)
        items.append({
            "key": text, "title": title, "date": date,
            "text": text, "url": base_url + "#" + section_id, "extra": {},
        })
    return items
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract_ir_page.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/extract.py tests/test_extract_ir_page.py
git commit -m "feat: IR 페이지 FAQ·표 추출기

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 3: IR자료실 추출기 — 목록 파싱 + 상세 JSON 파싱

**Files:**
- Modify: `peptron_watch/extract.py`
- Test: `tests/test_extract_ir_activity.py`

**Interfaces:**
- Consumes: `normalize.html_to_text`
- Produces:
  - `extract_ir_activity_list(page_html: str) -> list[dict]` — `#section009`의 `popOpen(...)` 인자에서 `{"id": str, "title": str, "date": str}` 추출 (마지막 인자가 IRActivityID)
  - `parse_ir_activity_detail(json_text: str, base_url: str) -> dict` — Detail2AJAX JSON → 항목 dict. `key`=IRActivityID(str), `text`=Subject+본문(html_to_text)+정렬된 부가필드, `extra`={"DeleteFlag","MainFlag","FileName","RegisterDate"}, `url`=`base_url+"#section009"`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_ir_activity.py`:
```python
from pathlib import Path
from peptron_watch.extract import extract_ir_activity_list, parse_ir_activity_detail

FIX = Path(__file__).parent / "fixtures"
BASE = "https://peptron.irupsite.co.kr/Default2.aspx"


def test_extract_activity_list_finds_ids():
    page = (FIX / "ir_default2.html").read_text(encoding="utf-8")
    items = extract_ir_activity_list(page)
    ids = {it["id"] for it in items}
    assert "246" in ids and "244" in ids
    it246 = next(it for it in items if it["id"] == "246")
    assert "CPHI Milan 2026" in it246["title"]
    assert it246["date"] == "2026-09-09"


def test_parse_activity_detail_extracts_body_and_flags():
    raw = (FIX / "ir_activity_246.json").read_text(encoding="utf-8")
    item = parse_ir_activity_detail(raw, BASE)
    assert item["key"] == "246"
    assert "CPHI Milan 2026" in item["text"]
    assert item["extra"]["DeleteFlag"] == "N"
    assert "RegisterDate" in item["extra"]
    assert item["url"].endswith("#section009")


def test_parse_activity_detail_body_change_changes_text():
    raw = (FIX / "ir_activity_246.json").read_text(encoding="utf-8")
    modified = raw.replace("CPHI Milan 2026", "CPHI Milan 2027")
    assert parse_ir_activity_detail(raw, BASE)["text"] != \
        parse_ir_activity_detail(modified, BASE)["text"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract_ir_activity.py -v`
Expected: FAIL (`cannot import name 'extract_ir_activity_list'`)

- [ ] **Step 3: 최소 구현 추가**

`peptron_watch/extract.py` 상단 import에 `import json`, `import re` 추가하고 아래 함수 추가:
```python
import json
import re

_POPOPEN_RE = re.compile(
    r"popOpen\(\s*'[^']*'\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*'([^']*)'"
    r"(?:\s*,\s*'[^']*'){3}\s*,\s*'(\d+)'"
)


def extract_ir_activity_list(page_html: str) -> list[dict]:
    soup = _soup(page_html)
    section = soup.select_one("#section009")
    items = []
    if not section:
        return items
    for a in section.select("a[href^='javascript:popOpen']"):
        m = _POPOPEN_RE.search(a.get("href", ""))
        if not m:
            continue
        title, date, act_id = m.group(1), m.group(2), m.group(3)
        items.append({"id": act_id, "title": title.replace("\\'", "'"), "date": date})
    return items


def parse_ir_activity_detail(json_text: str, base_url: str) -> dict:
    d = json.loads(json_text)
    subject = d.get("Subject") or ""
    body = html_to_text(d.get("Description") or "")
    flags = {
        "DeleteFlag": d.get("DeleteFlag"),
        "MainFlag": d.get("MainFlag"),
        "FileName": d.get("FileName") or "",
        "RegisterDate": d.get("RegisterDate"),
    }
    flag_text = "\n".join(f"{k}={v}" for k, v in sorted(flags.items()))
    text = normalize_text(f"{subject}\n{body}\n{flag_text}")
    return {
        "key": str(d.get("IRActivityID")),
        "title": subject,
        "date": "",
        "text": text,
        "url": base_url + "#section009",
        "extra": flags,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract_ir_activity.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/extract.py tests/test_extract_ir_activity.py
git commit -m "feat: IR자료실 목록·상세 JSON 추출기 (본문+숨김플래그 지문화)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 4: 링크 목록 추출기 + 일반 텍스트 추출기

**Files:**
- Modify: `peptron_watch/extract.py`
- Test: `tests/test_extract_generic.py`

**Interfaces:**
- Consumes: `normalize.html_to_text`
- Produces:
  - `extract_link_list(page_html: str, base_url: str, id_param: str = "no") -> list[dict]` — `<a href>` 중 `id_param`(예: `no`) 쿼리값을 가진 링크만. `key`=`f"{id_param}={값}"`, `title`=링크 텍스트, `text`=key, `url`=절대 URL. **`page` 같은 휘발성 파라미터는 key에 넣지 않아** 페이지네이션 오탐 방지
  - `extract_generic_text(page_html: str, base_url: str) -> list[dict]` — 페이지 전체를 항목 1개로. `key`=`"page"`, `text`=`html_to_text(page_html)`, `url`=base_url

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract_generic.py`:
```python
from pathlib import Path
from peptron_watch.extract import extract_link_list, extract_generic_text

FIX = Path(__file__).parent / "fixtures"
CORP = "https://www.peptron.co.kr/ds4_1_1.html"


def test_extract_link_list_uses_no_param_as_key():
    html = (FIX / "corp_news_list.html").read_text(encoding="utf-8")
    items = extract_link_list(html, CORP, id_param="no")
    keys = {it["key"] for it in items}
    assert "no=115" in keys
    # 각 key는 유일해야 함(page 파라미터가 달라도 중복 아님)
    assert len(keys) == len(items)


def test_link_list_ignores_volatile_page_param():
    html = '<a href="?db=newsp&no=50&c=view&page=1">A</a>' \
           '<a href="?db=newsp&no=50&c=view&page=2">A</a>'
    items = extract_link_list(html, CORP, id_param="no")
    assert len(items) == 1
    assert items[0]["key"] == "no=50"


def test_generic_text_single_item():
    html = "<html><body><p>본문 한 줄.</p></body></html>"
    items = extract_generic_text(html, CORP)
    assert len(items) == 1
    assert items[0]["key"] == "page"
    assert "본문 한 줄." in items[0]["text"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract_generic.py -v`
Expected: FAIL (`cannot import name 'extract_link_list'`)

- [ ] **Step 3: 최소 구현 추가**

`peptron_watch/extract.py` 상단에 `from urllib.parse import urljoin, urlparse, parse_qs` 추가 후:
```python
from urllib.parse import urljoin, urlparse, parse_qs


def extract_link_list(page_html: str, base_url: str, id_param: str = "no") -> list[dict]:
    soup = _soup(page_html)
    seen = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        qs = parse_qs(urlparse(href).query)
        if id_param not in qs:
            continue
        key = f"{id_param}={qs[id_param][0]}"
        if key in seen:
            continue
        seen[key] = {
            "key": key,
            "title": normalize_text(a.get_text()),
            "date": "",
            "text": key,
            "url": urljoin(base_url, href),
            "extra": {},
        }
    return list(seen.values())


def extract_generic_text(page_html: str, base_url: str) -> list[dict]:
    return [{
        "key": "page", "title": "", "date": "",
        "text": html_to_text(page_html), "url": base_url, "extra": {},
    }]
```
(`normalize_text`가 파일에 이미 import되어 있어야 함 — Task 2에서 추가됨)

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract_generic.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/extract.py tests/test_extract_generic.py
git commit -m "feat: 링크목록·일반텍스트 추출기 (page 파라미터 오탐 방지)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 5: 비교 엔진 (신규/수정/삭제)

**Files:**
- Create: `peptron_watch/compare.py`
- Test: `tests/test_compare.py`

**Interfaces:**
- Consumes: 항목 dict 리스트 (모든 추출기 공통 형식)
- Produces:
  - `compare_items(old_items: list[dict], new_items: list[dict], target: dict) -> list[dict]` — `target`은 `{"key","label","page_class","url"}`. `key` 기준으로 매칭. new에만 있으면 NEW, old에만 있으면 REMOVED, 둘 다 있고 `text`가 다르면 MODIFIED. MODIFIED는 `added_lines`/`removed_lines`(text 줄 diff)와 title/date 변경을 채운다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_compare.py`:
```python
from peptron_watch.compare import compare_items

TARGET = {"key": "ir_faq", "label": "FAQ", "page_class": "IR",
          "url": "https://x/#s"}


def _item(key, text, title=None, date=""):
    return {"key": key, "title": title or key, "date": date,
            "text": text, "url": "https://x/#s", "extra": {}}


def test_no_change_yields_no_events():
    items = [_item("a", "line1\nline2")]
    assert compare_items(items, items, TARGET) == []


def test_new_item_detected():
    old = [_item("a", "x")]
    new = [_item("a", "x"), _item("b", "y")]
    events = compare_items(old, new, TARGET)
    assert len(events) == 1
    assert events[0]["kind"] == "NEW"
    assert events[0]["item_key"] == "b"


def test_removed_item_detected():
    old = [_item("a", "x"), _item("b", "y")]
    new = [_item("a", "x")]
    events = compare_items(old, new, TARGET)
    assert len(events) == 1
    assert events[0]["kind"] == "REMOVED"
    assert events[0]["item_key"] == "b"


def test_modified_body_produces_diff_lines():
    old = [_item("a", "Q3. 체결기한입니까?\n아닙니다. 기본 계약기간과 관련된 시점입니다.")]
    new = [_item("a", "Q3. 체결기한입니까?\n아닙니다. 후속 계약 일정과 무관합니다.")]
    events = compare_items(old, new, TARGET)
    assert len(events) == 1
    e = events[0]
    assert e["kind"] == "MODIFIED"
    assert any("기본 계약기간" in ln for ln in e["removed_lines"])
    assert any("후속 계약 일정" in ln for ln in e["added_lines"])
    assert e["text_before"] and e["text_after"]


def test_title_change_recorded():
    old = [_item("a", "same", title="옛 제목")]
    new = [_item("a", "same2", title="새 제목")]
    e = compare_items(old, new, TARGET)[0]
    assert e["title_before"] == "옛 제목" and e["title_after"] == "새 제목"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_compare.py -v`
Expected: FAIL (`ModuleNotFoundError: peptron_watch.compare`)

- [ ] **Step 3: 최소 구현 작성**

`peptron_watch/compare.py`:
```python
import difflib


def _diff_lines(before: str, after: str):
    old_lines = before.split("\n")
    new_lines = after.split("\n")
    added, removed = [], []
    for ln in difflib.unified_diff(old_lines, new_lines, lineterm="", n=0):
        if ln.startswith("+") and not ln.startswith("+++"):
            added.append(ln[1:])
        elif ln.startswith("-") and not ln.startswith("---"):
            removed.append(ln[1:])
    return added, removed


def _event(target, kind, item, **extra):
    e = {
        "target_key": target["key"], "target_label": target["label"],
        "page_class": target["page_class"], "url": item.get("url") or target["url"],
        "kind": kind, "item_key": item["key"],
        "title": item.get("title", ""), "date": item.get("date", ""),
        "title_before": "", "title_after": "",
        "date_before": "", "date_after": "",
        "added_lines": [], "removed_lines": [],
        "text_before": "", "text_after": "",
    }
    e.update(extra)
    return e


def compare_items(old_items, new_items, target):
    old = {it["key"]: it for it in old_items}
    new = {it["key"]: it for it in new_items}
    events = []
    for key, item in new.items():
        if key not in old:
            events.append(_event(target, "NEW", item))
        elif item["text"] != old[key]["text"]:
            added, removed = _diff_lines(old[key]["text"], item["text"])
            ev = _event(
                target, "MODIFIED", item,
                added_lines=added, removed_lines=removed,
                text_before=old[key]["text"], text_after=item["text"],
            )
            if old[key].get("title", "") != item.get("title", ""):
                ev["title_before"] = old[key].get("title", "")
                ev["title_after"] = item.get("title", "")
            if old[key].get("date", "") != item.get("date", ""):
                ev["date_before"] = old[key].get("date", "")
                ev["date_after"] = item.get("date", "")
            events.append(ev)
    for key, item in old.items():
        if key not in new:
            events.append(_event(target, "REMOVED", item))
    return events
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_compare.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/compare.py tests/test_compare.py
git commit -m "feat: 신규/수정/삭제 비교 엔진 + 줄단위 diff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 6: 이벤트 강화 (중요도·변경비율·키워드·사건ID)

**Files:**
- Create: `peptron_watch/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `compare.compare_items`가 만든 이벤트 dict
- Produces:
  - `enrich_event(event: dict, keywords: list[str], now=None) -> dict` — 원본 이벤트에 `importance`, `change_ratio`, `keywords`, `event_id`, `event_type_label`, `detected_at`를 채워 반환
  - 규칙: 워치리스트 키워드가 변경 내용(added+removed+title)에 있거나 / page_class=="DISCLOSURE" NEW / kind=="REMOVED" → `CRITICAL`. FAQ·IR 본문 MODIFIED, NEW → `HIGH`. 그 외 `NORMAL`.
  - `event_type_label`: NEW→"신규 게시글", MODIFIED→"기존 게시글 수정", REMOVED→"게시글 삭제".
  - `change_ratio`: `round((1 - difflib.SequenceMatcher(None, before_lines, after_lines).ratio()) * 100, 1)`. NEW/REMOVED는 100.0.
  - `event_id`: `"EVT-" + sha256((target_key+item_key+"\n".join(added+removed)).encode()).hexdigest()[:10].upper()`.
  - `detected_at`: `now`(KST) → `"YYYY-MM-DD HH:MM:SS KST"`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_enrich.py`:
```python
from datetime import datetime, timezone, timedelta
from peptron_watch.enrich import enrich_event

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 11, 14, 9, 14, tzinfo=KST)
KW = ["SmartDepot", "릴리", "기술이전"]


def _base(**kw):
    e = {"target_key": "ir_faq", "target_label": "FAQ", "page_class": "IR",
         "url": "https://x", "kind": "MODIFIED", "item_key": "a",
         "title": "FAQ", "date": "", "title_before": "", "title_after": "",
         "date_before": "", "date_after": "",
         "added_lines": [], "removed_lines": [],
         "text_before": "", "text_after": ""}
    e.update(kw)
    return e


def test_keyword_match_makes_critical():
    e = enrich_event(_base(added_lines=["... SmartDepot 관련 ..."]), KW, now=NOW)
    assert e["importance"] == "CRITICAL"
    assert "SmartDepot" in e["keywords"]


def test_removed_is_critical():
    e = enrich_event(_base(kind="REMOVED"), KW, now=NOW)
    assert e["importance"] == "CRITICAL"
    assert e["event_type_label"] == "게시글 삭제"


def test_plain_modification_is_high():
    e = enrich_event(_base(added_lines=["평범한 문구"], removed_lines=["다른 문구"]), KW, now=NOW)
    assert e["importance"] == "HIGH"


def test_change_ratio_and_event_id_and_time():
    e = enrich_event(_base(
        added_lines=["b"], removed_lines=["a"],
        text_before="a\nc\nd\ne", text_after="b\nc\nd\ne"), KW, now=NOW)
    assert 0 < e["change_ratio"] < 100
    assert e["event_id"].startswith("EVT-") and len(e["event_id"]) == 14
    assert e["detected_at"] == "2026-09-11 14:09:14 KST"


def test_event_id_stable_for_same_change():
    a = enrich_event(_base(added_lines=["x"]), KW, now=NOW)
    b = enrich_event(_base(added_lines=["x"]), KW, now=NOW)
    assert a["event_id"] == b["event_id"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: FAIL (`ModuleNotFoundError: peptron_watch.enrich`)

- [ ] **Step 3: 최소 구현 작성**

`peptron_watch/enrich.py`:
```python
import difflib
import hashlib
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

_TYPE_LABEL = {"NEW": "신규 게시글", "MODIFIED": "기존 게시글 수정", "REMOVED": "게시글 삭제"}


def _matched_keywords(event, keywords):
    haystack = "\n".join(
        event.get("added_lines", []) + event.get("removed_lines", [])
        + [event.get("title", ""), event.get("title_after", "")]
    ).lower()
    return [kw for kw in keywords if kw.lower() in haystack]


def _importance(event, matched):
    if matched:
        return "CRITICAL"
    if event["kind"] == "REMOVED":
        return "CRITICAL"
    if event["kind"] == "NEW" and event["page_class"] == "DISCLOSURE":
        return "CRITICAL"
    if event["kind"] in ("NEW", "MODIFIED"):
        return "HIGH"
    return "NORMAL"


def _change_ratio(event):
    if event["kind"] in ("NEW", "REMOVED"):
        return 100.0
    before = event.get("text_before", "").split("\n")
    after = event.get("text_after", "").split("\n")
    ratio = difflib.SequenceMatcher(None, before, after).ratio()
    return round((1 - ratio) * 100, 1)


def _event_id(event):
    seed = event["target_key"] + event["item_key"] + "\n".join(
        event.get("added_lines", []) + event.get("removed_lines", []))
    return "EVT-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10].upper()


def enrich_event(event, keywords, now=None):
    now = now or datetime.now(KST)
    matched = _matched_keywords(event, keywords)
    out = dict(event)
    out["keywords"] = matched
    out["importance"] = _importance(event, matched)
    out["change_ratio"] = _change_ratio(event)
    out["event_id"] = _event_id(event)
    out["event_type_label"] = _TYPE_LABEL.get(event["kind"], event["kind"])
    out["detected_at"] = now.strftime("%Y-%m-%d %H:%M:%S KST")
    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/enrich.py tests/test_enrich.py
git commit -m "feat: 이벤트 강화 (중요도/변경비율/키워드/사건ID)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 7: 텔레그램 메시지 렌더링

**Files:**
- Create: `peptron_watch/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `enrich_event`가 반환한 강화 이벤트
- Produces:
  - `render_event(event: dict, max_len: int = 3800) -> str` — 스펙 §9 형식의 메시지. 중요도 이모지(CRITICAL=🔴, HIGH=🟠, NORMAL=🟢), 필드(중요도/구분/페이지 분류/페이지/발견 시각/사건 ID), 제목 변경 시 이전·이후, 추가/삭제 줄, 변경 비율, 관련 키워드, 원문 링크. `max_len` 초과 시 diff를 자르고 "…외 N줄 더 변경됨"을 붙임.
  - `render_startup(counts: dict, now_str: str) -> str` — baseline 시작 알림.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render.py`:
```python
from peptron_watch.render import render_event, render_startup


def _ev(**kw):
    e = {"target_label": "자주묻는질문(FAQ)", "page_class": "IR", "url": "https://x/#s",
         "kind": "MODIFIED", "importance": "CRITICAL",
         "event_type_label": "기존 게시글 수정", "item_key": "a",
         "title": "자주묻는질문(FAQ)", "title_before": "", "title_after": "",
         "added_lines": ["+추가된 문장"], "removed_lines": ["-삭제된 문장"],
         "change_ratio": 3.3, "keywords": ["SmartDepot"],
         "event_id": "EVT-5C3DB3A783", "detected_at": "2026-09-11 14:09:14 KST"}
    e.update(kw)
    return e


def test_render_contains_core_fields():
    msg = render_event(_ev())
    assert "중요도: CRITICAL" in msg
    assert "구분: 기존 게시글 수정" in msg
    assert "페이지 분류: IR" in msg
    assert "사건 ID: EVT-5C3DB3A783" in msg
    assert "변경 비율: 3.3%" in msg
    assert "관련 키워드: SmartDepot" in msg
    assert "https://x/#s" in msg
    assert "추가된 문장" in msg and "삭제된 문장" in msg


def test_render_truncates_long_diff():
    big = [f"라인 {i}" for i in range(1000)]
    msg = render_event(_ev(added_lines=big), max_len=1000)
    assert len(msg) <= 1000
    assert "외" in msg and "더 변경" in msg


def test_render_shows_title_change():
    msg = render_event(_ev(title_before="옛 제목", title_after="새 제목"))
    assert "이전 제목: 옛 제목" in msg
    assert "변경 후 제목: 새 제목" in msg


def test_render_no_keyword_line_when_empty():
    msg = render_event(_ev(keywords=[]))
    assert "관련 키워드" not in msg


def test_render_startup():
    msg = render_startup({"ir_faq": 1, "corp_news": 20}, "2026-09-11 14:00:00 KST")
    assert "감시" in msg and "ir_faq" in msg and "20" in msg
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL (`ModuleNotFoundError: peptron_watch.render`)

- [ ] **Step 3: 최소 구현 작성**

`peptron_watch/render.py`:
```python
_EMOJI = {"CRITICAL": "🔴", "HIGH": "🟠", "NORMAL": "🟢"}


def render_event(event, max_len=3800):
    emoji = _EMOJI.get(event["importance"], "🟢")
    head = f"{emoji} 펩트론 웹사이트 변경 감지"
    lines = [
        head, "",
        f"중요도: {event['importance']}",
        f"구분: {event['event_type_label']}",
        f"페이지 분류: {event['page_class']}",
        f"페이지: {event['target_label']}",
        f"발견 시각: {event['detected_at']}",
        f"사건 ID: {event['event_id']}",
    ]
    if event.get("title_before") or event.get("title_after"):
        lines += ["", f"이전 제목: {event['title_before']}",
                  f"변경 후 제목: {event['title_after']}"]

    added = event.get("added_lines", [])
    removed = event.get("removed_lines", [])
    body_lines = []
    if added:
        body_lines.append("\n추가:")
        body_lines += [f"+ {ln}" for ln in added]
    if removed:
        body_lines.append("\n삭제:")
        body_lines += [f"- {ln}" for ln in removed]

    tail = [""]
    tail.append(f"변경 비율: {event['change_ratio']}%")
    if event.get("keywords"):
        tail.append(f"관련 키워드: {', '.join(event['keywords'])}")
    tail += ["", "원문:", event["url"]]

    fixed = "\n".join(lines) + "\n" + "\n".join(tail)
    budget = max_len - len(fixed) - 40  # 잘림 안내 여유
    body = "\n".join(body_lines)
    if len(body) > budget > 0:
        kept, count = [], 0
        for ln in body_lines:
            if len("\n".join(kept + [ln])) > budget:
                break
            kept.append(ln)
            count += 1
        omitted = len(body_lines) - count
        body = "\n".join(kept) + f"\n…외 {omitted}줄 더 변경됨 (원문 확인)"

    msg = "\n".join(lines) + "\n" + body + "\n" + "\n".join(tail)
    if len(msg) > max_len:
        msg = msg[:max_len - 20].rstrip() + "\n…(잘림) 원문 확인"
    return msg


def render_startup(counts, now_str):
    parts = ", ".join(f"{k} {v}건" for k, v in counts.items())
    return (
        "🟢 펩트론 웹사이트 감시 시작\n\n"
        f"발견 시각: {now_str}\n"
        f"기준선 저장: {parts}\n\n"
        "이후 신규/수정/삭제가 감지되면 알림을 보냅니다."
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_render.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/render.py tests/test_render.py
git commit -m "feat: 텔레그램 메시지 렌더링 (길이 상한 잘림 포함)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 8: 상태 저장(state) + HTTP 페치(fetch)

**Files:**
- Create: `peptron_watch/state.py`
- Create: `peptron_watch/fetch.py`
- Test: `tests/test_state.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces (state):
  - `load_snapshot(state_dir: str, target_key: str) -> list[dict] | None` — 파일 없으면 `None`(baseline 신호), 있으면 항목 리스트
  - `save_snapshot(state_dir: str, target_key: str, items: list[dict]) -> None`
  - `load_health(state_dir: str) -> dict` / `save_health(state_dir: str, health: dict) -> None` — `{"consecutive_failures": int, "alerted": bool}`
- Produces (fetch):
  - `fetch_text(url: str, retries: int = 3, backoff: float = 2.0, sleep=time.sleep, session=None) -> str` — 200이 아니면 예외, 실패 시 지수 백오프 재시도. `sleep`/`session` 주입으로 테스트 가능

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_state.py`:
```python
from peptron_watch.state import (load_snapshot, save_snapshot,
                                  load_health, save_health)


def test_missing_snapshot_returns_none(tmp_path):
    assert load_snapshot(str(tmp_path), "ir_faq") is None


def test_save_then_load_roundtrip(tmp_path):
    items = [{"key": "a", "title": "t", "date": "", "text": "x",
              "url": "u", "extra": {}}]
    save_snapshot(str(tmp_path), "ir_faq", items)
    assert load_snapshot(str(tmp_path), "ir_faq") == items


def test_health_defaults_and_roundtrip(tmp_path):
    assert load_health(str(tmp_path)) == {"consecutive_failures": 0, "alerted": False}
    save_health(str(tmp_path), {"consecutive_failures": 3, "alerted": True})
    assert load_health(str(tmp_path))["consecutive_failures"] == 3
```

`tests/test_fetch.py`:
```python
import pytest
from peptron_watch.fetch import fetch_text


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text
        self.encoding = "utf-8"


class _Session:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_fetch_success_first_try():
    s = _Session([_Resp(200, "hello")])
    assert fetch_text("http://x", session=s, sleep=lambda _: None) == "hello"
    assert s.calls == 1


def test_fetch_retries_then_succeeds():
    s = _Session([_Resp(500), _Resp(200, "ok")])
    assert fetch_text("http://x", session=s, sleep=lambda _: None) == "ok"
    assert s.calls == 2


def test_fetch_raises_after_exhausting_retries():
    s = _Session([_Resp(500), _Resp(500), _Resp(500)])
    with pytest.raises(Exception):
        fetch_text("http://x", retries=3, session=s, sleep=lambda _: None)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_state.py tests/test_fetch.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 최소 구현 작성**

`peptron_watch/state.py`:
```python
import json
import os

_HEALTH_DEFAULT = {"consecutive_failures": 0, "alerted": False}


def _path(state_dir, name):
    return os.path.join(state_dir, name)


def load_snapshot(state_dir, target_key):
    p = _path(state_dir, f"{target_key}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(state_dir, target_key, items):
    os.makedirs(state_dir, exist_ok=True)
    p = _path(state_dir, f"{target_key}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def load_health(state_dir):
    p = _path(state_dir, "health.json")
    if not os.path.exists(p):
        return dict(_HEALTH_DEFAULT)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_health(state_dir, health):
    os.makedirs(state_dir, exist_ok=True)
    with open(_path(state_dir, "health.json"), "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)
```

`peptron_watch/fetch.py`:
```python
import time
import requests

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def fetch_text(url, retries=3, backoff=2.0, sleep=time.sleep, session=None):
    sess = session or requests.Session()
    last_err = None
    for attempt in range(retries):
        try:
            resp = sess.get(url, headers={"User-Agent": _UA}, timeout=30)
            if resp.status_code == 200:
                if getattr(resp, "encoding", None):
                    resp.encoding = "utf-8"
                return resp.text
            last_err = RuntimeError(f"HTTP {resp.status_code} for {url}")
        except Exception as e:  # 네트워크 예외 포함
            last_err = e
        if attempt < retries - 1:
            sleep(backoff * (2 ** attempt))
    raise last_err
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_state.py tests/test_fetch.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/state.py peptron_watch/fetch.py tests/test_state.py tests/test_fetch.py
git commit -m "feat: 스냅샷 저장소 + 재시도 HTTP 페치

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 9: 텔레그램 전송(notify)

**Files:**
- Create: `peptron_watch/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Produces:
  - `send_message(token: str, chat_id: str, text: str, retries: int = 3, sleep=time.sleep, poster=None) -> bool` — Telegram `sendMessage` 호출. `poster(url, data)->status_code` 주입으로 테스트. 200이면 True, 재시도 후에도 실패면 False(예외 아님 — 호출부가 스냅샷 미갱신으로 처리)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_notify.py`:
```python
from peptron_watch.notify import send_message


def test_send_success():
    calls = []

    def poster(url, data):
        calls.append((url, data))
        return 200

    assert send_message("TOK", "CID", "hi", poster=poster,
                        sleep=lambda _: None) is True
    assert "botTOK/sendMessage" in calls[0][0]
    assert calls[0][1]["chat_id"] == "CID"
    assert calls[0][1]["text"] == "hi"


def test_send_retries_then_fails():
    attempts = {"n": 0}

    def poster(url, data):
        attempts["n"] += 1
        return 500

    assert send_message("T", "C", "x", retries=3, poster=poster,
                        sleep=lambda _: None) is False
    assert attempts["n"] == 3
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_notify.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 최소 구현 작성**

`peptron_watch/notify.py`:
```python
import time
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _default_poster(url, data):
    resp = requests.post(url, data=data, timeout=30)
    return resp.status_code


def send_message(token, chat_id, text, retries=3, sleep=time.sleep, poster=None):
    poster = poster or _default_poster
    url = _API.format(token=token)
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    for attempt in range(retries):
        try:
            if poster(url, data) == 200:
                return True
        except Exception:
            pass
        if attempt < retries - 1:
            sleep(2.0 * (2 ** attempt))
    return False
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_notify.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add peptron_watch/notify.py tests/test_notify.py
git commit -m "feat: 텔레그램 전송 (재시도, 실패 시 False 반환)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 10: 설정 파일 + 오케스트레이션(main.py)

각 대상을 config대로 순회하며 fetch→extract→compare→enrich→render→notify→save를 엮는다. baseline·오류 알림·전송 실패 시 스냅샷 미갱신을 여기서 처리한다.

**Files:**
- Create: `watch_config.yaml`
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: 앞선 모든 모듈
- Produces:
  - `load_config(path: str) -> dict`
  - `extract_for(target: dict, fetcher) -> list[dict]` — `target["type"]`에 따라 알맞은 추출기 호출. `IR_ACTIVITY`는 목록의 각 id마다 `fetcher(detail_url)` 호출해 상세 병합. `fetcher(url)->str` 주입으로 테스트
  - `process_target(target, keywords, state_dir, fetcher, sender, now) -> list[dict]` — 한 대상 처리, 발송한 이벤트 리스트 반환. baseline이면 빈 리스트 반환하고 스냅샷만 저장. `sender(text)->bool` 실패 시 스냅샷 미갱신
  - `run(config, state_dir, fetcher, sender, now) -> None` — 전체 대상 순회 + health 갱신 + 오류 알림

- [ ] **Step 1: `watch_config.yaml` 작성**

```yaml
telegram:
  token_env: TELEGRAM_BOT_TOKEN
  chat_id_env: TELEGRAM_CHAT_ID

keywords:
  - 일라이릴리
  - 릴리
  - Lilly
  - 기술이전
  - 계약
  - 공동연구
  - SmartDepot
  - LUNA PHLEX
  - 임상
  - 승인
  - 마일스톤
  - 라이선스

targets:
  - key: ir_faq
    label: 자주묻는질문(FAQ)
    type: IR_FAQ
    page_class: IR
    url: https://peptron.irupsite.co.kr/Default2.aspx

  - key: ir_activity
    label: IR자료실
    type: IR_ACTIVITY
    page_class: IR
    url: https://peptron.irupsite.co.kr/Default2.aspx
    detail_url: https://peptron.irupsite.co.kr/IRActivity/Detail2AJAX.aspx?IRActivityID=

  - key: ir_disclosure
    label: 공시정보
    type: IR_TABLE
    section_id: section004
    page_class: DISCLOSURE
    url: https://peptron.irupsite.co.kr/Default2.aspx

  - key: ir_earning
    label: 경영공시
    type: IR_TABLE
    section_id: section001
    page_class: DISCLOSURE
    url: https://peptron.irupsite.co.kr/Default2.aspx

  - key: corp_news
    label: 펩트론 뉴스
    type: LINK_LIST
    id_param: "no"
    page_class: NEWS
    url: https://www.peptron.co.kr/ds4_1_1.html
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_main.py`:
```python
from datetime import datetime, timezone, timedelta
from pathlib import Path
import main as m

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 11, 14, 0, 0, tzinfo=KST)
FIX = Path(__file__).parent / "fixtures"
KW = ["SmartDepot"]


def _page_fetcher():
    page = (FIX / "ir_default2.html").read_text(encoding="utf-8")
    return lambda url: page


def test_extract_for_ir_faq():
    t = {"key": "ir_faq", "label": "FAQ", "type": "IR_FAQ",
         "page_class": "IR", "url": "https://peptron.irupsite.co.kr/Default2.aspx"}
    items = m.extract_for(t, _page_fetcher())
    assert items and items[0]["key"] == "자주묻는질문(FAQ)"


def test_baseline_saves_without_sending(tmp_path):
    sent = []
    t = {"key": "ir_faq", "label": "FAQ", "type": "IR_FAQ",
         "page_class": "IR", "url": "https://peptron.irupsite.co.kr/Default2.aspx"}
    events = m.process_target(t, KW, str(tmp_path), _page_fetcher(),
                              lambda text: sent.append(text) or True, NOW)
    assert events == []           # baseline: 알림 없음
    assert sent == []
    assert (tmp_path / "ir_faq.json").exists()


def test_second_run_no_change_sends_nothing(tmp_path):
    sent = []
    t = {"key": "ir_faq", "label": "FAQ", "type": "IR_FAQ",
         "page_class": "IR", "url": "https://peptron.irupsite.co.kr/Default2.aspx"}
    fetch = _page_fetcher()
    sender = lambda text: sent.append(text) or True
    m.process_target(t, KW, str(tmp_path), fetch, sender, NOW)  # baseline
    m.process_target(t, KW, str(tmp_path), fetch, sender, NOW)  # 변화 없음
    assert sent == []


def test_modification_triggers_send(tmp_path):
    sent = []
    t = {"key": "ir_faq", "label": "FAQ", "type": "IR_FAQ",
         "page_class": "IR", "url": "https://peptron.irupsite.co.kr/Default2.aspx"}
    page = (FIX / "ir_default2.html").read_text(encoding="utf-8")
    sender = lambda text: sent.append(text) or True
    m.process_target(t, KW, str(tmp_path), lambda u: page, sender, NOW)  # baseline
    changed = page.replace("일라이 릴리", "일라이 릴리(수정됨)", 1)
    m.process_target(t, KW, str(tmp_path), lambda u: changed, sender, NOW)
    assert len(sent) == 1
    assert "변경 감지" in sent[0]


def test_send_failure_keeps_old_snapshot(tmp_path):
    t = {"key": "ir_faq", "label": "FAQ", "type": "IR_FAQ",
         "page_class": "IR", "url": "https://peptron.irupsite.co.kr/Default2.aspx"}
    page = (FIX / "ir_default2.html").read_text(encoding="utf-8")
    m.process_target(t, KW, str(tmp_path), lambda u: page,
                     lambda text: True, NOW)  # baseline
    before = (tmp_path / "ir_faq.json").read_text(encoding="utf-8")
    changed = page.replace("일라이 릴리", "XYZ", 1)
    m.process_target(t, KW, str(tmp_path), lambda u: changed,
                     lambda text: False, NOW)  # 전송 실패
    after = (tmp_path / "ir_faq.json").read_text(encoding="utf-8")
    assert before == after   # 스냅샷 미갱신 → 다음 회차 재알림
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL (`ModuleNotFoundError: main` 또는 함수 없음)

- [ ] **Step 4: 최소 구현 작성**

`main.py`:
```python
import os
import sys
from datetime import datetime, timezone, timedelta

import yaml

from peptron_watch import extract, compare, enrich, render, state, fetch, notify

KST = timezone(timedelta(hours=9))
FAILURE_ALERT_THRESHOLD = 6  # 연속 6회(~30분) 실패 시 경고


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_for(target, fetcher):
    t = target["type"]
    url = target["url"]
    if t == "IR_FAQ":
        return extract.extract_ir_faq(fetcher(url), url)
    if t == "IR_TABLE":
        return extract.extract_ir_table(fetcher(url), target["section_id"], url)
    if t == "LINK_LIST":
        return extract.extract_link_list(
            fetcher(url), url, id_param=target.get("id_param", "no"))
    if t == "GENERIC_TEXT":
        return extract.extract_generic_text(fetcher(url), url)
    if t == "IR_ACTIVITY":
        listing = extract.extract_ir_activity_list(fetcher(url))
        items = []
        for entry in listing:
            detail = fetcher(target["detail_url"] + entry["id"])
            item = extract.parse_ir_activity_detail(detail, url)
            item["title"] = item["title"] or entry["title"]
            item["date"] = entry["date"]
            items.append(item)
        return items
    raise ValueError(f"Unknown target type: {t}")


def process_target(target, keywords, state_dir, fetcher, sender, now):
    items = extract_for(target, fetcher)
    old = state.load_snapshot(state_dir, target["key"])
    if old is None:  # baseline
        state.save_snapshot(state_dir, target["key"], items)
        return []
    tgt = {"key": target["key"], "label": target["label"],
           "page_class": target["page_class"], "url": target["url"]}
    events = compare.compare_items(old, items, tgt)
    if not events:
        return []
    enriched = [enrich.enrich_event(e, keywords, now=now) for e in events]
    order = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2}
    enriched.sort(key=lambda e: order.get(e["importance"], 3))
    all_sent = True
    for e in enriched:
        if not sender(render.render_event(e)):
            all_sent = False
    if all_sent:  # 전부 발송 성공했을 때만 스냅샷 갱신
        state.save_snapshot(state_dir, target["key"], items)
    return enriched


def run(config, state_dir, fetcher, sender, now=None):
    now = now or datetime.now(KST)
    keywords = config.get("keywords", [])
    health = state.load_health(state_dir)
    had_error = False
    is_first_run = not any(
        state.load_snapshot(state_dir, t["key"]) is not None
        for t in config["targets"])
    counts = {}
    for target in config["targets"]:
        try:
            events = process_target(target, keywords, state_dir, fetcher, sender, now)
            snap = state.load_snapshot(state_dir, target["key"]) or []
            counts[target["key"]] = len(snap)
            _ = events
        except Exception as e:
            had_error = True
            print(f"[error] {target['key']}: {e}", file=sys.stderr)
    if is_first_run:
        sender(render.render_startup(counts, now.strftime("%Y-%m-%d %H:%M:%S KST")))
    # health 갱신 + 오류 알림
    if had_error:
        health["consecutive_failures"] += 1
        if (health["consecutive_failures"] >= FAILURE_ALERT_THRESHOLD
                and not health["alerted"]):
            sender(f"⚠️ 펩트론 감시가 {health['consecutive_failures']}회 연속 실패 중입니다. 코드/사이트 점검이 필요합니다.")
            health["alerted"] = True
    else:
        health = {"consecutive_failures": 0, "alerted": False}
    state.save_health(state_dir, health)


def _cli():
    config = load_config(os.path.join(os.path.dirname(__file__), "watch_config.yaml"))
    state_dir = os.path.join(os.path.dirname(__file__), "state")
    dry = "--dry-run" in sys.argv
    fetcher = fetch.fetch_text
    if dry:
        def sender(text):
            print("----- (dry-run) 전송 안 함 -----\n" + text + "\n")
            return True
    else:
        token = os.environ[config["telegram"]["token_env"]]
        chat_id = os.environ[config["telegram"]["chat_id_env"]]
        def sender(text):
            return notify.send_message(token, chat_id, text)
    run(config, state_dir, fetcher, sender)


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 전체 테스트 실행**

Run: `python -m pytest -v`
Expected: 모든 테스트 PASS

- [ ] **Step 7: 커밋**

```bash
git add watch_config.yaml main.py tests/test_main.py
git commit -m "feat: 설정 로드 + 전체 오케스트레이션 (baseline/전송실패/오류알림)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

### Task 11: GitHub Actions 배포 + README + 실제 dry-run 검증

**Files:**
- Create: `.github/workflows/watch.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `main.py`, `watch_config.yaml`, Secrets `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`
- Produces: 배포 산출물 (테스트 대상 아님)

- [ ] **Step 1: 워크플로 작성**

`.github/workflows/watch.yml`:
```yaml
name: peptron-web-watch

on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:

concurrency:
  group: peptron-watch
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: python -m pip install -r requirements.txt

      - name: Run watcher
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py

      - name: Commit snapshot changes
        run: |
          git config user.name "peptron-watch-bot"
          git config user.email "actions@github.com"
          git add state/
          if git diff --cached --quiet; then
            echo "변경 없음 — 커밋 생략"
          else
            git commit -m "state: 스냅샷 갱신 ($(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M KST')) [skip ci]"
            git push
          fi
```

- [ ] **Step 2: README 작성**

`README.md`에 다음을 포함(단계별, 초보자 기준):
```markdown
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
```

- [ ] **Step 3: 실제 dry-run 검증**

Run: `python main.py --dry-run`
Expected: 두 사이트를 실제로 받아와 처리. 첫 실행이므로 "감시 시작" 메시지가 콘솔에 출력되고 `state/*.json`이 생성됨. 오류 스택트레이스 없음.

- [ ] **Step 4: 두 번째 dry-run으로 오탐 없음 확인**

Run: `python main.py --dry-run`
Expected: 변경 이벤트 메시지가 출력되지 않음(사이트가 그새 안 바뀌었다면). "감시 시작"도 다시 나오지 않음.

- [ ] **Step 5: 전체 테스트 최종 실행**

Run: `python -m pytest -v`
Expected: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add .github/workflows/watch.yml README.md
git commit -m "feat: GitHub Actions 5분 cron 배포 + README

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

- [ ] **Step 7: state 디렉토리를 gitignore에서 제외 확인**

`state/` 스냅샷은 커밋되어야 하므로 `.gitignore`에 없는지 확인. baseline 스냅샷을 최초 커밋한다:
```bash
git add state/
git commit -m "state: 초기 기준선 스냅샷

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FkDWhRjhAuXtf4L1tBcZjg"
```

---

## Self-Review

**1. Spec coverage:**
- §2.1 IR 섹션(FAQ/공시/경영공시/IR자료실) → Task 2, 3 ✓
- §2.2 본사 링크 목록 → Task 4 ✓
- §3 설정 파일·페이지 유형 → Task 10 (watch_config.yaml + extract_for) ✓
- §4 강화 필드(중요도/변경비율/키워드/사건ID) → Task 6 ✓
- §5 GitHub Actions 5분 public → Task 11 ✓
- §6 모듈 구조 → 전 Task ✓
- §7 정규화 → Task 1 ✓
- §8 흐름·baseline → Task 10 ✓
- §9 메시지 형식 → Task 7 ✓
- §10 오류 처리(재시도/연속실패/전송실패 미갱신) → Task 8, 9, 10 ✓
- §11 테스트 → 각 Task ✓
- §13 미공개 탐침 제외 → 설계상 목록 항목만 처리, Global Constraints 명시 ✓

**2. Placeholder scan:** 모든 코드 블록에 실제 구현·실제 테스트 포함. "TBD"/"적절한 처리" 없음 ✓

**3. Type consistency:** 항목 dict(`key/title/date/text/url/extra`)와 이벤트 dict 키가 Task 5~10에서 일관. `fetch_text`/`send_message`/`extract_*` 시그니처가 Task 10 `extract_for`·`_cli`에서 동일하게 사용됨 ✓

**참고 — 사이트 구조 관찰**: 본사 뉴스 링크 식별자는 `no=`, IR자료실은 `IRActivityID`, 공시는 표 행 텍스트. `page` 등 휘발성 쿼리는 key에서 배제(Task 4)해 페이지네이션 오탐을 막음.

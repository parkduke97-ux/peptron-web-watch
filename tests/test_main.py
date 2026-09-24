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
    assert items and items[0]["key"] == "자주묻는질문(FAQ)|2026-09-11"


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


def test_reorder_sends_once_then_stays_quiet(tmp_path):
    sent = []
    t = {"key": "corp_news", "label": "펩트론 뉴스", "type": "LINK_LIST",
         "page_class": "NEWS", "url": "https://www.peptron.co.kr/ds4_1_1.html"}
    sender = lambda text: sent.append(text) or True
    before = '<a href="?no=3">셋</a><a href="?no=2">둘</a><a href="?no=1">하나</a>'
    after = '<a href="?no=1">하나</a><a href="?no=3">셋</a><a href="?no=2">둘</a>'
    m.process_target(t, KW, str(tmp_path), lambda u: before, sender, NOW)  # baseline
    m.process_target(t, KW, str(tmp_path), lambda u: after, sender, NOW)
    m.process_target(t, KW, str(tmp_path), lambda u: after, sender, NOW)
    assert len(sent) == 1
    assert "게시물 순서 변경" in sent[0]
    assert "하나: 3번째 → 1번째" in sent[0]


def test_run_fetches_each_url_once_per_cycle(tmp_path):
    page = (FIX / "ir_default2.html").read_text(encoding="utf-8")
    url = "https://peptron.irupsite.co.kr/Default2.aspx"
    config = {"keywords": [], "targets": [
        {"key": "ir_faq", "label": "FAQ", "type": "IR_FAQ", "page_class": "IR", "url": url},
        {"key": "ir_disclosure", "label": "공시정보", "type": "IR_TABLE",
         "section_id": "section004", "page_class": "DISCLOSURE", "url": url},
    ]}
    calls = []
    fetcher = lambda u: calls.append(u) or page
    m.run(config, str(tmp_path), fetcher, lambda text: True, now=NOW)
    m.run(config, str(tmp_path), fetcher, lambda text: True, now=NOW)
    assert calls == [url, url]  # 주기마다 1번씩


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

from pathlib import Path

from peptron_watch.compare import compare_items
from peptron_watch.extract import extract_ir_faq

TARGET = {"key": "ir_faq", "label": "FAQ", "page_class": "IR",
          "url": "https://x/#s"}

FIX = Path(__file__).parent / "fixtures"
BASE = "https://peptron.irupsite.co.kr/Default2.aspx"


def _real_faq_items():
    page = (FIX / "ir_default2.html").read_text(encoding="utf-8")
    return extract_ir_faq(page, BASE)


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


# --- Regression: real IR FAQ page, newest-first prepend must not spuriously
# --- MODIFY every same-titled entry (the fix is a unique key = title|date
# --- in extract_ir_faq, not positional pairing in compare_items).

def test_real_faq_prepend_yields_single_new_no_spurious_modified():
    old = _real_faq_items()
    # The site renders newest-first: a new posting is PREPENDED at index 0,
    # not appended. Same title as the current first entry, brand-new date.
    new_entry = dict(old[0])
    new_entry["date"] = "2026-09-12"
    new_entry["key"] = f"{new_entry['title']}|{new_entry['date']}"
    new_entry["text"] = new_entry["text"] + "\n신규 공지 문구"
    new = [new_entry] + old

    events = compare_items(old, new, TARGET)
    assert len(events) == 1
    assert events[0]["kind"] == "NEW"
    assert events[0]["item_key"] == new_entry["key"]
    assert all(e["kind"] != "MODIFIED" for e in events)


def test_real_faq_body_edit_yields_single_modified_for_that_entry():
    old = _real_faq_items()
    new = [dict(it) for it in old]
    target_idx = 0
    edited = new[target_idx]
    edited["text"] = edited["text"].replace("일라이 릴리", "일라이 릴리(수정됨)", 1)
    assert edited["text"] != old[target_idx]["text"]

    events = compare_items(old, new, TARGET)
    assert len(events) == 1
    assert events[0]["kind"] == "MODIFIED"
    assert events[0]["item_key"] == old[target_idx]["key"]

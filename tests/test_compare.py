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

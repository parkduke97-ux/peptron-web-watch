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


def test_reorder_is_critical_with_label_ratio_and_keywords():
    moved = ["릴리 기술이전 안내: 4번째 → 1번째"]
    e = enrich_event(_base(kind="REORDERED", item_key="__order__", moved_lines=moved,
                           text_before="a\nb\nc\nd", text_after="d\na\nb\nc"), KW, now=NOW)
    assert e["importance"] == "CRITICAL"
    assert e["event_type_label"] == "고정 공지·게시물 순서 변경"
    assert 0 < e["change_ratio"] < 100
    assert "릴리" in e["keywords"]
    other = enrich_event(_base(kind="REORDERED", item_key="__order__",
                               moved_lines=["다른 글: 2번째 → 1번째"]), KW, now=NOW)
    assert e["event_id"] != other["event_id"]


def test_event_id_stable_for_same_change():
    a = enrich_event(_base(added_lines=["x"]), KW, now=NOW)
    b = enrich_event(_base(added_lines=["x"]), KW, now=NOW)
    assert a["event_id"] == b["event_id"]

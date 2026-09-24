import difflib
import hashlib
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

_TYPE_LABEL = {"NEW": "신규 게시글", "MODIFIED": "기존 게시글 수정", "REMOVED": "게시글 삭제",
               "REORDERED": "고정 공지·게시물 순서 변경"}


def _change_lines(event):
    return (event.get("added_lines", []) + event.get("removed_lines", [])
            + event.get("moved_lines", []))


def _matched_keywords(event, keywords):
    haystack = "\n".join(
        _change_lines(event) + [event.get("title", ""), event.get("title_after", "")]
    ).lower()
    return [kw for kw in keywords if kw.lower() in haystack]


def _importance(event, matched):
    if matched:
        return "CRITICAL"
    if event["kind"] in ("REMOVED", "REORDERED"):
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
    seed = event["target_key"] + event["item_key"] + "\n".join(_change_lines(event))
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

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

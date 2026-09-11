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
    # Group by key (not a plain dict) because some extractors legitimately
    # produce multiple items that share the same "key" (e.g. IR FAQ entries
    # whose title is a repeated generic label). A plain {key: item} dict
    # would silently collapse those into the last one seen, and a real
    # change to an earlier duplicate-keyed item would go undetected. Items
    # sharing a key are paired up positionally (occurrence order preserved
    # from the source list) instead.
    old_groups = {}
    for it in old_items:
        old_groups.setdefault(it["key"], []).append(it)
    new_groups = {}
    for it in new_items:
        new_groups.setdefault(it["key"], []).append(it)

    events = []
    for key, news in new_groups.items():
        olds = old_groups.get(key, [])
        for i, item in enumerate(news):
            if i >= len(olds):
                events.append(_event(target, "NEW", item))
                continue
            old_item = olds[i]
            if item["text"] != old_item["text"]:
                added, removed = _diff_lines(old_item["text"], item["text"])
                ev = _event(
                    target, "MODIFIED", item,
                    added_lines=added, removed_lines=removed,
                    text_before=old_item["text"], text_after=item["text"],
                )
                if old_item.get("title", "") != item.get("title", ""):
                    ev["title_before"] = old_item.get("title", "")
                    ev["title_after"] = item.get("title", "")
                if old_item.get("date", "") != item.get("date", ""):
                    ev["date_before"] = old_item.get("date", "")
                    ev["date_after"] = item.get("date", "")
                events.append(ev)
    for key, olds in old_groups.items():
        news = new_groups.get(key, [])
        for i, old_item in enumerate(olds):
            if i >= len(news):
                events.append(_event(target, "REMOVED", old_item))
    return events

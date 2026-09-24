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


def _reorder_event(old_items, new_items, target):
    old_seq = [it["key"] for it in old_items]
    new_seq = [it["key"] for it in new_items]
    common = set(old_seq) & set(new_seq)
    old_seq = [k for k in old_seq if k in common]
    new_seq = [k for k in new_seq if k in common]
    if old_seq == new_seq:
        return None
    # 최장 공통 순서에 남은 글은 제자리로 보고 나머지만 "이동"으로 알린다 (덩달아 밀린 글 제외)
    sm = difflib.SequenceMatcher(None, old_seq, new_seq, autojunk=False)
    kept = {k for _, b, n in sm.get_matching_blocks() for k in new_seq[b:b + n]}
    old_pos = {it["key"]: i + 1 for i, it in enumerate(old_items)}
    new_by_key = {it["key"]: (i + 1, it) for i, it in enumerate(new_items)}
    moved_lines = []
    for k in new_seq:
        if k in kept:
            continue
        pos, item = new_by_key[k]
        title = " ".join((item.get("title") or k).split())
        moved_lines.append(f"{title}: {old_pos[k]}번째 → {pos}번째")
    return _event(target, "REORDERED", {"key": "__order__"},
                  moved_lines=moved_lines,
                  text_before="\n".join(old_seq), text_after="\n".join(new_seq))


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
    reorder = _reorder_event(old_items, new_items, target)
    if reorder:
        events.append(reorder)
    return events

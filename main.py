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
    pages = {}  # 여러 대상이 같은 IR 페이지(약 300KB)를 쓰므로 주기 안에서는 한 번만 받는다

    def cached_fetch(url):
        if url not in pages:
            pages[url] = fetcher(url)
        return pages[url]

    for target in config["targets"]:
        try:
            events = process_target(target, keywords, state_dir, cached_fetch, sender, now)
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
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
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

_EMOJI = {"CRITICAL": "🔴", "HIGH": "🟠", "NORMAL": "🟢"}


def render_event(event, max_len=3800):
    if event["kind"] == "REORDERED":
        head = "⚠️ 펩트론 홈페이지 게시물 순서 변경"
    else:
        head = f"{_EMOJI.get(event['importance'], '🟢')} 펩트론 웹사이트 변경 감지"
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
    moved = event.get("moved_lines", [])
    body_lines = []
    if moved:
        body_lines.append("\n이동한 게시물:")
        body_lines += [f"• {ln}" for ln in moved]
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

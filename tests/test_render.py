from peptron_watch.render import render_event, render_startup


def _ev(**kw):
    e = {"target_label": "자주묻는질문(FAQ)", "page_class": "IR", "url": "https://x/#s",
         "kind": "MODIFIED", "importance": "CRITICAL",
         "event_type_label": "기존 게시글 수정", "item_key": "a",
         "title": "자주묻는질문(FAQ)", "title_before": "", "title_after": "",
         "added_lines": ["+추가된 문장"], "removed_lines": ["-삭제된 문장"],
         "change_ratio": 3.3, "keywords": ["SmartDepot"],
         "event_id": "EVT-5C3DB3A783", "detected_at": "2026-09-11 14:09:14 KST"}
    e.update(kw)
    return e


def test_render_contains_core_fields():
    msg = render_event(_ev())
    assert "중요도: CRITICAL" in msg
    assert "구분: 기존 게시글 수정" in msg
    assert "페이지 분류: IR" in msg
    assert "사건 ID: EVT-5C3DB3A783" in msg
    assert "변경 비율: 3.3%" in msg
    assert "관련 키워드: SmartDepot" in msg
    assert "https://x/#s" in msg
    assert "추가된 문장" in msg and "삭제된 문장" in msg


def test_render_truncates_long_diff():
    big = [f"라인 {i}" for i in range(1000)]
    msg = render_event(_ev(added_lines=big), max_len=1000)
    assert len(msg) <= 1000
    assert "외" in msg and "더 변경" in msg


def test_render_shows_title_change():
    msg = render_event(_ev(title_before="옛 제목", title_after="새 제목"))
    assert "이전 제목: 옛 제목" in msg
    assert "변경 후 제목: 새 제목" in msg


def test_render_no_keyword_line_when_empty():
    msg = render_event(_ev(keywords=[]))
    assert "관련 키워드" not in msg


def test_render_reorder_shows_header_and_moved_items():
    msg = render_event(_ev(kind="REORDERED", event_type_label="고정 공지·게시물 순서 변경",
                           added_lines=[], removed_lines=[],
                           moved_lines=["고정 공지: 4번째 → 1번째"]))
    assert msg.splitlines()[0] == "⚠️ 펩트론 홈페이지 게시물 순서 변경"
    assert "구분: 고정 공지·게시물 순서 변경" in msg
    assert "이동한 게시물:" in msg
    assert "• 고정 공지: 4번째 → 1번째" in msg


def test_render_startup():
    msg = render_startup({"ir_faq": 1, "corp_news": 20}, "2026-09-11 14:00:00 KST")
    assert "감시" in msg and "ir_faq" in msg and "20" in msg

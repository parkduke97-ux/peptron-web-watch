from pathlib import Path
from peptron_watch.extract import extract_ir_activity_list, parse_ir_activity_detail

FIX = Path(__file__).parent / "fixtures"
BASE = "https://peptron.irupsite.co.kr/Default2.aspx"


def test_extract_activity_list_finds_ids():
    page = (FIX / "ir_default2.html").read_text(encoding="utf-8")
    items = extract_ir_activity_list(page)
    ids = {it["id"] for it in items}
    assert "246" in ids and "244" in ids
    it246 = next(it for it in items if it["id"] == "246")
    assert "CPHI Milan 2026" in it246["title"]
    assert it246["date"] == "2026-09-09"


def test_parse_activity_detail_extracts_body_and_flags():
    raw = (FIX / "ir_activity_246.json").read_text(encoding="utf-8")
    item = parse_ir_activity_detail(raw, BASE)
    assert item["key"] == "246"
    assert "CPHI Milan 2026" in item["text"]
    assert item["extra"]["DeleteFlag"] == "N"
    assert "RegisterDate" in item["extra"]
    assert item["url"].endswith("#section009")


def test_parse_activity_detail_body_change_changes_text():
    raw = (FIX / "ir_activity_246.json").read_text(encoding="utf-8")
    modified = raw.replace("CPHI Milan 2026", "CPHI Milan 2027")
    assert parse_ir_activity_detail(raw, BASE)["text"] != \
        parse_ir_activity_detail(modified, BASE)["text"]

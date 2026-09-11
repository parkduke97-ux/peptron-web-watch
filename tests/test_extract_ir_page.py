from pathlib import Path
from peptron_watch.extract import extract_ir_faq, extract_ir_table

FIX = Path(__file__).parent / "fixtures"
BASE = "https://peptron.irupsite.co.kr/Default2.aspx"


def _page():
    return (FIX / "ir_default2.html").read_text(encoding="utf-8")


def test_extract_ir_faq_returns_items_with_body():
    items = extract_ir_faq(_page(), BASE)
    assert len(items) >= 1
    faq = items[0]
    assert faq["key"] == "자주묻는질문(FAQ)"
    assert faq["date"] == "2026-09-11"
    # 본문에 실제 Q 문항이 들어 있어야 함
    assert "일라이 릴리" in faq["text"]
    assert faq["url"].endswith("#section007")


def test_extract_ir_table_disclosure_has_rows():
    items = extract_ir_table(_page(), "section004", BASE)
    assert len(items) >= 1
    assert all(it["key"] for it in items)
    assert items[0]["url"].endswith("#section004")


def test_extract_ir_faq_stable_across_calls():
    # 같은 입력 두 번 → 완전히 동일한 결과(오탐 방지)
    assert extract_ir_faq(_page(), BASE) == extract_ir_faq(_page(), BASE)

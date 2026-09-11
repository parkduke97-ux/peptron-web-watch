from pathlib import Path
from peptron_watch.extract import extract_link_list, extract_generic_text

FIX = Path(__file__).parent / "fixtures"
CORP = "https://www.peptron.co.kr/ds4_1_1.html"


def test_extract_link_list_uses_no_param_as_key():
    html = (FIX / "corp_news_list.html").read_text(encoding="utf-8", errors="replace")
    items = extract_link_list(html, CORP, id_param="no")
    keys = {it["key"] for it in items}
    assert "no=115" in keys
    # 각 key는 유일해야 함(page 파라미터가 달라도 중복 아님)
    assert len(keys) == len(items)


def test_extract_link_list_titles_are_real_korean_not_mojibake():
    # 회귀 테스트: apparent_encoding(예: MacCyrillic) 추측으로 되돌아가면
    # 실패해야 한다. 이 사이트는 utf-8 바이트를 보내므로 utf-8로 디코딩해야
    # 한글이 깨지지 않는다.
    html = (FIX / "corp_news_list.html").read_text(encoding="utf-8", errors="replace")
    items = extract_link_list(html, CORP, id_param="no")
    assert any("오송바이오파크" in it["title"] for it in items)


def test_link_list_ignores_volatile_page_param():
    html = '<a href="?db=newsp&no=50&c=view&page=1">A</a>' \
           '<a href="?db=newsp&no=50&c=view&page=2">A</a>'
    items = extract_link_list(html, CORP, id_param="no")
    assert len(items) == 1
    assert items[0]["key"] == "no=50"


def test_generic_text_single_item():
    html = "<html><body><p>본문 한 줄.</p></body></html>"
    items = extract_generic_text(html, CORP)
    assert len(items) == 1
    assert items[0]["key"] == "page"
    assert "본문 한 줄." in items[0]["text"]

from peptron_watch.normalize import normalize_text, html_to_text


def test_normalize_collapses_whitespace_and_blank_lines():
    raw = "  Q1.  질문   내용  \n\n\n\n  A1. 답변 \n"
    assert normalize_text(raw) == "Q1. 질문 내용\n\nA1. 답변"


def test_html_to_text_strips_tags_and_editor_attrs():
    html = (
        '<h3 data-start="128" data-section-id="4ybbmx">제목</h3>'
        '<p>첫 문장.</p><p>둘째 문장.</p>'
    )
    assert html_to_text(html) == "제목\n첫 문장.\n둘째 문장."


def test_html_to_text_removes_scripts_and_decodes_entities():
    html = "<script>var x=1;</script><p>A&nbsp;B &amp; C</p>"
    assert html_to_text(html) == "A B & C"


def test_only_editor_attr_change_yields_identical_text():
    # 편집기가 data-start 값만 바꿔 저장한 경우 → 동일 텍스트여야 함(오탐 방지)
    a = '<p data-start="10" data-end="20">동일한 문장입니다.</p>'
    b = '<p data-start="99" data-end="105">동일한 문장입니다.</p>'
    assert html_to_text(a) == html_to_text(b)

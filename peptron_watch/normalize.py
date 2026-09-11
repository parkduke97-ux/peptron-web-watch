import re
import html as _html


def normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t　\xa0]+", " ", ln).strip() for ln in text.split("\n")]
    # 연속 빈 줄을 최대 1개로 압축
    out = []
    for ln in lines:
        if ln == "" and out and out[-1] == "":
            continue
        out.append(ln)
    return "\n".join(out).strip()


def html_to_text(html: str) -> str:
    # script/style 제거
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", html)
    # 블록 경계 → 줄바꿈
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|li|div|h[1-6]|tr)>", "\n", html)
    # 나머지 태그 제거
    html = re.sub(r"(?s)<[^>]+>", "", html)
    # 엔티티 디코드
    html = _html.unescape(html)
    return normalize_text(html)

import json
import re
from bs4 import BeautifulSoup
from .normalize import html_to_text, normalize_text


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


_POPOPEN_RE = re.compile(
    r"popOpen\(\s*'[^']*'\s*,\s*'((?:[^'\\]|\\.)*)\s*'\s*,\s*'([^']*)'"
    r"(?:\s*,\s*'[^']*'){3}\s*,\s*'(\d+)'"
)


def extract_ir_faq(page_html: str, base_url: str) -> list[dict]:
    soup = _soup(page_html)
    section = soup.select_one("#section007")
    items = []
    if not section:
        return items
    for li in section.select(".faq-list li"):
        tit_el = li.select_one(".tit")
        date_el = li.select_one(".date")
        body_el = li.select_one(".target")
        title = normalize_text(tit_el.get_text()) if tit_el else ""
        date = normalize_text(date_el.get_text()) if date_el else ""
        body = html_to_text(str(body_el)) if body_el else ""
        text = normalize_text(f"{title}\n{body}")
        items.append({
            "key": title, "title": title, "date": date,
            "text": text, "url": base_url + "#section007", "extra": {},
        })
    return items


def extract_ir_table(page_html: str, section_id: str, base_url: str) -> list[dict]:
    soup = _soup(page_html)
    section = soup.select_one(f"#{section_id}")
    items = []
    if not section:
        return items
    for tr in section.select("tbody tr"):
        cells = [normalize_text(td.get_text()) for td in tr.find_all("td")]
        if not cells:
            continue
        title = cells[0]
        date = cells[-1] if len(cells) > 1 else ""
        text = " | ".join(cells)
        items.append({
            "key": text, "title": title, "date": date,
            "text": text, "url": base_url + "#" + section_id, "extra": {},
        })
    return items


def extract_ir_activity_list(page_html: str) -> list[dict]:
    soup = _soup(page_html)
    section = soup.select_one("#section009")
    items = []
    if not section:
        return items
    for a in section.select("a[href^='javascript:popOpen']"):
        m = _POPOPEN_RE.search(a.get("href", ""))
        if not m:
            continue
        title, date, act_id = m.group(1), m.group(2), m.group(3)
        items.append({"id": act_id, "title": title.replace("\\'", "'"), "date": date})
    return items


def parse_ir_activity_detail(json_text: str, base_url: str) -> dict:
    d = json.loads(json_text)
    subject = d.get("Subject") or ""
    body = html_to_text(d.get("Description") or "")
    flags = {
        "DeleteFlag": d.get("DeleteFlag"),
        "MainFlag": d.get("MainFlag"),
        "FileName": d.get("FileName") or "",
        "RegisterDate": d.get("RegisterDate"),
    }
    flag_text = "\n".join(f"{k}={v}" for k, v in sorted(flags.items()))
    text = normalize_text(f"{subject}\n{body}\n{flag_text}")
    return {
        "key": str(d.get("IRActivityID")),
        "title": subject,
        "date": "",
        "text": text,
        "url": base_url + "#section009",
        "extra": flags,
    }

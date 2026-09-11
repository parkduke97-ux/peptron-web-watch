import time
import requests

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def fetch_text(url, retries=3, backoff=2.0, sleep=time.sleep, session=None):
    sess = session or requests.Session()
    last_err = None
    for attempt in range(retries):
        try:
            resp = sess.get(url, headers={"User-Agent": _UA}, timeout=30)
            if resp.status_code == 200:
                # Force utf-8 decoding (the HTTP header charset both target sites
                # send, even when a page's stale <meta> tag claims euc-kr).
                # Do NOT use resp.apparent_encoding here: for www.peptron.co.kr it
                # guesses "MacCyrillic" (a single-byte codec that never raises),
                # which silently decodes valid UTF-8 bytes into mojibake instead
                # of failing loudly.
                resp.encoding = "utf-8"
                return resp.text
            last_err = RuntimeError(f"HTTP {resp.status_code} for {url}")
        except Exception as e:  # 네트워크 예외 포함
            last_err = e
        if attempt < retries - 1:
            sleep(backoff * (2 ** attempt))
    raise last_err

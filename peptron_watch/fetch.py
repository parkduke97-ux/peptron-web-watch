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
                # Use apparent_encoding if available (for detecting euc-kr vs utf-8),
                # otherwise fall back to resp.encoding. This keeps the brief's tests
                # passing (their fake _Resp has no apparent_encoding, so getattr -> None)
                # while correctly handling real sites like www.peptron.co.kr (euc-kr).
                enc = getattr(resp, "apparent_encoding", None) or resp.encoding
                if enc:
                    resp.encoding = enc
                return resp.text
            last_err = RuntimeError(f"HTTP {resp.status_code} for {url}")
        except Exception as e:  # 네트워크 예외 포함
            last_err = e
        if attempt < retries - 1:
            sleep(backoff * (2 ** attempt))
    raise last_err

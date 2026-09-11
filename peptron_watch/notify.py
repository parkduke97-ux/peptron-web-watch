import time
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _default_poster(url, data):
    resp = requests.post(url, data=data, timeout=30)
    return resp.status_code


def send_message(token, chat_id, text, retries=3, sleep=time.sleep, poster=None):
    poster = poster or _default_poster
    url = _API.format(token=token)
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    for attempt in range(retries):
        try:
            if poster(url, data) == 200:
                return True
        except Exception:
            pass
        if attempt < retries - 1:
            sleep(2.0 * (2 ** attempt))
    return False

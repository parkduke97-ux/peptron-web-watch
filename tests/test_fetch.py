import pytest
from peptron_watch.fetch import fetch_text


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text
        self.encoding = "utf-8"


class _Session:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_fetch_success_first_try():
    s = _Session([_Resp(200, "hello")])
    assert fetch_text("http://x", session=s, sleep=lambda _: None) == "hello"
    assert s.calls == 1


def test_fetch_retries_then_succeeds():
    s = _Session([_Resp(500), _Resp(200, "ok")])
    assert fetch_text("http://x", session=s, sleep=lambda _: None) == "ok"
    assert s.calls == 2


def test_fetch_raises_after_exhausting_retries():
    s = _Session([_Resp(500), _Resp(500), _Resp(500)])
    with pytest.raises(Exception):
        fetch_text("http://x", retries=3, session=s, sleep=lambda _: None)

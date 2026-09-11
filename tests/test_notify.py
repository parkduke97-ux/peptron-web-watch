from peptron_watch.notify import send_message


def test_send_success():
    calls = []

    def poster(url, data):
        calls.append((url, data))
        return 200

    assert send_message("TOK", "CID", "hi", poster=poster,
                        sleep=lambda _: None) is True
    assert "botTOK/sendMessage" in calls[0][0]
    assert calls[0][1]["chat_id"] == "CID"
    assert calls[0][1]["text"] == "hi"


def test_send_retries_then_fails():
    attempts = {"n": 0}

    def poster(url, data):
        attempts["n"] += 1
        return 500

    assert send_message("T", "C", "x", retries=3, poster=poster,
                        sleep=lambda _: None) is False
    assert attempts["n"] == 3

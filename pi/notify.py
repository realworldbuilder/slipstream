"""Telegram alerts.

Settings live in /etc/slipstream/telegram, two lines written by `slipstream-alerts setup`:

    token=123456:ABC...
    chat_id=987654321

No file means alerts are off. The file is read on every call so turning alerts on or off
needs no restart. Sending never raises: a dead network must not break watch mode.
"""
import json
import os
import sys
import threading
import urllib.request
import uuid

FILE = os.environ.get("SLIPSTREAM_TELEGRAM_FILE", "/etc/slipstream/telegram")
API = "https://api.telegram.org/bot{token}/{method}"


def settings():
    try:
        with open(FILE) as f:
            kv = dict(line.strip().split("=", 1) for line in f if "=" in line)
    except OSError:
        return None
    return kv if kv.get("token") and kv.get("chat_id") else None


def configured():
    return settings() is not None


def send_photo(jpg, caption):
    """Posts one JPEG with a caption. Returns True when Telegram accepted it."""
    s = settings()
    if not s:
        return False
    boundary = uuid.uuid4().hex
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{s["chat_id"]}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="slipstream.jpg"\r\n'
        f'Content-Type: image/jpeg\r\n\r\n'.encode(), jpg, b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        API.format(token=s["token"], method="sendPhoto"), data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return bool(json.load(r).get("ok"))
    except Exception as e:
        print(f"telegram: {e}", file=sys.stderr, flush=True)
        return False


def alert(jpg, caption):
    """send_photo in the background, so the caller never waits on the network."""
    threading.Thread(target=send_photo, args=(jpg, caption), daemon=True).start()

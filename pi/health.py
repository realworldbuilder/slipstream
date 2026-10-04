#!/usr/bin/env python3
"""Slipstream control service: health, stills and mode switching.

GET  /              control page
GET  /health        JSON status; 200 when the stream is up, 503 otherwise
GET  /still.jpg     one frame grabbed from the running stream
GET  /mode          current mode and the available modes
POST /mode/<name>   switch mode
GET  /captures      recent snapshots saved by watch and timelapse

Every route needs the login (HTTP Basic), except for requests from the Pi itself.
"""
import base64
import hmac
import json
import os
import re
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import modes

PORT = 8080
CAMERA = "/dev/v4l/by-id/usb-046d_C270_HD_WEBCAM_BCED6B80-video-index0"
MTX_API = "http://127.0.0.1:9997/v3/paths/get/cam"
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "control.html")
CAPTURE_PATH = re.compile(r"^/captures/(watch|timelapse)/(\d{8}-\d{6}\.jpg)$")
USER = "slipstream"
PASSWORD_FILE = os.environ.get("SLIPSTREAM_PASSWORD_FILE", "/etc/slipstream/password")

# Written by install.sh. Without it the service does not start, rather than run open.
with open(PASSWORD_FILE) as f:
    LOGIN = base64.b64encode(f"{USER}:{f.read().strip()}".encode()).decode()

mode = modes.Modes()


def stream_ready():
    try:
        with urllib.request.urlopen(MTX_API, timeout=2) as r:
            return bool(json.load(r).get("ready"))
    except Exception:
        return False


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000, 1)
    except OSError:
        return None


def uptime():
    with open("/proc/uptime") as f:
        return int(float(f.read().split()[0]))


def mode_info():
    return {"mode": mode.current, "modes": {n: fn.__doc__ for n, fn in modes.MODES.items()}}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, "application/json", json.dumps(obj).encode())

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                self._send(200, ctype, f.read())
        except OSError:
            self._send(404, "text/plain", b"not found\n")

    def _authorized(self):
        if self.client_address[0] in ("127.0.0.1", "::1"):
            return True
        scheme, _, given = self.headers.get("Authorization", "").partition(" ")
        if scheme.lower() == "basic" and hmac.compare_digest(given.strip().encode(), LOGIN.encode()):
            return True
        body = b"password required\n"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Slipstream"')
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def do_GET(self):
        if not self._authorized():
            return
        capture = CAPTURE_PATH.match(self.path)
        if self.path == "/":
            self._file(PAGE, "text/html; charset=utf-8")
        elif self.path == "/health":
            ready = stream_ready()
            self._json(200 if ready else 503, {
                "ok": ready,
                "host": os.uname().nodename,
                "time": int(time.time()),
                "uptime_s": uptime(),
                "cpu_temp_c": cpu_temp(),
                "camera_present": os.path.exists(CAMERA),
                "stream_ready": ready,
                "mode": mode.current,
            })
        elif self.path == "/still.jpg":
            try:
                jpg = modes.grab_still()
            except subprocess.TimeoutExpired:
                jpg = None
            if jpg:
                self._send(200, "image/jpeg", jpg)
            else:
                self._send(503, "text/plain", b"stream not available\n")
        elif self.path == "/mode":
            self._json(200, mode_info())
        elif self.path == "/captures":
            self._json(200, modes.recent_captures())
        elif capture:
            self._file(os.path.join(modes.CAPTURES, *capture.groups()), "image/jpeg")
        else:
            self._send(404, "text/plain", b"not found\n")

    def do_POST(self):
        if not self._authorized():
            return
        if self.path.startswith("/mode/") and mode.set(self.path[len("/mode/"):]):
            self._json(200, mode_info())
        else:
            self._send(404, "text/plain", b"not found\n")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()

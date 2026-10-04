#!/usr/bin/env python3
"""Slipstream health and still-capture endpoint.

GET /health     JSON status; 200 when the stream is up, 503 otherwise
GET /still.jpg  one frame grabbed from the running stream
"""
import json
import os
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8080
CAMERA = "/dev/v4l/by-id/usb-046d_C270_HD_WEBCAM_BCED6B80-video-index0"
STREAM = "rtsp://127.0.0.1:8554/cam"
MTX_API = "http://127.0.0.1:9997/v3/paths/get/cam"


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


def grab_still():
    # Read from the stream so the camera is never opened a second time.
    r = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-rtsp_transport", "tcp", "-i", STREAM,
         "-frames:v", "1", "-q:v", "2", "-f", "image2", "-"],
        capture_output=True, timeout=15,
    )
    return r.stdout if r.returncode == 0 and r.stdout else None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            ready = stream_ready()
            body = json.dumps({
                "ok": ready,
                "host": os.uname().nodename,
                "time": int(time.time()),
                "uptime_s": uptime(),
                "cpu_temp_c": cpu_temp(),
                "camera_present": os.path.exists(CAMERA),
                "stream_ready": ready,
            }).encode()
            self._send(200 if ready else 503, "application/json", body)
        elif self.path == "/still.jpg":
            try:
                jpg = grab_still()
            except subprocess.TimeoutExpired:
                jpg = None
            if jpg:
                self._send(200, "image/jpeg", jpg)
            else:
                self._send(503, "text/plain", b"stream not available\n")
        else:
            self._send(404, "text/plain", b"not found\n")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()

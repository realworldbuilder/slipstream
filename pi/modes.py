"""Slipstream modes.

The camera stream always runs. A mode decides what else runs on top of it.
Each mode is one function below; its docstring is the description shown on
the control page.
"""
import os
import subprocess
import threading
import time

import notify

STREAM = "rtsp://127.0.0.1:8554/cam"
STATE = os.environ.get("SLIPSTREAM_STATE", "/var/lib/slipstream")
MODE_FILE = os.path.join(STATE, "mode")
CAPTURES = os.path.join(STATE, "captures")
# Scratch frame for watch mode. On tmpfs so it never wears the SD card.
LATEST = "/dev/shm/slipstream-latest.jpg"

TIMELAPSE_INTERVAL_S = 60
WATCH_QUIET_S = 10             # this long with no motion ends a motion event
WATCH_SIZE = (160, 90)         # motion is judged on a small greyscale copy
WATCH_PIXEL_DELTA = 25         # how far a pixel must change to count (0-255)
WATCH_CHANGED_FRACTION = 0.01  # share of pixels that must change to call it motion

# -an: the stream carries the mic too, and nothing below wants audio.
FFMPEG_IN = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-rtsp_transport", "tcp", "-i", STREAM, "-an"]


def grab_still():
    # Read from the stream so the camera is never opened a second time.
    r = subprocess.run(
        FFMPEG_IN + ["-frames:v", "1", "-q:v", "2", "-f", "image2", "-"],
        capture_output=True, timeout=15,
    )
    return r.stdout if r.returncode == 0 and r.stdout else None


def save(kind, jpg):
    out = os.path.join(CAPTURES, kind)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, time.strftime("%Y%m%d-%H%M%S.jpg")), "wb") as f:
        f.write(jpg)


def live(job):
    """Just the stream, for OBS and browsers."""
    job.stopping.wait()


def moved(prev, cur):
    changed = sum(abs(a - b) > WATCH_PIXEL_DELTA for a, b in zip(prev, cur))
    return changed > len(cur) * WATCH_CHANGED_FRACTION


def watch(job):
    """Saves a snapshot and sends a Telegram alert each time motion starts."""
    w, h = WATCH_SIZE
    # One ffmpeg, two outputs: tiny grey frames to compare, and the latest
    # full-size frame kept on disk so a snapshot is instant.
    proc = job.spawn(FFMPEG_IN + [
        "-vf", f"fps=2,scale={w}:{h},format=gray", "-f", "rawvideo", "-",
        "-vf", "fps=2", "-q:v", "2", "-f", "image2", "-update", "1", "-atomic_writing", "1", LATEST,
    ], stdout=subprocess.PIPE)
    try:
        # A motion event starts on the first moving frame after a still spell and
        # ends once nothing has moved for WATCH_QUIET_S. One snapshot and one
        # alert per event, however long the movement goes on.
        prev, moving, last_motion = None, False, 0.0
        while True:
            cur = proc.stdout.read(w * h)
            if len(cur) < w * h:
                break
            if prev and moved(prev, cur):
                last_motion = time.time()
                if not moving:
                    moving = True
                    try:
                        with open(LATEST, "rb") as f:
                            jpg = f.read()
                    except OSError:
                        jpg = None
                    if jpg:
                        save("watch", jpg)
                        notify.alert(jpg, f"Motion at {time.strftime('%H:%M:%S')} · {os.uname().nodename}")
            elif moving and time.time() - last_motion >= WATCH_QUIET_S:
                moving = False
            prev = cur
    finally:
        proc.terminate()


def timelapse(job):
    """Saves a still every 60 seconds."""
    while not job.stopping.is_set():
        jpg = grab_still()
        if jpg:
            save("timelapse", jpg)
        job.stopping.wait(TIMELAPSE_INTERVAL_S)


MODES = {"live": live, "watch": watch, "timelapse": timelapse}


class Job(threading.Thread):
    """Runs one mode until stopped, restarting it if it falls over."""

    def __init__(self, mode):
        super().__init__(daemon=True)
        self.mode, self.proc, self.stopping = mode, None, threading.Event()

    def spawn(self, cmd, **kw):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, **kw)
        if self.stopping.is_set():
            self.proc.terminate()
        return self.proc

    def stop(self):
        self.stopping.set()
        if self.proc:
            self.proc.terminate()

    def run(self):
        while not self.stopping.is_set():
            try:
                MODES[self.mode](self)
            except Exception:
                pass
            # ffmpeg exits when the stream is down; try again shortly.
            self.stopping.wait(5)


class Modes:
    """The current mode. Remembered across restarts in MODE_FILE."""

    def __init__(self):
        self.lock = threading.Lock()
        try:
            with open(MODE_FILE) as f:
                name = f.read().strip()
        except OSError:
            name = "live"
        self.job = Job(name if name in MODES else "live")
        self.job.start()

    @property
    def current(self):
        return self.job.mode

    def set(self, name):
        if name not in MODES:
            return False
        with self.lock:
            self.job.stop()
            os.makedirs(STATE, exist_ok=True)
            with open(MODE_FILE, "w") as f:
                f.write(name + "\n")
            self.job = Job(name)
            self.job.start()
        return True


def recent_captures(limit=24):
    items = []
    for kind in ("watch", "timelapse"):
        try:
            names = os.listdir(os.path.join(CAPTURES, kind))
        except OSError:
            continue
        items += [(n, kind) for n in names if n.endswith(".jpg")]
    items.sort(reverse=True)
    return [{"kind": k, "name": n, "url": f"/captures/{k}/{n}"} for n, k in items[:limit]]

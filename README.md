# Slipstream

A Raspberry Pi 5 with a Logitech C270 that serves a network camera feed for OBS.

## Use it

| What | Where |
| --- | --- |
| OBS Media Source (uncheck "Local File") | `rtsp://slipstream:PASSWORD@YOUR-PI:8554/cam` |
| Browser view (WebRTC) | `http://YOUR-PI:8889/cam` |
| Control page (modes, live view, snapshots) | `http://YOUR-PI:8080/` |
| Health | `http://YOUR-PI:8080/health` |
| Still image | `http://YOUR-PI:8080/still.jpg` |
| Shell | `ssh slipstream` |

Replace `YOUR-PI` with the Pi's hostname (its Tailscale name, or `hostname.local` on the home network) and
`PASSWORD` with the password below.

Everything asks for a login: user `slipstream`, and a password that exists only on the Pi.
`install.sh` prints it; to see it again run `ssh slipstream sudo cat /etc/slipstream/password`.
To change it, delete that file and run `install.sh` again. Commands run on the Pi itself need no password.

## How it works

- `pi/mediamtx.yml`: MediaMTX runs ffmpeg, which reads 1280x720 MJPEG at 30 fps from the camera and
  encodes H.264 with libx264. MediaMTX restarts ffmpeg if the camera drops.
- `pi/health.py`: small HTTP service on port 8080: health, stills, the control page, and mode switching.
  Stills are grabbed from the running stream.
- `pi/modes.py`: the modes. The stream always runs; a mode decides what else runs on top of it.
- `pi/systemd/`: `slipstream-mediamtx.service` and `slipstream-health.service`, both enabled at boot.

## Modes

| Mode | What it adds |
| --- | --- |
| `live` | Nothing. Just the stream. |
| `watch` | Saves a snapshot when something moves, at most one every 20 seconds. |
| `timelapse` | Saves a still every 60 seconds. |

Switch from the control page, or on the Pi with `slipstream-mode watch`, or with
`curl -u slipstream:PASSWORD -X POST http://YOUR-PI:8080/mode/watch`. The mode survives a reboot.
Snapshots are saved under `/var/lib/slipstream/captures/` and are not pruned.

## Deploy

From the Mac, in this folder:

```bash
rsync -a --exclude .git ./ slipstream:slipstream/ && ssh slipstream 'bash ~/slipstream/pi/install.sh'
```

`install.sh` installs ffmpeg and MediaMTX if missing, creates the password on first run, writes the
MediaMTX config with that password to `/etc/slipstream/`, then installs and restarts the services.

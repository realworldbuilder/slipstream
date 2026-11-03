# Slipstream

A Raspberry Pi 5 with a Logitech C270 that serves a network camera feed, with sound, for OBS.
It can also watch a room and send a Telegram photo when something moves.

## Use it

| What | Where |
| --- | --- |
| OBS Media Source (uncheck "Local File"; video and mic audio) | `rtsp://slipstream:PASSWORD@YOUR-PI:8554/cam` |
| Browser view (WebRTC) | `http://YOUR-PI:8889/cam` |
| Control page (modes, live view, snapshots) | `http://YOUR-PI:8080/` |
| Health | `http://YOUR-PI:8080/health` |
| Still image | `http://YOUR-PI:8080/still.jpg` |
| Shell | `ssh slipstream` |
| Telegram alerts, one-time setup | `ssh -t slipstream slipstream-alerts setup` |

Replace `YOUR-PI` with the Pi's hostname (its Tailscale name, or `hostname.local` on the home network) and
`PASSWORD` with the password below.

Everything asks for a login: user `slipstream`, and a password that exists only on the Pi.
`install.sh` prints it; to see it again run `ssh slipstream sudo cat /etc/slipstream/password`.
To change it, delete that file and run `install.sh` again. Commands run on the Pi itself need no password.

## How it works

- `pi/mediamtx.yml`: MediaMTX runs ffmpeg, which reads 1280x720 MJPEG at 30 fps and the mic from the
  camera and encodes H.264 with libx264 and Opus with libopus. MediaMTX restarts ffmpeg if the camera drops.
- `pi/health.py`: small HTTP service on port 8080: health, stills, the control page, mode switching and a
  test alert. Stills are grabbed from the running stream.
- `pi/modes.py`: the modes. The stream always runs; a mode decides what else runs on top of it.
- `pi/notify.py`: sends a photo to Telegram. `pi/slipstream-alerts` sets that up.
- `pi/systemd/`: `slipstream-mediamtx.service` and `slipstream-health.service`, both enabled at boot.

## Modes

| Mode | What it adds |
| --- | --- |
| `live` | Nothing. Just the stream. |
| `watch` | Saves a snapshot and sends a Telegram alert each time motion starts. |
| `timelapse` | Saves a still every 60 seconds. |

Switch from the control page, or on the Pi with `slipstream-mode watch`, or with
`curl -u slipstream:PASSWORD -X POST http://YOUR-PI:8080/mode/watch`. The mode survives a reboot.
Snapshots are saved under `/var/lib/slipstream/captures/` and are not pruned.

## Alerts

Watch mode sends each snapshot to Telegram as a photo. A *motion event* starts on the first frame that
moves after the scene has been still and ends after 10 seconds without movement; each event gives one
snapshot and one alert, however long the movement lasts. Thresholds are constants at the top of `pi/modes.py`.

Setup is once, from the Mac, and needs a terminal because it asks questions:

```bash
ssh -t slipstream slipstream-alerts setup
```

It asks for a bot token (make one with @BotFather in Telegram), then waits for you to message that bot so it
can learn your chat id, writes both to `/etc/slipstream/telegram` on the Pi, and sends a test photo.
`slipstream-alerts test` sends another; `slipstream-alerts off` deletes the file and stops alerts. The control
page shows whether alerts are on and has a "Send test alert" button. Without the file, watch mode still saves
snapshots, it just tells nobody.

## Deploy

From the Mac, in this folder:

```bash
rsync -a --exclude .git ./ slipstream:slipstream/ && ssh slipstream 'bash ~/slipstream/pi/install.sh'
```

`install.sh` installs ffmpeg and MediaMTX if missing, creates the password on first run, writes the
MediaMTX config with that password to `/etc/slipstream/`, then installs and restarts the services. It
leaves the alert settings alone, and says at the end whether they exist.

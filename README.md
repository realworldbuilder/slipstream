# Slipstream

A Raspberry Pi 5 (`slipstream-01`) with a Logitech C270 that serves a network camera feed for OBS.

## Use it

| What | Where |
| --- | --- |
| OBS Media Source (uncheck "Local File") | `rtsp://slipstream-01:8554/cam` |
| Browser view (WebRTC) | `http://slipstream-01:8889/cam` |
| Health | `http://slipstream-01:8080/health` |
| Still image | `http://slipstream-01:8080/still.jpg` |
| Shell | `ssh slipstream` |

`slipstream-01` resolves over Tailscale. On the home network without Tailscale, use `slipstream-01.local`.

## How it works

- `pi/mediamtx.yml`: MediaMTX runs ffmpeg, which reads 1280x720 MJPEG at 30 fps from the camera and
  encodes H.264 with libx264. MediaMTX restarts ffmpeg if the camera drops.
- `pi/health.py`: small HTTP service on port 8080. Stills are grabbed from the running stream.
- `pi/systemd/`: `slipstream-mediamtx.service` and `slipstream-health.service`, both enabled at boot.

## Deploy

From the Mac, in this folder:

```bash
rsync -a --exclude .git ./ slipstream:slipstream/ && ssh slipstream 'bash ~/slipstream/pi/install.sh'
```

`install.sh` installs ffmpeg and MediaMTX if missing, then installs and restarts the services.

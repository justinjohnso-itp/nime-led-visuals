# Handoff — Live Music Root Tuning & Web Control UI

## Next Steps (For Next Agent)
1. **Read this `HANDOFF.md` and `AGENTS.md` first.**
2. **Verify live Pi status** over SSH (`ssh -i ~/.ssh/github_ed25519 admin@nime-visuals.local`):
   - Service: `sudo systemctl status nime-led-visuals`
   - Web UI: `http://nime-visuals.local/` (port `80`) or `http://nime-visuals.local:8080/` (port `8080`)
3. **Fine-tune live parameters during soundcheck/set** if requested, or extend presets in `scripts/config.py` (`PRESETS`).

## What Was Accomplished & Verified
- **Hardware & Wiring Verified:** Confirmed single USB power + ground harness from Pi USB port + GPIO 21 (physical pin 40) data line works cleanly without ground-reference flicker. Added `~/.ssh/github_ed25519.pub` to `admin@nime-visuals.local:~/.ssh/authorized_keys`.
- **Audible Root Frequency Weighting (`scripts/audio_analyzer.py`):**
  - Added `_compute_root_weight_curve()` controlled by live `root_focus` parameter (`default: 0.80`).
  - Boosts audible musical root fundamentals (`38–950 Hz`, bands `0–20` up to `1.75x`), rolls off upper mids (`950–2200 Hz`), and attenuates high overtone/cymbal wash (`>2200 Hz` down to `0.25x`).
  - Added peak-relative root dominance contrast (`(spectrum_norm / frame_peak) ** (1 + 0.95 * root_focus)`) so defining root notes command the visual field during full live mixes while keeping peaks at `1.0`.
- **Anti-Spike Mitigation & Floor-Safety Idle Animation (`scripts/audio_analyzer.py`, `scripts/effects.py`, `scripts/config.py`, `scripts/web_server.py`):**
  - Recorded live incoming telemetry from the Pi and eliminated random flashes during chill music via 4 layers (`spike_suppression`, default `0.82`): (1) 98th-percentile time-domain de-clicker for USB ADC pops, (2) rolling `spectrum_buffer` updates even during noise-gate closure so stale loud samples never burst when the gate opens, (3) soft noise-gate knee + pre-normalization per-band 1-frame jump filter + multi-second slow peak ceiling (`slow_global_max`) so brief pauses don't collapse `global_max` and cause the next chill note to flash at 100%, and (4) upward slew-rate limiting (especially on upper blue bands `16..31`).
  - Added automatic **Floor Guard** idle animation (`idle_brightness=0.35`, `idle_timeout=4.0s`) that smoothly fades in after `idle_timeout` seconds of silence (and fades out in ~80ms when music plays) with pulsing corner/end beacons on each of the 3 bars plus high-contrast outward traveling waves and a sweeping comet orb so nobody steps on the floor strips between sets.
  - Added live **Active Preset Indicator** in the Web UI header (`PRESET`) and glowing `ACTIVE` badge on the matching preset button (or `Custom` when sliders are tweaked).
- **Live Web Control UI & Power-On Resilience (`scripts/web_server.py`, `scripts/main.py`, `scripts/audio_input.py`, `scripts/shell/install-service.sh`):**
  - Built zero-dependency `ThreadingHTTPServer` + Server-Sent Events (`/api/stream`, `/api/params`, `/api/init`, `/api/reset`) listening on **both port `80` and port `8080`**.
  - Starts the web server **before** audio initialization and runs audio capture inside a self-healing hot-plug retry loop (`sd._terminate(); sd._initialize()`). Even if the Pi powers on before the `AB13X` USB audio dongle or 3.5mm cable is plugged in, the web UI comes up immediately on power-on and automatically connects to audio the moment the cable is inserted.
  - Updated `nime-led-visuals.service` with `StartLimitIntervalSec=0` and `Restart=always` so systemd never stops restarting the service.
  - Real-time ~16 FPS canvas visualization of the 3 angled stage LED strips (`432 LEDs`) + `32-band` spectrum with root-zone highlight, telemetry, 4 live presets (`Live Music Roots`, `Punchy Band Mix`, `Massive Root Bloom`, `NIME Original`), and 14 live sliders persisted to `runtime_params.json`.
- **Verification Evidence:**
  - Local tests passed: `test_complete_pipeline.py`, `test_spectrum_viz.py`, `test_40hz_isolation.py`, plus HTTP/SSE endpoint integration checks.
  - Synced to Pi (`/home/admin/Code/nime-led-visuals`), restarted `nime-led-visuals.service`, and verified `http://127.0.0.1:8080/api/init` and `active (running)` systemd status on `nime-visuals.local`.

## Decisions & Rationale
- **Zero-dependency stdlib HTTP + SSE server:** Avoids installing Flask/FastAPI on the 1 GB RAM Pi 3B or mutating `pixi.lock` before a live show.
- **Thread-safe `LIVE_PARAMS` with JSON persistence (`runtime_params.json`):** Allows slider tweaks from phone/laptop to survive service restarts without dirtying git-tracked files.

## Learning Checkpoint (Not Saved; Promotion Not Approved)
- **Candidate:** When driving WS2812B strips on Raspberry Pi alongside a live web control UI, downsample LED preview frames (3:1, 432 -> 144 pixels at ~16 Hz over SSE) so mobile browsers render smoothly without starving the 60 FPS `rpi_ws281x` DMA thread.

## Git & Deployment State
- **Worktree:** `/Users/justin/Dropbox/NYU/semester-3-2025-fall/new-interfaces-for-musical-expression/nime-led-visuals` (`main` branch, pushed to `origin/main`).
- **Pi Checkout:** `/home/admin/Code/nime-led-visuals` synced with latest code and running via `nime-led-visuals.service`.

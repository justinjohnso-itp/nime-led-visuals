# nime-led-visuals

Audio-reactive LED visualization. Shows dominant audio frequencies as a color gradient (red=bass, blue=treble) across 432 LEDs (3 strips × 144 LEDs each).

## Quick Start (Raspberry Pi)

### Automated Setup (Recommended)

**Use Raspberry Pi OS Desktop** (not Lite - missing audio/driver packages).

On a fresh Raspberry Pi OS Desktop install, run:

```bash
cd ~/Code/nime-led-visuals
./scripts/shell/setup-all.sh
```

This script:
- Installs system dependencies (ALSA, PulseAudio, PortAudio, build tools)
- Enables I2C, SPI, and console auto-login via raspi-config
- Adds your user to `audio`, `gpio`, `i2c`, `spi` groups
- Configures WiFi (MrPineapple by default)
- Installs pixi and Python dependencies
- Installs systemd service for auto-start at boot

After setup completes, reboot:

```bash
sudo reboot
```

Visualization starts automatically. View logs with:

```bash
journalctl -u nime-led-visuals -f
```

### Manual Setup (macOS Development)

On macOS with pixi installed:

```bash
pixi install
```

## Run

### On Raspberry Pi

```bash
# Test LED strips
pixi run test-leds

# Test audio analysis
pixi run test-audio

# Run file visualization + web console (http://localhost:8080/)
pixi run run-file

# Run live visualization
pixi run run-live

# View service logs
journalctl -u nime-led-visuals -f
```

### On macOS

```bash
# Test audio analysis
pixi run test-audio

# Run file visualization + web console (http://localhost:8080/)
pixi run run-file
```

## How It Works

Analyzes incoming audio at 48 kHz and renders a live stage show across 3 floor bars (`Stage Left`, `Center Stage`, `Stage Right`):
- **32-band logarithmic spectrum** (`45–7040 Hz`) with 2nd–15th harmonic suppression, audible root weighting (`40–950 Hz`), downward root bloom (`center_strip_boost`), and 4-stage anti-spike filtering
- **Floor Guard idle safety mode** (`idle_brightness=0.28`) fades in strip-end safety beacons and a gentle breathing wave between sets
- **Web Control UI** on ports `80` and `8080` (`http://nime-visuals.local/`) with live 3-bar LED preview, 32-band spectrum, presets, and persistent parameter sliders (`runtime_params.json`)

## Code Structure

- `scripts/main.py` - Entry point, audio/LED threads, hot-plug retry loop, terminal monitor
- `scripts/audio_analyzer.py` - Dual-FFT 32-band spectrum, harmonic suppression, root weighting, and spike filtering
- `scripts/audio_input.py` - Live USB audio (`sounddevice`) and file (`librosa`) input handlers
- `scripts/effects.py` - Mirrored root-warped spectrum renderer, downward root bloom, and Floor Guard idle animation
- `scripts/web_server.py` - Zero-dependency HTTP + SSE live control UI on ports `80` and `8080`
- `scripts/config.py` - Tunable constants, presets, and thread-safe runtime state

## Hardware

- Raspberry Pi 3B+ or 4 (GPIO 21 for LED data, pin 40)
- 3× WS2812B LED strips (144 LEDs each, daisy-chained)
- 5V power supply (30A recommended for 432 LEDs)
- USB audio interface

### Wiring

```
LED Strip                         Raspberry Pi
────────────────────────────────────────────────
5V  ←── External 5V PSU (+)
GND ←── External 5V PSU (-) ───── GND (pin 6)
DIN ←── 330Ω resistor ─────────── GPIO21 (pin 40)
```

**Important:** Connect Pi GND to LED strip GND for common ground reference.

### Safe Power Handling

⚠️ **Never connect/disconnect GPIO while powered** - this can permanently damage GPIO pins.

#### Power-Up Sequence
1. Everything OFF
2. Connect all wires (GND first, then data, then power)
3. Power ON LED strip PSU
4. Power ON Pi

#### Power-Down Sequence
1. Stop LED software (`Ctrl+C`)
2. Shutdown Pi: `sudo shutdown -h now` (wait for green LED to stop)
3. Power OFF LED strip PSU
4. Disconnect wires

#### Hardware Shutdown Button (Recommended)

Add to `/boot/firmware/config.txt`:
```
dtoverlay=gpio-shutdown,gpio_pin=3
dtoverlay=gpio-poweroff,gpiopin=26
```

Wire a momentary button between **Pin 5 (GPIO3)** and **Pin 6 (GND)**:
- Press → Pi shuts down safely
- Press again → Pi boots back up

Optional: Wire an LED (with 330Ω resistor) to GPIO26 - lights up when safe to unplug.

## Project Context

- [`HANDOFF.md`](./HANDOFF.md) - Live root tuning, Floor Guard idle safety mode, and web control UI details
- [`ROADMAP.md`](./ROADMAP.md) - OctoRig comparison, immediate performance fixes, and planned NIME/DSP/hardware tracks
- [`AGENTS.md`](./AGENTS.md) - Development decisions and cross-platform setup details

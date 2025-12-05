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

# Test audio with file
pixi run test-audio music/test.mp3

# Run live visualization
pixi run run-live

# View service logs
journalctl -u nime-led-visuals -f
```

### On macOS

```bash
# Test audio analysis
pixi run test-audio music/test.mp3
```

## How It Works

Analyzes incoming audio in real-time:
- **Spectral centroid** identifies the dominant frequency
- **Bandwidth** measures how broad the spectrum is
- Maps to a color: red (20 Hz) → green (450 Hz) → blue (20 kHz)
- Brightness follows volume
- Edge LEDs show secondary frequencies

Example: Playing a low note lights up mostly red with some orange edges. Playing a high note lights up mostly blue with some cyan edges.

## Code Structure

- `main.py` - Entry point, threading, main loop
- `audio_analyzer.py` - FFT analysis, spectral centroid/bandwidth calculation
- `audio_input.py` - Audio device interface
- `effects.py` - LED color mapping from audio features
- `config.py` - All tunable constants

All code is self-documented with docstrings and inline comments explaining the algorithms.

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

See `AGENTS.md` for development decisions and cross-platform setup details.

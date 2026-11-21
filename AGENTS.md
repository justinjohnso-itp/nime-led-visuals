# AGENTS.md - Development Context & Decisions

---
## ⚠️ CRITICAL: Context & Thread Tracking

### 🚨 ACTIVE HANDOFF: Read `HANDOFF.md` First!
**Before doing anything else, read [`HANDOFF.md`](./HANDOFF.md) in the repository root.** It contains the exact state of the live pop-up installation, the live web control UI (`http://nime-visuals.local:8080/`), the audible root-frequency weighting & LED real-estate warp, and SSH access details for `admin@nime-visuals.local`.

### Before Starting Work
1. **Read `HANDOFF.md` and this entire `AGENTS.md`** to understand project state and conventions
2. **Use `read_thread` on relevant threads** from the history below based on what you're working on:
   - Audio analysis issues → Phase 2, 4 threads
   - LED effects/visualization → Phase 5, 7 threads  
   - Color/brightness tuning → Phase 3 threads
   - Responsiveness/edge cases → Phase 6 threads
3. **Check `git log` and `git diff`** when you need to understand recent changes or debug regressions

### Before Ending Work
**ALWAYS add this thread's ID to the "Audio-Reactive LED Visualization Thread History" section at the bottom of this file.**

Format: `- [T-{id}](https://ampcode.com/threads/T-{id}) - Brief description of what was done`

The current thread URL is in your Environment context. This maintains project continuity across sessions.

**Do this EARLY** - as soon as you've made meaningful changes, add the thread to history. Don't wait until the end, as context may run out unexpectedly.

---

## Project Overview
Audio-reactive LED visualization running on Raspberry Pi (aarch64) with development on macOS (arm64).

## Environment Management

### Tool Choice: Pixi (not Poetry)
- **Why Pixi:** Multi-language, conda-based, handles cross-platform dependencies reliably on embedded systems
- **Why not Poetry:** Slow/unreliable on ARM systems, pure Python only
- **Reference:** T-880467b8-311c-495b-9523-d8014f902a90

### Dependency Configuration Structure
Use **single `pixi.toml`** with platform-specific `[target.PLATFORM.pypi-dependencies]` sections.

**Key Pattern:**
```toml
[workspace]
platforms = ["linux-aarch64", "osx-arm64"]

[dependencies]
# Shared conda dependencies (both platforms)
python = "3.13.*"
numpy = ">=1.26.0"

[target.linux-aarch64.pypi-dependencies]
# Raspberry Pi only
adafruit-blinka = ">=8.0.0"
rpi-ws281x = ">=5.0.0"
```

**Do NOT use:**
- `pyproject.toml` with `[tool.pixi]` sections
- PEP 508 markers in PyPI dependencies (Pixi doesn't support them)

### Commands
```bash
pixi install              # Install all dependencies for current platform
pixi run test-audio       # Run task from pixi.toml
pixi run test-leds        # Test LED hardware
```

---

## Audio Playback (MP3 on Raspberry Pi)

### Solution: ffmpeg → aplay Pipeline
Direct `mpg123` subprocess calls fail due to audio driver context issues. Use explicit format matching.

**Working Pattern (in Python):**
```python
ffmpeg_proc = subprocess.Popen(
    ['ffmpeg', '-i', filepath, '-f', 's16le', '-ar', '44100', '-ac', '2', '-'],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
)
subprocess.Popen(
    ['aplay', '-f', 'S16_LE', '-r', '44100', '-c', '2'],
    stdin=ffmpeg_proc.stdout, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
)
ffmpeg_proc.stdout.close()
```

**Critical Details:**
- FFmpeg format: `-f s16le -ar 44100 -ac 2`
- Aplay format: `-f S16_LE -r 44100 -c 2`
- Must match exactly or audio will be garbled

**Reference:** T-8e1094c5-f3f7-4c0e-ac39-483e724b9151

---

## LED Control (Raspberry Pi)

### Required Dependencies
- `adafruit-blinka` (provides `board` module)
- `rpi-ws281x`
- `adafruit-circuitpython-neopixel`
- `adafruit-circuitpython-led-animation`

### Hardware
- GPIO Pin: `board.D21` / pin 40 (NeoPixel data line) - GPIO18 was damaged by hot-unplug

### Task Execution Pattern for sudo Commands
Tasks requiring `sudo` (GPIO access) cannot use pixi environment variables directly. Use shell script wrappers.

**pixi.toml:**
```toml
[tasks]
test-leds = "bash run_leds.sh"
run-live = "bash run_live.sh"
```

**run_leds.sh:**
```bash
#!/bin/bash
sudo "$(which python)" scripts/test_led.py
```

This ensures `sudo` runs the pixi-managed Python, not system Python.

**Reference:** T-71a81be7-6b48-490d-875e-f6360125779d

---

## Audio Analysis (Librosa Mel-Spectrogram)

### Implementation: `scripts/audio_analyzer.py`
Single source of truth for audio feature extraction. Uses librosa for robust FFT windowing.

**Key Parameters:**
- `n_fft=2048`: FFT window size (frequency resolution: 21.5 Hz/bin at 44.1 kHz)
- `hop_length=512`: Samples between frames (fixed)
- `center=False`: No padding on signal edges (correct for streaming with `with_buffer`)
- `n_mels=128`: Mel-scale frequency bands

**Buffer Management:**
- Accumulates audio chunks (1024 samples @ 44.1 kHz = 23.2 ms per chunk)
- Waits for `n_fft` samples before first analysis (~2 chunks = 46 ms startup)
- Drops `num_frames * hop_length` samples after analysis to prevent re-analysis
- Maintains overlap for proper spectral continuity

**Known Limitation: Spectral Leakage at Low Frequencies**
- 40 Hz tone shows energy across sub_bass (20-80 Hz) and bass (80-250 Hz)
- This is FFT windowing behavior, not a bug. Mel-scale groups frequencies logarithmically.
- Use `n_fft >= 3072` for better sub-bass resolution, but increases startup latency
- Current choice (n_fft=2048) balances responsiveness with reasonable frequency resolution

**Reference:** T-65b448a9-8796-4f59-aa35-262f55bd0106, T-9dae6224-0bd2-48b0-b6c6-4b7891d70ca8

---

## File Structure

```
.
├── pixi.toml                    # Single source of truth for dependencies
├── pixi.lock                    # Lock file (commit this)
├── scripts/
│   ├── audio_analyzer.py       # Audio feature extraction (librosa) - ONLY analyzer
│   ├── audio_input.py          # Audio input handler
│   ├── config.py               # Configuration (SAMPLE_RATE, CHUNK_SIZE, FREQ_BANDS)
│   ├── effects.py              # LED effect algorithms
│   ├── main.py                 # Main visualization loop
│   ├── test_audio.py           # MP3 playback test
│   ├── test_led.py             # LED hardware test
│   └── tests/                  # Test suite
├── run_leds.sh                 # Wrapper for sudo LED test
├── run_live.sh                 # Wrapper for sudo live visualization
└── music/
    └── test.mp3                # Test audio file
```

---

## Development Workflow

### Audio Test Files
- `music/music-test.mp3` - Full song (~3 minutes) for end-to-end testing with real music
- `music/sweep.wav` - 30-second logarithmic sine wave sweep (20 Hz to 7040 Hz) for diagnostic testing
  - Use this to verify frequency-to-LED mapping and harmonic suppression across the full instrument range
  - Frequency increases exponentially (logarithmically), matching human hearing perception

### On macOS
```bash
pixi run test-audio music/music-test.mp3  # Test with real music
pixi run test-audio music/sweep.wav       # Test with frequency sweep
```

### On Raspberry Pi
```bash
pixi run test-leds                        # Test LED control
pixi run run-live                         # Run visualization with live audio input
```

---

## Safe Power Handling

### Golden Rules
1. **Power OFF everything before connecting/disconnecting GPIO** - hot-plug kills pins
2. **Connect GND first, disconnect GND last** - ensures common reference
3. **Power strip separately from Pi** - 432 LEDs can draw 26A at full white

### Power-Up Sequence
```
1. Everything OFF
2. Connect wires (GND first, then data, then power)
3. Power ON LED strip PSU
4. Power ON Pi
```

### Power-Down Sequence
```
1. Stop LED software (Ctrl+C)
2. Power OFF Pi (sudo shutdown -h now, wait for green LED stop)
3. Power OFF LED strip PSU
4. Disconnect wires (power first, data, GND last)
```

### Hardware Shutdown Button (Recommended)

Add to `/boot/firmware/config.txt`:
```
dtoverlay=gpio-shutdown,gpio_pin=3
dtoverlay=gpio-poweroff,gpiopin=26
```

**Wiring:**
```
Shutdown Button: Pin 5 (GPIO3) ──┤ Button ├── Pin 6 (GND)
Safe-to-unplug LED: GPIO26 ──┤ 330Ω ├── LED ── GND
```

- Press button → Pi shuts down safely
- LED lights when safe to unplug
- Press button again → Pi boots back up

### Wiring Best Practices
```
LED Strip Power (5V, high current)
├── 5V  ←── External 5V PSU (+)
├── GND ←── External 5V PSU (-) ←── ALSO connect to Pi GND (common ground!)
└── DIN ←── Pi GPIO (pin 40/GPIO21) via 330Ω resistor

Pi Power
└── Separate USB-C / micro-USB supply
```

**Optional protection:**
- 330Ω resistor on data line (limits current spikes)
- 1000µF capacitor across LED strip power (prevents voltage spikes)

---

## Known Limitations & Workarounds

1. **Markers in PyPI dependencies:** Pixi doesn't support PEP 508 markers like `markers = "platform_machine == 'aarch64'"`. Use `[target.PLATFORM.pypi-dependencies]` instead.

2. **Sudo with pixi environment:** Must use shell script wrappers with `$(which python)` to ensure sudo runs the correct Python interpreter.

3. **Audio driver context:** Subprocess calls to audio tools default to OSS or fail PulseAudio connection. Must use explicit format piping (ffmpeg → aplay).

---

---

## Audio-Reactive LED Visualization Thread History

**When starting a new thread for visualization work, reference the most recent thread below as context.**

### Phase 1: Initial Setup & Core Architecture
- [T-558a4f5f-18fa-4943-9b55-ed363ff74eea](https://ampcode.com/threads/T-558a4f5f-18fa-4943-9b55-ed363ff74eea) - Project initialization and red core dynamics
- [T-76202d6c-a3bf-4bdd-873e-3432f044d11e](https://ampcode.com/threads/T-76202d6c-a3bf-4bdd-873e-3432f044d11e) - Spectral color representation issue
- [T-6f554b21-98ff-4edf-be34-f2746edfcc9a](https://ampcode.com/threads/T-6f554b21-98ff-4edf-be34-f2746edfcc9a) - Frequency-to-color mapping strategy

### Phase 2: Refinement & Optimization
- [T-58b990b3-c7d6-4984-934b-e32135d4ab0d](https://ampcode.com/threads/T-58b990b3-c7d6-4984-934b-e32135d4ab0d)
- [T-d451920e-a84e-4554-8af2-d1de72446918](https://ampcode.com/threads/T-d451920e-a84e-4554-8af2-d1de72446918)
- [T-32f30632-1aa7-43fe-9c98-54793bedea05](https://ampcode.com/threads/T-32f30632-1aa7-43fe-9c98-54793bedea05)
- [T-745fad0d-dfe7-4125-bbc1-1eb4237f3fff](https://ampcode.com/threads/T-745fad0d-dfe7-4125-bbc1-1eb4237f3fff)
- [T-65b448a9-8796-4f59-aa35-262f55bd0106](https://ampcode.com/threads/T-65b448a9-8796-4f59-aa35-262f55bd0106)
- [T-9dae6224-0bd2-48b0-b6c6-4b7891d70ca8](https://ampcode.com/threads/T-9dae6224-0bd2-48b0-b6c6-4b7891d70ca8)

### Phase 3: Color Science & Perceptual Tuning
- [T-126fb8c8-3a2d-4f29-ba57-e56cfc0e2df3](https://ampcode.com/threads/T-126fb8c8-3a2d-4f29-ba57-e56cfc0e2df3)
- [T-fe91cf6f-9ea2-4a1a-a24a-4492ce109110](https://ampcode.com/threads/T-fe91cf6f-9ea2-4a1a-a24a-4492ce109110)
- [T-f182f82d-83b3-47e7-8147-5a111e12ba44](https://ampcode.com/threads/T-f182f82d-83b3-47e7-8147-5a111e12ba44)

### Phase 4: Advanced Frequency Analysis & Hue Dynamics
- [T-ca0ddde4-319e-4f0f-9a13-5e8b0935f4a8](https://ampcode.com/threads/T-ca0ddde4-319e-4f0f-9a13-5e8b0935f4a8)
- [T-e98279df-d848-4ab5-9418-0dc256968dc0](https://ampcode.com/threads/T-e98279df-d848-4ab5-9418-0dc256968dc0)
- [T-b5c6a48d-d8a6-4d5f-a34d-89a95185d642](https://ampcode.com/threads/T-b5c6a48d-d8a6-4d5f-a34d-89a95185d642)

### Phase 5: Dominant Band Detection & Spatial Effects
- [T-8e1094c5-f3f7-4c0e-ac39-483e724b9151](https://ampcode.com/threads/T-8e1094c5-f3f7-4c0e-ac39-483e724b9151)
- [T-71a81be7-6b48-490d-875e-f6360125779d](https://ampcode.com/threads/T-71a81be7-6b48-490d-875e-f6360125779d)
- [T-880467b8-311c-495b-9523-d8014f902a90](https://ampcode.com/threads/T-880467b8-311c-495b-9523-d8014f902a90)

### Phase 6: Responsiveness & Edge Cases
- [T-7f02993a-a2a1-4768-93ad-d13f511bd5c0](https://ampcode.com/threads/T-7f02993a-a2a1-4768-93ad-d13f511bd5c0)
- [T-318040e4-4cf7-4ac0-92d2-d7dec2e58344](https://ampcode.com/threads/T-318040e4-4cf7-4ac0-92d2-d7dec2e58344)
- [T-eb6e8804-fa52-4231-ad1a-10ad89f5ab1f](https://ampcode.com/threads/T-eb6e8804-fa52-4231-ad1a-10ad89f5ab1f)

### Phase 7: Frequency Mapping & Band Feathering (Current)
- [T-03c80fab-c286-405b-a059-e24afa22d852](https://ampcode.com/threads/T-03c80fab-c286-405b-a059-e24afa22d852) - Doubled cluster width (2x previous)
- [T-35d620a1-0719-42f6-b0dc-5e57c9524b8a](https://ampcode.com/threads/T-35d620a1-0719-42f6-b0dc-5e57c9524b8a) - Doubled cluster width again (4x original), raised gain/brightness, fixed dead bands

### Phase 8: Hardware Debugging
- [T-e66c5294-d8e5-4e01-aeb5-22cf3410a095](https://ampcode.com/threads/T-e66c5294-d8e5-4e01-aeb5-22cf3410a095) - GPIO18 damage diagnosis after hot-unplug crash, LED strip only showing first 2 LEDs

### Phase 9: Live Music Root Weighting & Web Control UI (Current — see `HANDOFF.md`)
- Added live HTTP + SSE web control UI (`scripts/web_server.py` on both port `80` and port `8080`, `http://nime-visuals.local/` and `http://nime-visuals.local:8080/`) for phone/laptop monitoring and live parameter tuning (`runtime_params.json`).
- Made power-on startup resilient to unplugged USB/3.5mm audio: `main.py` starts the web server before audio init, and `audio_thread_func` + `LiveAudioInput` auto-retry PortAudio initialization every 2s until the USB dongle / 3.5mm jack is connected.
- Tuned `scripts/audio_analyzer.py` and `scripts/effects.py` for live music: weighted audible root frequencies (`40–950 Hz`, `root_focus=0.80`) with peak-relative root dominance contrast, and warped physical LED strip mapping (`root_real_estate=1.65`) so root frequencies command ~75% of the LED strip real estate.

Completely refactored to display a **mirrored logarithmic frequency spectrum** across the LED strip.

#### Audio Analysis Enhancements (`scripts/audio_analyzer.py`)
- **A-Weighting Disabled:** Preserves full bass response
- **Spectrum Decay:** Set to 0.95 for faster responsiveness while holding peaks
- **Frequency Range:** Extended to **20 Hz to 7040 Hz** (captures 30s Hz from NIME controller)
- **Bass Boost (Minimal):** Only bands 0-3 boosted 2.0x→1.0x (prevents flattening spectrum)
- **Global Normalization:** Uses global spectrum maximum (not per-band) to keep fundamental peak sharp
- **Harmonic Suppression:** **EXTREME** - Eliminates virtually all harmonic noise for pure fundamental visualization
  - **Detection window:** ±5% (extremely tight) - only suppresses bands exactly at harmonic frequencies
  - **2nd harmonic:** -36dB suppression (annihilates 2nd, most audible harmonic)
  - **3rd harmonic:** -30dB suppression (extreme suppression, very prominent naturally)
  - **4th-15th harmonics:** -24dB suppression, same tight detection
  - **Gaussian falloff:** Full suppression at exact harmonic, sharp Gaussian fade
  - **Post-suppression cleanup:** Eliminates outlier bands >2.0x median energy to 10% of value (ultra-aggressive, catches escaped harmonics at high frequencies)
  - **Result:** Fundamental concentration at 77-86% across all test frequencies, harmonics virtually invisible
- **Bass Bleed:** **DISABLED** - global normalization handles bass prominence without spreading energy
- **Result:** Visualization shows one tight, stable frequency group with virtually no harmonic noise throughout frequency sweep

#### LED Visualization (`scripts/effects.py`)
- **Linear Band Mapping:** Band 0 (lowest freq) at center → Band 31 (highest freq) at edges (bass centered, treble outward)
- **Brightness Window:** Minimal falloff (1 - 0.4x) creates extra-wide, well-lit cluster
  - Fundamental band at peak (1.0), brightness stays at 0.8 at band edges
  - Keeps entire frequency group well-lit with no dim LEDs
  - Energy distributed very widely across 4 levels of adjacent bands
- **Band Feathering:** EXTREMELY aggressive blending across 4 levels of adjacent bands
  - **First adjacent bands:** 50% max contribution (full range blend)
  - **Second adjacent bands:** 35% max contribution (full range blend)
  - **Third adjacent bands:** 20% max contribution (full range blend)
  - **Fourth adjacent bands:** 10% max contribution (full range blend)
  - Creates one massive visual cluster roughly 4x the width of original (~2x previous doubled version)
  - Peak brightness at fundamental, smooth linear fade to outermost LEDs
- **Brightness Gradient:** Center peak fades smoothly across very wide band range
  - Fundamental is brightest, brightness decreases linearly outward
  - All LEDs maintain good brightness across the entire group width
  - Creates impression of a very large, strong "blob" moving up the strip
- **Mirrored Display:** Spectrum reflects from center outward, creating symmetrical visual pattern
- **Perceptual Brightness:** Red/Bass boosted (1.0x max), Blue/Treble reduced (0.5x max) to emphasize low-end
- **Result:** Extra-wide, cohesive frequency group (~4x LED count) with all LEDs well-lit, peak at fundamental fading linearly to edges

---

## References
- T-8e1094c5-f3f7-4c0e-ac39-483e724b9151: Audio & LED setup
- T-71a81be7-6b48-490d-875e-f6360125779d: pixi.toml configuration
- T-880467b8-311c-495b-9523-d8014f902a90: Pixi vs Poetry decision
- T-7f02993a-a2a1-4768-93ad-d13f511bd5c0: MIDI controller (related project)
- T-318040e4-4cf7-4ac0-92d2-d7dec2e58344: Daisy Seed configuration (related hardware)
- T-eb6e8804-fa52-4231-ad1a-10ad89f5ab1f: Spectral complexity issue with full songs

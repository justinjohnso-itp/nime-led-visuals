# Project Roadmap

This roadmap tracks the current architecture, pending branch consolidation, and planned hardware, audio DSP, rendering, and show-control additions for `nime-led-visuals`, alongside a technical comparison against the commercial [OctoRig](https://octorig.com/) LED controller.

---

## 1. Current Baseline & Active Workstreams

### 1.1 Production Baseline on `origin/main` (Deployed on Raspberry Pi 3B)
- **Hardware & Power:** Drives 432 WS2812B 5V addressable LEDs (`3 × 144` daisy-chained floor bars: Stage Left, Center Stage, Stage Right) from Raspberry Pi `board.D21` (GPIO 21 / `PCM_DOUT`, physical pin 40) with an external 5V 30A power supply and an `AB13X` USB audio interface (`48000 Hz`, `1024`-sample chunks).
- **Audio Analysis & Anti-Spike Filtering (`scripts/audio_analyzer.py`, `scripts/config.py`):**
  - Dual `numpy.fft.rfft` pipeline: a `1024`-sample fast window (`46.88 Hz/bin`, `21.33 ms`) and a rolling `2048`-sample Hanning window (`23.44 Hz/bin`, `42.67 ms`) mapped across 32 logarithmic bands (`45 Hz – 7040 Hz`, with live `bass_floor_hz` slider defaulting to `55 Hz`).
  - Suppresses 2nd–15th harmonics (`-36 dB` on 2nd, `-30 dB` on 3rd, `-24 dB` on 4th–15th at `1.0` strength, scaled by `harmonic_suppression=0.85` by default) so fundamental notes hold 77–86% of band energy.
  - Weights audible root frequencies (`40–950 Hz`, `root_focus=0.80`), warps spatial strip mapping (`root_real_estate=1.65`), and applies downward root bloom (`center_strip_boost=1.65x`) so bass and low-mid fundamentals illuminate all 144 LEDs of the physical center strip.
  - 4-stage `spike_suppression` (`default: 0.82`): 98th-percentile time-domain ADC pop de-clicker, continuous rolling `spectrum_buffer` updates during noise-gate closure, soft noise-gate knee with multi-second `slow_global_max` ceiling, and upward slew-rate limiting on upper bands (`16..31`).
- **Floor Guard Idle Safety & Web Control UI (`scripts/effects.py`, `scripts/web_server.py`, `scripts/main.py`):**
  - Automatic **Floor Guard** idle animation (`idle_brightness=0.28`, `idle_timeout=4.0s`) fades in steady strip-end safety beacons and a gentle outward breathing wave when no music is playing so people do not trip over the floor bars between sets, fading out in ~80 ms when audio resumes.
  - Zero-dependency `ThreadingHTTPServer` + Server-Sent Events (SSE) console listening on **both port `80` and port `8080`** (`http://nime-visuals.local/`), starting before audio initialization with a self-healing PortAudio hot-plug retry loop (`sd._terminate(); sd._initialize()`) so the web UI stays online even if the USB audio interface is unplugged at boot.
  - Streams live 3:1 downsampled LED previews (`144` preview pixels / `48` per bar at ~16.7 FPS), 32-band spectrum, active preset badge, 4 presets, and live parameter sliders persisted to `runtime_params.json`.

### 1.2 Built on `hermes-master` Local Branch (`94daca1..0b6548a`, Ready to Merge with `origin/main`)
A parallel feature stack on the `hermes-master` server implements:
- **Stabilized Pitch, Beat/BPM & Macro Section Tracker (`scripts/audio_analyzer.py`):** 3-frame pitch persistence hysteresis and slew-rate glide (`stabilized_band`, `focus_band_pos`, cutting frame-to-frame dominant band jumps on `music/music-test.mp3` by 78.1%), refractory-gated (`165 ms`) kick/snare spectral flux beat onset detector with median IOI BPM estimation (`55–210 BPM`), and a macro song section classifier (`calm`, `groove`, `build`, `peak`) comparing short-term (`0.5s`) and long-term (`3.8s`) energy.
- **3-Layer HTP/LTP Concert Busking Engine (`scripts/effects.py`):** Simultaneous Base Wash (Layer 1), Center Stage Stabilized Root + Wing Harmonic Swell (Layer 2), and Beat-Phase Outward Pulse Waves + Blinders (Layer 3), using Latest/Focal Takes Precedence (LTP) color priority so blue high notes never mix with red wash into magenta, shortest-arc hue crossfading (`_interp_hue`), automatic palette drift on `build`/`peak` transitions, and a $C^0/C^1$ continuous perceptual luminance curve.
- **Concert Lighting Console UI (`scripts/web_server.py`, `scripts/config.py`):** Adds `TAP TEMPO`, `PUNT LOOK`, `FREEZE`, `BLACKOUT`, momentary `BLINDER HIT` and `WASH SWELL` pads with watchdog timers, 6 vertical submaster faders, 6 concert color palettes, and atomic `.tmp` + `os.replace()` persistence.
- **Standalone Venue Wi-Fi AP + Hotspot Auto-Switching (`scripts/shell/setup-wifi-ap.sh`):** `nime-wifi-auto.timer` scans `wlan0` every 20 seconds when no client is connected to the AP and joins any saved Wi-Fi network in range (`MrPineapple` phone hotspot or home Wi-Fi), or falls back to hosting the `NIME-Visuals` (`10.42.0.1`) AP without DHCP Options 3 and 6 so connected phones keep 5G/LTE internet.

---

## 2. Comparison: OctoRig Controller vs. `nime-led-visuals`

| Capability | OctoRig Controller (`octorig.com`) | `nime-led-visuals` (Current + Planned) |
| :--- | :--- | :--- |
| **Core Architecture** | Mac/Windows desktop app streams effect parameters over USB-C or 2.4 GHz Wi-Fi to a microcontroller board ($59.99 5V / $74.99 5V–24V). | Standalone Raspberry Pi runs audio capture, NumPy FFT analysis, multi-layer rendering, and the HTTP/SSE web console on one box. |
| **Live Audio Input** | Captures desktop audio (often via BlackHole on Mac or VB-Audio Cable on Windows), line-in, or mic on the host computer. | Direct low-latency ALSA/PortAudio capture from a USB audio interface (`AB13X`) on the Pi with automatic hot-plug recovery; no laptop required at the venue. |
| **Preview Accuracy** | Desktop app and hardware board run separate effect engines; preview approximates output. | Web console streams `LEDEffects.last_leds` directly from the renderer (downsampled 3:1 to 144 preview pixels) so colors and layers match the physical bars. |
| **Pitch & Overtone DSP** | Generic volume/beat reactivity and preset animations. | 32-band log spectrum (`45–7040 Hz`) with `-24 dB` to `-36 dB` harmonic suppression, root weighting, anti-spike filtering, and 3-frame pitch hysteresis. |
| **Song Section Awareness** | Manual timeline programming in Show Creator (synced to Spotify/YouTube tracks) or manual live triggers. | Autonomous `calm` / `groove` / `build` / `peak` classifier with automatic palette drift on upward transitions and Floor Guard idle safety mode between sets. |
| **Layering & Color Priority** | Runs one active effect or hit per configured Rig/Zone. | Simultaneous 3-layer busking engine (Wash + Root Focal + Beat Bump) with LTP color priority and perceptual luminance correction. |
| **Hardware Outputs & Voltage** | 4 parallel 3-pin ports (up to 900–1,200 px/port), 8A shared onboard power pass-through, native 5V/12V/24V support on upgraded board. | Single Pi `GPIO 21` (`PCM_DOUT`) driving 432 5V pixels today; expandable via multi-channel Pi DMA or UDP DDP/Art-Net to WLED nodes. |
| **Venue Hotspot Behavior** | Connecting directly to the `http://octorig.setup` hotspot drops phone/laptop internet access; onboard web UI is limited. | `NIME-Visuals` AP omits DHCP Options 3 and 6 so phones retain 5G/LTE data while running the full lighting desk in a mobile browser. |
| **Custom Code & Sensors** | Closed firmware and desktop app; user-scriptable effects are still on the future roadmap. | Open Python/NumPy stack; accepts custom DSP, USB serial from a Daisy Seed, UDP OSC, and multi-channel audio stems. |

---

## 3. Immediate Codebase Fixes & Quick Wins (Phase 10)

Inspection of the current `scripts/` modules identified six concrete high-leverage improvements that require zero extra hardware:

1. **Unify `origin/main` (`381d4bc`) and `hermes-master` Busking Engine (`0b6548a`):**
   - Combine `origin/main`'s boot-time PortAudio hot-plug retry loop, dual port `80`/`8080` web listener, 4-stage `spike_suppression`, `bass_floor_hz` / `center_strip_boost`, and **Floor Guard** idle safety beacons with `0b6548a`'s 3-layer HTP/LTP busking engine, 3-frame pitch hysteresis, refractory beat/BPM & section classifier, concert transport keys (`PUNT LOOK`, `FREEZE`, `BLACKOUT`, `BLINDER HIT`, `WASH SWELL`), and `setup-wifi-ap.sh` auto-switching timer.
2. **Fix `LEDThread` 30 FPS Sleep Cap (`scripts/main.py`):**
   - *Current issue:* `led_thread_func` runs `LEDEffects.frequency_spectrum()`, calls `pixels.show()` (which takes `~13.26 ms` of 800 kHz WS2812B wire transfer time for 432 LEDs), and then executes a fixed `time.sleep(0.01667)`. That `13.26 ms + 16.67 ms` cycle caps physical Raspberry Pi output at `~33 FPS` instead of `60 FPS`. Furthermore, when `HAS_LEDS` is `False` on macOS, `main.py` updates `LEDEffects.frequency_spectrum()` inside the `time.sleep(0.05)` terminal status loop (`20 FPS`).
   - *Fix:* Replace fixed `time.sleep(0.01667)` with a monotonic deadline scheduler (`next_t += 1.0 / FPS_TARGET; time.sleep(max(0.0, next_t - time.monotonic()))`) and run the 60 Hz render loop on macOS as well so web preview and envelope timing match hardware.
3. **Eliminate 432-Iteration `PixelSubset` Write Loops (`scripts/effects.py` and `scripts/main.py`):**
   - *Current issue:* After computing all 432 RGB tuples in vectorized NumPy, `effects.py` writes them one pixel at a time (`strip[led_idx] = leds[offset + led_idx]`) through `adafruit_led_animation.helper.PixelSubset`, triggering 432 Python wrapper calls per frame.
   - *Fix:* Have `led_thread_func` in `main.py` pass `strips=None` and assign the full 432-pixel list directly to the root `NeoPixel` buffer (`pixels[:] = leds`) before `pixels.show()`, while keeping `strips` population when `strips is not None` so existing unit tests (`test_busking_engine.py`, `test_spectrum_viz.py`, `test_complete_pipeline.py`, `test_instrument_range.py`, `test_led_viz.py`) continue to pass.
4. **Atomic `AudioFrame` Snapshot Swapping (`scripts/main.py`):**
   - *Current issue:* `AudioThread` mutates `shared_features` in-place via `shared_features.update(features)` while `LEDThread` and `WebServerThread` read keys concurrently, allowing torn mid-frame state reads.
   - *Fix:* Have `analyzer.analyze()` return an immutable snapshot dict (or frozen dataclass) and swap a single reference (`state_holder["latest"] = features`) between threads. Keep a ring buffer inside `LiveAudioInput`'s PortAudio callback so audio capture never blocks.
5. **Float32 Audio Pipeline & Pre-Gain ADC Clipping Detection (`scripts/audio_input.py:157-163`):**
   - *Current issue:* `LiveAudioInput.read_chunk()` converts float samples to `np.int16(data.flatten() * 32767)` without clamping to `[-1.0, 1.0]`, and `audio_analyzer.py` multiplies by `input_gain` (`15.0x`) afterward.
   - *Fix:* Pass `float32` arrays directly from `sounddevice` into `AudioAnalyzer`, measure hardware ADC clipping (`np.max(np.abs(raw_audio)) >= 0.99`) before software `input_gain`, and expose a live `CLIP` warning pill in the web console header.
6. **User-Savable Web Console Presets (`scripts/config.py`, `scripts/web_server.py`):**
   - Add `POST /api/presets` to save, rename, or delete custom soundcheck looks into `custom_presets.json` using lock-free atomic `.tmp` + `os.replace()` writes.

---

## 4. Track 1: NIME Sensor, Gesture & Daisy Seed Integration

Because the controller is a Linux box running Python, physical instrument gestures can modulate the lighting engine directly alongside audio analysis.

### 1.1 Daisy Seed USB CDC Serial & MIDI Telemetry Bridge
- **Problem:** Acoustic FFT pitch tracking requires waiting for at least one audio buffer (`21.3 ms` to `42.7 ms`). When performing on a custom Daisy Seed synthesizer, the microcontroller already knows the exact oscillator pitch, envelope gate, filter cutoff, and physical knob positions the instant a note is triggered.
- **Implementation (`scripts/daisy_bridge.py`):**
  - Open a non-blocking USB CDC serial reader (`pyserial` at `115200` or `921600` baud) or USB MIDI listener reading structured telemetry frames from the Daisy Seed (`{freq_hz, gate, filter_cutoff, morph_knob, sensor_dist}`).
  - Add a `pitch_source` mode (`"audio"`, `"daisy_serial"`, `"hybrid"`) in `config.py`. In `"hybrid"` mode, Daisy Seed note-on events immediately seed `stabilized_band` and `focus_band_pos` with zero FFT latency, while acoustic spectral energy drives the wing harmonics and wash envelope.

### 1.2 UDP Open Sound Control (OSC) Server (`python-osc`)
- **Problem:** External NIME patches (Max/MSP, Pure Data, TouchOSC, wireless ESP32/RP2040 sensor nodes) need a low-latency network protocol to steer lighting parameters without HTTP polling overhead.
- **Implementation (`scripts/osc_server.py`):**
  - Run an asynchronous UDP OSC server on port `9000` (`python-osc`).
  - Map `/nime/param/<key>` directly to `update_live_params(..., persist=False)`, `/nime/action/<cmd>` to `trigger_console_action()`, and `/nime/gesture/{spread,tilt,tension}` to real-time spatial modulators in `LEDEffects`.

### 1.3 Performer Gesture Sensors (ToF, IMU, String/Web Tension)
- **Hardware Topology Note:** Do not run long stage wires from `VL53L0X` time-of-flight or `BNO055` IMU sensors directly to Raspberry Pi I2C pins (`GPIO 2/3`); standard I2C degrades past `~0.5–1 m` of cable and synchronous Linux `smbus` reads (`5–20 ms`) stall threads. Attach gesture sensors to the **Daisy Seed** (wired USB serial) or a battery-powered **XIAO ESP32-S3** (streaming UDP OSC over the `NIME-Visuals` Wi-Fi AP).
- **Creative Mappings:**
  - *Sinetactophone dual distance sensors:* Map Player 1 hand distance to Center Stage focal position (`focus_band_pos`) and Player 2 hand distance to Stage Left/Right wing spread (`cluster_width`), and trigger white/gold interference blooms when both players converge on a harmonic interval.
  - *Tensioned thread / web piezo transducers:* Map pluck velocity and radial thread tension directly to outward traveling wave speed (`movement_speed`) and Strip 0 / Strip 2 asymmetry.

---

## 5. Track 2: Audio DSP & Musical Intelligence Upgrades

### 2.1 Multi-Resolution Sub-Bass FFT / Constant-Q Transform (CQT)
- **Root Cause in Current Code (`scripts/audio_analyzer.py`):** At `SAMPLE_RATE = 48000` and `spectrum_n_fft = 2048`, linear FFT bin spacing is `23.44 Hz`. However, the 32 logarithmic bands in `SPECTRUM_FREQS` are only `4–11 Hz` wide at the bottom of the spectrum (whether starting at `20 Hz` or `45 Hz`). When no FFT bin falls inside a narrow low band (`idx.size == 0`), the bin builder falls back to `closest = np.argmin(...)`, mapping multiple adjacent bass bands to the exact same FFT bin.
- **Solution:**
  - Maintain a parallel 8x-decimated sub-bass ring buffer (`48000 Hz -> 6000 Hz` via a lightweight IIR low-pass + decimation step) fed into a `512`-sample FFT.
  - This yields **`2.93 Hz/bin` resolution** across `20–250 Hz` (`~85 ms` window for sub-bass only) while keeping the `2048`-sample (`42.7 ms`) and `1024`-sample (`21.3 ms`) windows for mid/high frequencies and beat transients. Every logarithmic band from Band 0 upward gets its own distinct frequency bin.

### 2.2 Log-Magnitude Parabolic Bin Interpolation for Continuous Pitch Glide
- **Current Behavior:** Sub-band position tracking computes a weighted center of mass after bucketing energy into the 32 discrete bands.
- **Upgrade:** Before 32-band bucketing, fit a parabola to the log-magnitude of the peak FFT bin $k^*$ and its neighbors $(k^*-1, k^*+1)$:
  $$\delta = \frac{1}{2} \frac{\alpha - \gamma}{\alpha - 2\beta + \gamma}$$
  Converting $f_{\text{exact}} = (k^* + \delta)\frac{f_s}{N}$ into continuous logarithmic band coordinates eliminates stepping artifacts during slow theremin, cello, or fretless bass glissandos.

### 2.3 12-Bin Chromagram & Harmonic Key/Mood Tracking
- Fold FFT bin magnitudes from `C2 (65.4 Hz)` to `C6 (1046.5 Hz)` into a 12-element pitch-class profile (`C, C#, D, ..., B`).
- Correlate the rolling 4-second chromagram against Krumhansl-Schmuckler major/minor key profiles to estimate harmonic tension and major/minor modality:
  - Steer `auto_palette_drift` toward warmer/brighter palettes (`amber_crimson`, `emerald_gold`) in major keys and deeper high-contrast palettes (`indigo_rose`, `fire_ice`) in minor or chromatic passages.
  - Trigger subtle LTP hue shifts when a chord change (chromagram cosine distance spike) occurs on a downbeat.

### 2.4 Timbre & Articulation Classifier (Plucked vs. Sustained vs. Percussive)
- Compute **Spectral Flatness** (geometric mean divided by arithmetic mean of power spectrum) and **Spectral Crest / Attack Slope** in `AudioAnalyzer`:
  - *Bowed / sustained tonal notes (low flatness, slow attack):* Automatically widen `cluster_width` and lengthen `decay_speed` for smooth, slow-decaying stage washes.
  - *Plucked / staccato notes (low flatness, high attack slope):* Narrow `cluster_width` and boost `easing_exponent` for tight, localized note strikes.
  - *Percussive / noisy textures (high flatness):* Route energy to Layer 3 wing ripples rather than moving the Layer 2 Center Stage root lock.

### 2.5 Multi-Channel / Per-Stem USB Audio Routing (`scripts/audio_input.py`)
- **Current Limitation (`scripts/audio_input.py:159-162`):** `LiveAudioInput` averages stereo input channels to mono (`np.mean(data, axis=1)`).
- **Upgrade:** Support 2-to-8 independent input channels from multi-channel USB interfaces or mixers:
  - **Channel 1 (Solo NIME Instrument / Lead Vocal):** Drives Layer 2 (`stabilized_band`, `focus_band_pos`, Center Stage focal bloom) with zero drum bleed.
  - **Channel 2 (Kick / Rhythm Bus / Bass DI):** Drives Layer 3 (`beat_hit`, `beat_envelope`, `bpm`) and Layer 1 bass wash.
  - **Stereo Panning:** When fed a stereo main mix, compute left/right spectral energy difference per band (`pan_pos[b]`) to bias Stage Left (`Strip 0`) vs. Stage Right (`Strip 2`) wing blooms.

---

## 6. Track 3: External Sync, DAW/DJ Integration & Show Control

### 3.1 USB MIDI Clock, Ableton Link & Latency Anticipation
- **Goal:** Lock `bpm`, `beat_phase`, and `beat_index` (`1..4` downbeat) to external electronic instruments, DAWs, or DJ software (such as BiteDJ or Mixxx) instead of relying solely on acoustic spectral flux when a digital clock is available.
- **Implementation:**
  - **USB MIDI Clock (`mido`):** Listen for `clock` (`0xF8` at 24 PPQN), `start` (`0xFA`), and `continue` (`0xFB`) messages from any USB MIDI cable or DAW.
  - **Ableton Link (via `carabiner` or UDP bridge):** Because native C++ Python Link bindings (`aalink`) often lack prebuilt `linux-aarch64` wheels for Python 3.13 in `pixi.toml`, run a lightweight Link-to-OSC daemon or pure-Python UDP beat packet receiver on the local network.
  - **Latency Anticipation (`5–25 ms`):** Advance `beat_phase` by a configurable `sync_lead_ms` offset so Layer 3 outward pulse waves compensate for WS2812B wire transfer time (`13.3 ms`) and reach peak brightness on the physical LEDs at the exact acoustic downbeat.

### 3.2 Class-Compliant USB MIDI Controller Surface
- Plug a hardware MIDI controller (e.g., Novation Launchpad, Akai APC Mini, Midi Fighter Twister, or a 4-switch MIDI foot pedal for hands-free instrument performance) directly into the Raspberry Pi USB port:
  - Map hardware faders/knobs (MIDI CC) to the 6 submasters (`brightness`, `wash_intensity`, `root_swell`, `accent_amount`, `movement_speed`, `cluster_width`).
  - Map pads/footswitches (MIDI Notes) to `PUNT LOOK`, `BLACKOUT`, `FREEZE`, `TAP TEMPO`, `BLINDER HIT`, and `WASH SWELL`.
  - Send LED feedback velocities back to the MIDI controller so pad colors match the active `PALETTES` swatches and `beat_index` pip.

### 3.3 Real-Time Clock Governor for `FileAudioInput` & JSON Cue Recorder
- **Current Limitation (`scripts/audio_input.py:107-122`):** `FileAudioInput.read_chunk()` yields chunks in an unthrottled loop as fast as the CPU runs `rfft` (10x–50x faster than real time) and does not play audio through the Pi's headphone jack (`hw:1,0`).
- **Upgrade:**
  - Add a monotonic sample-clock governor and optional synchronized `ffmpeg -> aplay` audio playback inside `FileAudioInput` so `--file music-test.mp3` runs at exact 1.0x wall-clock speed with audible output.
  - Add a **Cue Recorder / Timeline Player** (`scripts/show_recorder.py`) that logs timestamped parameter changes, palette selections, and manual hits (`blinder_flash`, `wash_swell`, `punt_mode`) to a `.show.json` file and replays them sample-accurately alongside live audio analysis.

---

## 7. Track 4: Spatial Rendering, 2D Mapping & Color Pipeline

### 4.1 Polyphonic Multi-Peak Tracking (Dyads, Chords & Two-Player Instruments)
- **Current Behavior:** Layer 2 locks onto a single dominant fundamental (`stabilized_band`) and projects it onto Center Stage.
- **Upgrade:** After harmonic suppression in `AudioAnalyzer`, extract up to **3 distinct fundamental peaks** separated by at least 2 bands (`peaks = [p0, p1, p2]`):
  - In `"polyphonic_trio"` busk mode, route the lowest fundamental (`p0`, bass/root) to **Center Stage (`Strip 1`)**, the middle voice (`p1`) to **Stage Left (`Strip 0`)**, and the highest voice (`p2`) to **Stage Right (`Strip 2`)**, each rendered with its own pitch-mapped hue and independent 3-frame hysteresis tracker.

### 4.2 2D Physical Stage Coordinate Mapper (`(x, y)` Layout Engine)
- **Goal:** Allow effects to move across true physical 2D stage geometry (V-wings, vertical towers, triangles, or circular NIME surrounds) rather than assuming 1D strip indices `0..143`.
- **Implementation (`scripts/stage_layout.py`):**
  - Represent each strip segment by start/end 2D coordinates `(x0, y0) -> (x1, y1)` in normalized stage meters (matching the segment vector structure already used in `web_server.py:drawStageLEDs()`).
  - Precompute per-pixel `(x, y)` coordinates and polar `(r, theta)` vectors from stage center.
  - Add 2D spatial effects: horizontal/vertical stage sweeps, rotating lighthouse beams, and radial shockwaves expanding from `(0, 0)` across all three bars according to their real physical angles.
  - Make strip endpoints draggable in the web console's `stageCanvas` and persist the geometry to `stage_layout.json`.

### 4.3 Layer 3 1D/2D Particle & Shockwave Emitters
- Replace static Gaussian beat pulses on Layer 3 with a lightweight stateful particle pool (16–32 active particles vectorized in NumPy):
  - Each `beat_hit` spawns an ember/spark pair at the active `focus_band_pos` on Center Stage with initial velocity proportional to `beat_envelope` and `section_intensity`.
  - Particles travel outward onto Stage Left and Stage Right with configurable drag, gravity, and color cooling (white-gold core cooling through amber to crimson tail).

### 4.4 Linear-Light Gamma Pipeline & 1D Spatial Error-Diffusion Dithering
- **Problem:** At low brightness (`punt_level = 0.12`, `idle_brightness = 0.28`, or slow fade-outs), 8-bit integer WS2812B channels (`0..255`) step visibly between `1`, `2`, and `3`, shifting hue toward whichever primary channel rounds up first. Temporal dithering at `60 FPS` produces visible `30 Hz` flicker on dark stages.
- **Solution:**
  - Keep all layer blending in floating-point linear light (`0.0..1.0`), apply perceptual gamma (`gamma = 2.2`) at the end of `LEDEffects.frequency_spectrum()`, and run a single vectorized pass of **1D Sierra-Lite spatial error-diffusion dithering** along each 144-LED bar before converting to `uint8`. High pixel density (`144 LEDs/m`) blends neighboring 1-LSB dither patterns smoothly to the eye without temporal flicker.

---

## 8. Track 5: Hardware Scaling, Multi-Port Output & Lighting Protocols

### 5.1 Wireless/Wired WLED DDP, Art-Net & E1.31 (sACN) Output
- **Goal:** OctoRig's primary hardware advantage is its 4 independent output ports and 5V–24V strip support. Adding a network pixel output driver lets the Raspberry Pi act as the central audio DSP and busking controller while driving any number of remote LED strips or stage fixtures over Ethernet or Wi-Fi.
- **Implementation (`scripts/network_output.py`):**
  - **DDP (Distributed Display Protocol, UDP port `4048`):** A ~40-line pure-Python socket sender that packs RGB bytes with a 10-byte DDP header and streams them at 60 FPS to cheap ESP32 [WLED](https://kno.wled.ge/) controllers. Each ESP32 node can drive multiple 5V, 12V (WS2815), or 24V strips with zero changes to `audio_analyzer.py` or `effects.py`.
  - **Art-Net (UDP port `6454`) & E1.31 sACN (UDP port `5568`):** Map Layer 1 (`wash_rgb`), Layer 2 (`focal_rgb`), and Layer 3 (`accent_rgb`) summary channels or pixel universes to standard DMX512 universes so venue DMX par cans, wash bars, and moving heads follow the Pi's busking engine in lockstep with the LED strips.

### 5.2 Parallel Multi-Pin Local Output on Raspberry Pi 3/4/5
- **Hardware Constraint:** `adafruit-circuitpython-neopixel` wraps `rpi_ws281x` as a singleton channel and cannot drive multiple GPIO pins simultaneously. In addition, `PWM0` (`GPIO 12/18`) and `PWM1` (`GPIO 13/19`) share hardware with onboard 3.5mm analog audio (`bcm2835_audio`), and `GPIO 18` on the current Pi was damaged by hot-unplugging.
- **Upgrade Path:**
  - **Raspberry Pi 3/4 Direct Multi-Channel DMA:** Replace the `adafruit-circuitpython-neopixel` wrapper with direct `rpi_ws281x.PixelStrip` initialization (or a dedicated output abstraction) to drive up to 3 parallel local outputs simultaneously:
    - Strip 0: `GPIO 21` (`PCM_DOUT`, DMA channel 10)
    - Strip 1: `GPIO 12` (`PWM0`, channel 0) and Strip 2: `GPIO 13` (`PWM1`, channel 1) with `dtparam=audio=off` in `/boot/firmware/config.txt` (safe when using the `AB13X` USB audio interface).
    - Or Strip 2 on `GPIO 10` (`SPI0 MOSI` via `/dev/spidev0.0` with `spidev.bufsiz=32768`).
  - **Raspberry Pi 5 Compatibility (`Pi5Neo` / RP1 SPI):** Add an optional SPI backend (`Pi5Neo` under `[target.linux-aarch64.pypi-dependencies]` in `pixi.toml`) so the rig can migrate to a Raspberry Pi 5 without relying on BCM2835 DMA registers.
  - **Wire-Time Benefit:** Splitting 432 LEDs from one 432-pixel chain (`13.26 ms` wire time) into three parallel 144-pixel channels cuts wire transfer time to **`4.42 ms`**. This supports **120+ FPS** refresh rates or **SK6812 RGBW** strips (`32 bits/pixel`, `5.90 ms` per 144-LED strip) without dropping below 60 FPS.

### 5.3 GPIO Protection, Level Shifting & Software Power Limiter
- **Sacrificial 5V Logic Level Shifter Hat:** Add a `74AHCT125` quad buffer powered from the 5V rail with a `330 Ω` series output resistor and a `5.1V` TVS diode on each data connector. This shifts the Pi's `3.3V` logic to true `5.0V` CMOS thresholds (preventing data corruption on long stage runs) and isolates the Pi's SoC pins from hot-unplug voltage spikes.
- **Deterministic Software Power Limiter (`scripts/effects.py`):**
  - Full white across 432 WS2812B LEDs draws up to `~23.8 A – 26.0 A` at 5V.
  - Before `pixels.show()`, compute estimated current draw in software:
    $$I_{\text{est}} = I_{\text{quiescent}} + \sum_{i=1}^{432} \frac{R_i + G_i + B_i}{255} \times 0.0183\text{ A}$$
  - If $I_{\text{est}} > I_{\text{max}}$ (configurable `max_current_amps`, e.g., `20.0 A` for a 30A PSU with headroom, or `4.5 A` when testing on a small bench supply), scale output RGB by $I_{\text{max}} / I_{\text{est}}$ for that frame and display a live `AMPS` telemetry pill in the web UI.
  - *(Note: If hardware current telemetry via an `INA219`/`INA226` is added later, it must use an external `50A / 75mV` milliohm shunt rather than the breakout's `0.1 Ω` 3.2A shunt, and be polled at `<= 5 Hz` in a background thread.)*

---

## 9. Implementation Phasing

### Phase 10: Branch Consolidation & Core Engine Quick Wins (Zero Extra Hardware)
- [ ] Merge the `hermes-master` 3-layer HTP/LTP busking engine and `setup-wifi-ap.sh` auto-switching timer (`94daca1..0b6548a`) with `origin/main` (`381d4bc`'s Floor Guard idle safety mode, 4-stage spike suppression, `bass_floor_hz` / `center_strip_boost`, and boot-time USB audio hot-plug loop).
- [ ] Replace fixed `time.sleep(0.01667)` in `scripts/main.py` with a monotonic 60 Hz deadline timer and run `LEDEffects` at 60 Hz on macOS (`HAS_LEDS = False`).
- [ ] Bypass per-LED `PixelSubset` loops in `scripts/main.py` by passing `strips=None` and writing `pixels[:] = leds` directly before `pixels.show()`.
- [ ] Switch `shared_features` from in-place dict mutation to atomic frame snapshot swapping.
- [ ] Pass `float32` audio chunks from `LiveAudioInput` to `AudioAnalyzer` and add pre-gain hardware ADC clipping detection (`CLIP` indicator in web UI).
- [ ] Add deterministic software current estimation (`max_current_amps` limiter + live `AMPS` readout in web console).
- [ ] Add user-savable custom presets (`custom_presets.json`) and live audio input device selection in the web UI.

### Phase 11: Musical Intelligence & NIME Telemetry (Medium-Term)
- [ ] Add 8x-decimated sub-bass FFT (`6000 Hz`, `512` samples = `2.93 Hz/bin`) to resolve narrow low-frequency bands (`20–80 Hz`) without `argmin` bin collisions.
- [ ] Add parabolic log-magnitude FFT bin interpolation for continuous pitch glide.
- [ ] Add 12-bin chromagram mood tracking and spectral flatness timbre classification (bowed vs. plucked vs. percussive).
- [ ] Add UDP OSC server (`python-osc`, port `9000`) and Daisy Seed USB CDC serial / MIDI telemetry bridge (`scripts/daisy_bridge.py`).
- [ ] Support 2-channel independent stem routing in `LiveAudioInput` (Channel 1 = NIME lead pitch on Center Stage; Channel 2 = rhythm/kick on Layer 3).

### Phase 12: Spatial Mapping, Show Sync & Distributed Hardware (Long-Term)
- [ ] Add polyphonic 3-peak tracking (`Center`, `Left`, `Right` independent voice assignment) and Layer 3 velocity particle emitters.
- [ ] Add 2D `(x, y)` stage coordinate mapping with interactive strip placement in `stageCanvas` and 1D Sierra-Lite spatial dithering.
- [ ] Add USB MIDI controller surface support, MIDI Clock / Ableton Link phase lock with `5–25 ms` latency anticipation, and a real-time clock governor + `.show.json` cue recorder for `FileAudioInput`.
- [ ] Add UDP **DDP (port 4048)** and **Art-Net / E1.31 sACN** output drivers to stream 60 FPS pixel frames to wireless ESP32 WLED nodes and venue DMX fixtures.
- [ ] Build a `74AHCT125` 5V level-shifter + TVS protection carrier board and optional multi-channel local DMA output (`PCM_DOUT` + `PWM0`/`PWM1` + `SPI0`).

---

## 10. Development & Dependency Rules Reminder

When implementing items from this roadmap, preserve the repository constraints documented in [`AGENTS.md`](./AGENTS.md) and [`HANDOFF.md`](./HANDOFF.md):
- Manage all dependencies in `pixi.toml` (`linux-aarch64` and `osx-arm64`). Place Raspberry Pi hardware libraries (`rpi-ws281x`, `Pi5Neo`, `spidev`) strictly under `[target.linux-aarch64.pypi-dependencies]`; do not use `pyproject.toml` or PEP 508 markers.
- Keep transient console overrides (`blackout`, `punt_mode`, `freeze_mode`, `blinder_until`, `swell_until`) in memory only so a reboot never starts the stage rig in blackout or freeze.
- Run `pixi run python -m unittest discover -s scripts/tests -v` and the standalone verification scripts (`test_complete_pipeline.py`, `test_spectrum_viz.py`, `test_40hz_isolation.py`, `test_instrument_range.py`, `test_led_viz.py`, `scripts/test_harmonics.py`) before merging changes.

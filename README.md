# nime-led-visuals

Audio-reactive LED visual system for Daisy Seed instrument output on Raspberry Pi 3B.

## Hardware

- **Raspberry Pi 3B** (controller)
- **3x WS2812B LED strips** (144 LEDs each, 3.2ft, 5V DC)
- **Total: 432 LEDs**
- **5V Power Supply**: 30A recommended (or 10A at 30% brightness)
- **USB Audio Interface** with INPUT capability (for audio capture from Daisy)
- **Logic Level Shifter** (3.3V to 5V) for reliable LED data signal
- **Audio Y-Splitter** (3.5mm stereo)

## Setup

### Installation

```bash
pixi install
```

### Wiring

LED strips are wired in parallel with separate GPIO pins for independent effects:
- Strip 1: GPIO 18
- Strip 2: GPIO 13
- Strip 3: GPIO 19

All strips share +5V and GND (star topology for power distribution).

**Critical:** Must use external 5V power supply; do not power strips from Pi GPIO.

## Usage

```bash
pixi run run-live
```

Analyzes audio from Daisy Seed in real-time and drives LED animations based on frequency bands:
- Bass (<200Hz) → Blue
- Mid (200-2000Hz) → Green
- High (>2000Hz) → Red

## Architecture

- `audio_analyzer.py`: Real-time FFT analysis of audio input
- `effects.py`: Visual effects mapped to audio features
- `config.py`: LED strip and GPIO configuration
- `main.py`: Main control loop

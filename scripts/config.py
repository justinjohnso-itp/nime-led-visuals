"""Configuration constants for nime-led-visuals"""

# LED Configuration
NUM_LEDS_PER_STRIP = 144
NUM_STRIPS = 3
LED_BRIGHTNESS = 0.85  # Applied in effects.py (perceptual correction) - NOT the hardware brightness parameter

# GPIO Pin (BCM numbering)
GPIO_PIN = 18  # All daisy-chained strips on GPIO 18

# Audio Configuration
SAMPLE_RATE = 48000
CHUNK_SIZE = 1024
AUDIO_OUTPUT_DEVICE = "hw:1,0"  # Headphones output (Raspberry Pi), survives reboots
# AUDIO_INPUT_DEVICE can be:
#   - int: explicit device index
#   - str: case-insensitive substring to match device name (e.g. "scarlett")
#   - None: auto-select first suitable input device
AUDIO_INPUT_DEVICE = "AB13X"  # AB13X USB Audio by name pattern

# Frequency Bands (Hz) - 5 legacy bands for compatibility
FREQ_BANDS = [
    (20, 90, "sub_bass"),       # Sub-bass: deep kick (red)
    (90, 250, "bass"),          # Bass: foundational low end (red-orange)
    (250, 1000, "low_mid"),     # Low-mid: presence (amber)
    (1000, 2500, "mid_high"),   # Mid-high: clarity (lowered from 4000)
    (2500, 20000, "treble"),    # Treble: hi-hats, cymbals (lowered from 4000)
]

# 32-band spectrum for smooth color mapping
# Logarithmically spaced from instrument's frequency range (20 Hz to 7040 Hz)
# Extended lower range to capture 30s Hz frequencies from NIME controller
import numpy as np
NUM_SPECTRUM_BANDS = 32
SPECTRUM_FREQS = np.logspace(np.log10(20), np.log10(7040), NUM_SPECTRUM_BANDS + 1)

# Legacy band definitions for compatibility (remapped to instrument range)
BASS_LOW = 20        # Extended lower limit (was C1 at 32.7 Hz)
BASS_HIGH = 250      # Upper bass range
MID_LOW = 250        # Low-mid range
MID_HIGH = 1000      # Mid range
HIGH_LOW = 1000      # High range
HIGH_HIGH = 7040     # B8 - highest note on instrument
FREQ_MIN = 20        # Extended to capture 30s Hz (was C1 at 32.7 Hz)
FREQ_MAX = 7040      # Highest playable note (B8)

# Audio Input Scaling
INPUT_GAIN = 100.0     # Aux cable input is often weak; increase to 100x for better signal

# Colors (RGB tuples) - mapped to frequency bands
COLORS = {
    'bass': (100, 50, 200),      # Purple for bass (warm, deep)
    'mid': (50, 200, 100),       # Green for mid (balanced)
    'high': (255, 150, 0),       # Orange for high (bright, piercing)
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'cyan': (0, 255, 255),
    'magenta': (255, 0, 255),
    'yellow': (255, 255, 0),
    'white': (255, 255, 255),
    'black': (0, 0, 0),
}

# Effect Settings
FPS_TARGET = 60              # Increased from 30 for smoother animation
SMOOTHING_FACTOR = 0.008     # Ultra-fast (0.008) - minimal smoothing for snappy response
BRIGHTNESS_EXPONENT = 1.5    # Log scaling for brightness (makes quiet moments darker, peaks brighter)
# NOTE: Perceptual brightness correction in effects.py uses CIE luminance to ensure all colors
# appear equally bright across the spectrum. Red is the baseline (1.0x), blues/cyans are dimmed.

# Attack/Decay Envelope for brightness (like a synthesizer ADSR)
ATTACK_TIME = 0.02           # How fast brightness jumps to a new peak (20ms = 1 frame at 60fps)
DECAY_TIME = 0.15            # How fast brightness falls back down (150ms = smooth falloff)

# Noise Gate (silence if below this threshold)
NOISE_GATE_THRESHOLD = 0.01   # Mute signals quieter than 1% RMS (lowered to catch quieter notes)

# Dominant Frequency Visualization Parameters
HUE_RANGE = 240              # Red (0°) to Blue (240°) covers bass to treble
EDGE_HUE_SHIFT = 120         # ±120° hue shift at edges (aggressive treble bleed for hi-hats/claps)
CORE_FRACTION_MIN = 0.2      # Minimum core width (20%, narrower for more edge bleed)
CORE_FRACTION_MAX = 0.5      # Maximum core width (50%, narrower for more edge bleed)
MIN_BRIGHTNESS = 0.0         # Fully off when silent
EDGE_FADE_RATE = 0.25        # Brightness fades to 75% at edges for more visible edge bleed
TRANSIENT_BOOST = 0.5        # Extra brightness boost for sudden volume increases (increased)

"""Configuration constants for nime-led-visuals"""

# LED Configuration
NUM_LEDS_PER_STRIP = 144
NUM_STRIPS = 3
LED_BRIGHTNESS = 0.85  # Applied in effects.py (perceptual correction) - NOT the hardware brightness parameter

# GPIO Pin (BCM numbering)
GPIO_PIN = 21  # All daisy-chained strips on GPIO 21 (pin 40) - GPIO18 was damaged

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
INPUT_GAIN = 15.0     # Librosa normalizes audio to quiet levels; use higher gain (15x)

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

# Web Server Configuration
WEB_PORT = 8080

# Live Runtime Tunable Parameters (shared across threads, editable via Web UI)
import json
import os
import threading

_PARAMS_LOCK = threading.Lock()
_RUNTIME_PARAMS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime_params.json")

DEFAULT_LIVE_PARAMS = {
    "brightness": float(LED_BRIGHTNESS),       # Master LED brightness (0.0 - 1.0)
    "response_intensity": 1.15,                # Pre-easing energy multiplier (0.1 - 3.0)
    "easing_exponent": 1.25,                   # Easing curve gamma: <1 softer/wider, 1 linear, >1 punchier peaks (0.25 - 3.5)
    "cluster_width": 1.10,                     # Adjacent band feathering multiplier (0.0 - 2.5)
    "root_focus": 0.80,                        # Weighting toward audible root frequencies 40-900Hz & root dominance (0.0 - 1.5)
    "root_real_estate": 1.65,                  # Spatial warp giving audible roots more physical LED strip real estate (1.0 - 2.8)
    "input_gain": float(INPUT_GAIN),           # Audio input gain multiplier (0.5 - 80.0)
    "noise_gate": float(NOISE_GATE_THRESHOLD), # Silence RMS threshold (0.0 - 0.25)
    "attack_speed": 0.65,                      # Spectrum rise smoothing factor (0.02 - 1.0)
    "decay_speed": 0.22,                       # Spectrum falloff smoothing factor (0.01 - 0.95)
    "peak_hold_decay": 0.82,                   # Running max decay rate per frame (0.40 - 0.995)
    "harmonic_suppression": 0.85,              # Suppresses overtones so root fundamentals dominate (0.0 - 1.0)
    "bass_boost": 2.2,                         # Low-frequency root boost (0.5 - 5.0)
    "bass_hue": 0.0,                           # Center (low freq) hue in degrees (0 - 360)
    "treble_hue": 240.0,                       # Edge (high freq) hue in degrees (0 - 360)
    "perceptual_correction": 1.0,              # Blend factor for perceptual luminance dimming (0.0 - 1.0)
}

PRESETS = {
    "live_roots": {
        "label": "Live Music Roots (Default)",
        "description": "Weights audible root notes (40–900 Hz) heavily and gives them ~75% of the LED strip real estate",
        "params": dict(DEFAULT_LIVE_PARAMS),
    },
    "live_band_punchy": {
        "label": "Punchy Band Mix",
        "description": "Fast transient attack, high contrast easing curve, strong bass/mid root lock for loud full bands",
        "params": {
            **DEFAULT_LIVE_PARAMS,
            "response_intensity": 1.25,
            "easing_exponent": 1.55,
            "cluster_width": 1.0,
            "root_focus": 0.95,
            "root_real_estate": 1.80,
            "harmonic_suppression": 0.75,
            "attack_speed": 0.78,
            "decay_speed": 0.30,
            "input_gain": 12.0,
        },
    },
    "wide_root_bloom": {
        "label": "Massive Root Bloom",
        "description": "Extra-wide root clusters that fill the strips with smooth, weighty movement",
        "params": {
            **DEFAULT_LIVE_PARAMS,
            "brightness": 0.95,
            "response_intensity": 1.30,
            "easing_exponent": 0.90,
            "cluster_width": 1.45,
            "root_focus": 1.0,
            "root_real_estate": 1.95,
            "attack_speed": 0.45,
            "decay_speed": 0.12,
        },
    },
    "nime_linear": {
        "label": "NIME Original (Linear)",
        "description": "Original unwarped 32-band mapping for single-instrument sweeps",
        "params": {
            **DEFAULT_LIVE_PARAMS,
            "response_intensity": 1.0,
            "easing_exponent": 1.0,
            "cluster_width": 1.0,
            "root_focus": 0.0,
            "root_real_estate": 1.0,
            "harmonic_suppression": 1.0,
            "bass_boost": 2.0,
            "attack_speed": 0.60,
            "decay_speed": 0.20,
            "peak_hold_decay": 0.80,
        },
    },
}

LIVE_PARAMS = dict(DEFAULT_LIVE_PARAMS)


def load_live_params() -> dict:
    """Load persisted runtime parameters if present."""
    with _PARAMS_LOCK:
        if os.path.exists(_RUNTIME_PARAMS_FILE):
            try:
                with open(_RUNTIME_PARAMS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for k, default_val in DEFAULT_LIVE_PARAMS.items():
                    if k in saved and isinstance(saved[k], (int, float)):
                        LIVE_PARAMS[k] = float(saved[k])
            except Exception as e:
                print(f"Warning: could not load runtime_params.json: {e}")
        return dict(LIVE_PARAMS)


def get_live_params() -> dict:
    """Return a snapshot copy of current live parameters."""
    with _PARAMS_LOCK:
        return dict(LIVE_PARAMS)


def update_live_params(updates: dict, persist: bool = True) -> dict:
    """Validate, clamp, and apply live parameter updates."""
    bounds = {
        "brightness": (0.0, 1.0),
        "response_intensity": (0.1, 3.0),
        "easing_exponent": (0.25, 3.5),
        "cluster_width": (0.0, 2.5),
        "root_focus": (0.0, 1.5),
        "root_real_estate": (1.0, 2.8),
        "input_gain": (0.5, 80.0),
        "noise_gate": (0.0, 0.25),
        "attack_speed": (0.02, 1.0),
        "decay_speed": (0.01, 0.95),
        "peak_hold_decay": (0.40, 0.995),
        "harmonic_suppression": (0.0, 1.0),
        "bass_boost": (0.5, 5.0),
        "bass_hue": (0.0, 360.0),
        "treble_hue": (0.0, 360.0),
        "perceptual_correction": (0.0, 1.0),
    }
    with _PARAMS_LOCK:
        for k, v in updates.items():
            if k in DEFAULT_LIVE_PARAMS and isinstance(v, (int, float)):
                lo, hi = bounds.get(k, (-1e9, 1e9))
                LIVE_PARAMS[k] = float(max(lo, min(hi, float(v))))
        if persist:
            try:
                with open(_RUNTIME_PARAMS_FILE, "w", encoding="utf-8") as f:
                    json.dump(LIVE_PARAMS, f, indent=2)
            except Exception as e:
                print(f"Warning: could not save runtime_params.json: {e}")
        return dict(LIVE_PARAMS)


def reset_live_params(persist: bool = True) -> dict:
    """Reset all live parameters to DEFAULT_LIVE_PARAMS."""
    with _PARAMS_LOCK:
        LIVE_PARAMS.clear()
        LIVE_PARAMS.update(DEFAULT_LIVE_PARAMS)
        if persist and os.path.exists(_RUNTIME_PARAMS_FILE):
            try:
                os.remove(_RUNTIME_PARAMS_FILE)
            except Exception:
                pass
        return dict(LIVE_PARAMS)


load_live_params()


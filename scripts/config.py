"""Configuration constants for nime-led-visuals"""

# LED Configuration
NUM_LEDS_PER_STRIP = 144
NUM_STRIPS = 3
LED_BRIGHTNESS = 0.4

# GPIO Pin (BCM numbering)
GPIO_PIN = 18  # All daisy-chained strips on GPIO 18

# Audio Configuration
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024
AUDIO_OUTPUT_DEVICE = "hw:1,0"  # Headphones output (Raspberry Pi), survives reboots
AUDIO_INPUT_DEVICE = 1  # Focusrite 2i2 USB (from sounddevice.query_devices())

# Frequency Bands (Hz) - Rebalanced for even contribution
BASS_LOW = 20
BASS_HIGH = 250      # Slightly wider for better bass presence
MID_LOW = 250
MID_HIGH = 4000      # Wider mid range but less dominant
HIGH_LOW = 4000
HIGH_HIGH = 20000
FREQ_MIN = 20        # Sub-bass floor
FREQ_MAX = 20000     # Treble ceiling

# Audio Input Scaling
INPUT_GAIN = 5.0     # Amplify quiet input signals (5x gain)

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

# Attack/Decay Envelope for brightness (like a synthesizer ADSR)
ATTACK_TIME = 0.02           # How fast brightness jumps to a new peak (20ms = 1 frame at 60fps)
DECAY_TIME = 0.15            # How fast brightness falls back down (150ms = smooth falloff)

# Noise Gate (silence if below this threshold)
NOISE_GATE_THRESHOLD = 0.02   # Mute signals quieter than 2% RMS to kill input noise

# Dominant Frequency Visualization Parameters
HUE_RANGE = 240              # Red (0°) to Blue (240°) covers bass to treble
EDGE_HUE_SHIFT = 40          # ±40° hue shift at edges (adjacent frequency blending)
CORE_FRACTION_MIN = 0.4      # Minimum core width (40%, for narrow tones)
CORE_FRACTION_MAX = 0.8      # Maximum core width (80%, for broad spectrum)
MIN_BRIGHTNESS = 0.01        # Even lower floor (nearly off) for maximum contrast
EDGE_FADE_RATE = 0.4         # Brightness fades to 60% at edges
TRANSIENT_BOOST = 0.5        # Extra brightness boost for sudden volume increases (increased)

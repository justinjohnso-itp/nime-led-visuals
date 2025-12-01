"""Configuration constants for nime-led-visuals"""

# LED Configuration
NUM_LEDS_PER_STRIP = 144
NUM_STRIPS = 3
LED_BRIGHTNESS = 1.0  # 100% for testing (reduce to 0.3 once confirmed working)

# GPIO Pin (BCM numbering)
GPIO_PIN = 18  # All daisy-chained strips on GPIO 18

# Audio Configuration
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024
AUDIO_OUTPUT_DEVICE = "hw:1,0"  # Headphones output (Raspberry Pi), survives reboots
AUDIO_INPUT_DEVICE = 1  # Focusrite 2i2 USB (from sounddevice.query_devices())

# Frequency Bands (Hz)
BASS_LOW = 20
BASS_HIGH = 200
MID_LOW = 200
MID_HIGH = 2000
HIGH_LOW = 2000
HIGH_HIGH = 20000
FREQ_MIN = 20        # Sub-bass floor
FREQ_MAX = 20000     # Treble ceiling

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
FPS_TARGET = 30
SMOOTHING_FACTOR = 0.2  # 0.0-1.0, higher = snappier response

# Dominant Frequency Visualization Parameters
HUE_RANGE = 240              # Red (0°) to Blue (240°) covers bass to treble
EDGE_HUE_SHIFT = 40          # ±40° hue shift at edges (adjacent frequency blending)
CORE_FRACTION_MIN = 0.4      # Minimum core width (40%, for narrow tones)
CORE_FRACTION_MAX = 0.8      # Maximum core width (80%, for broad spectrum)
MIN_BRIGHTNESS = 0.3         # Keep colors visible even in quiet passages
EDGE_FADE_RATE = 0.4         # Brightness fades to 60% at edges

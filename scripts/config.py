"""Configuration constants for nime-led-visuals"""

# LED Configuration
NUM_LEDS_PER_STRIP = 144
NUM_STRIPS = 3
LED_BRIGHTNESS = 0.3  # 30% to save power

# GPIO Pin (BCM numbering)
GPIO_PIN = 18  # All daisy-chained strips on GPIO 18

# Audio Configuration
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024
AUDIO_DEVICE = "default"  # ALSA device (configured in ~/.asoundrc), or None for system default

# Frequency Bands (Hz)
BASS_LOW = 20
BASS_HIGH = 200
MID_LOW = 200
MID_HIGH = 2000
HIGH_LOW = 2000
HIGH_HIGH = 20000

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
SMOOTHING_FACTOR = 0.1  # 0.0-1.0, lower = more smoothing

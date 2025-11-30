# 💻 Code Implementation Guide

## 📂 Project Structure

```
nime-led-visuals/
├── pyproject.toml          # Poetry config
├── poetry.lock
├── README.md
├── HARDWARE_SETUP.md       # Physical wiring (companion doc)
├── CODE_GUIDE.md          # This file
├── scripts/
│   ├── main.py            # Main loop (integration of all modules)
│   ├── audio_input.py     # File/live audio abstraction
│   ├── audio_analyzer.py  # FFT and feature extraction
│   ├── effects.py         # Visual effect mapping
│   ├── config.py          # Configuration constants
│   ├── test_leds.py       # Hardware verification test
│   └── test_audio.py      # Audio input and analysis test
└── test.mp3              # Sample MP3 for testing tonight
```

---

## 🚀 Step-by-Step Code Implementation

### Phase 1: Project Setup

**Step 1.1: Initialize Poetry**
```bash
mkdir nime-led-visuals
cd nime-led-visuals
poetry init
# Follow prompts, use defaults
```

**Step 1.2: Add dependencies**
```bash
# Core LED libraries (same as your looper.py)
poetry add rpi-ws281x
poetry add adafruit-circuitpython-neopixel
poetry add adafruit-circuitpython-led-animation

# Audio processing
poetry add sounddevice numpy scipy

# File input (for testing with MP3s tonight)
poetry add librosa
```

---

### Phase 2: Create config.py

**What to code:**
Create `config.py` with all your constants.

**Include:**
- GPIO pins for LED strips
- Number of LEDs per strip
- Brightness setting
- Audio sample rate, chunk size
- Frequency band ranges (bass/mid/high cutoffs)
- Color palette definitions

**Example structure:**
```python
# config.py skeleton
# LED Configuration
NUM_LEDS_PER_STRIP = 144
NUM_STRIPS = 3
LED_BRIGHTNESS = 0.3  # 30% to save power

# GPIO Pins (BCM numbering)
# Use GPIO 18, 13, 19 (PWM-capable)

# Audio Configuration
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024  # Adjust for responsiveness

# Frequency Bands (Hz)
# Define where bass/mid/high split

# Colors
# Define your color palette
```

---

### Phase 3: Test LEDs (test_leds.py)

**What to code:**
Simple script to verify LED hardware works.

**Your task:**
1. Import `board` and `neopixel`
2. Import your `config.py` constants
3. Create NeoPixel object(s) - decide:
   - **Option A:** Single strip of 432 LEDs (daisy-chained)
   - **Option B:** Three separate 144-LED strips (parallel)
4. Test patterns:
   - Fill all LEDs red, then green, then blue
   - Chase pattern (similar to Comet from your looper.py)
   - Verify all 432 LEDs respond

**Run:**
```bash
poetry run sudo python test_leds.py
```

**Expected result:** All LEDs light up, no flickering, correct colors

---

### Phase 3b: Audio Input Abstraction (audio_input.py)

**What to code:**
Module that abstracts between file and live audio sources. This lets you test tonight with MP3s and switch to live input tomorrow.

**Your task:**
Create `audio_input.py` with:
1. `AudioInput` base class with `read_chunk()` and `close()` methods
2. `FileAudioInput` - read from MP3 using librosa (for testing tonight)
3. `LiveAudioInput` - read from USB interface using sounddevice (for tomorrow)
4. `get_audio_input()` factory function

**Key benefit:** One interface for both sources - just swap one line to change input.

**Example usage:**
```python
# Tonight: file input
audio = get_audio_input(source="file", filepath="test.mp3")

# Tomorrow: live input
audio = get_audio_input(source="live", device=0)
```

---

### Phase 4: Test Audio Input (test_audio.py)

**What to code:**
Script to verify audio analysis works.

**Your task:**
1. Import `audio_input` and `audio_analyzer`
2. Create audio input (start with file mode)
3. Loop:
   - Read chunk from audio input
   - Analyze with audio_analyzer
   - Print features (volume, bass, mid, high)

**Tonight:** Point to an MP3 file
**Tomorrow:** Change `source="live"` to use USB input

**Expected result:** Console shows changing numbers, matching what you're playing

---

### Phase 5: Audio Analysis (audio_analyzer.py)

**What to code:**
Module with functions to extract musical features from audio.

**Functions to write:**

**Function 1: `get_rms(audio_data)`**
- Takes raw audio samples (numpy array)
- Returns volume level (0.0 to 1.0)
- Use: `np.sqrt(np.mean(audio_data**2))`

**Function 2: `get_frequency_bands(audio_data, sample_rate)`**
- Takes audio samples and sample rate
- Performs FFT: `np.fft.rfft(audio_data)`
- Splits into bands:
  - Bass: 0-200 Hz
  - Mid: 200-2000 Hz  
  - High: 2000+ Hz
- Returns dict: `{'bass': 0.0-1.0, 'mid': 0.0-1.0, 'high': 0.0-1.0}`

**Function 3: `get_audio_features(audio_data, sample_rate)`**
- Combines RMS + frequency bands
- Returns complete feature dict
- This is what your main loop will call

**Libraries to use:**
- `numpy.fft.rfft()` for FFT
- `numpy.fft.rfftfreq()` for frequency bins
- `np.abs()` for magnitudes

---

### Phase 6: Visual Effects (effects.py)

**What to code:**
Functions that map audio features → LED patterns.

**Effect 1: `vu_meter(strip, volume)`**
- Light up LEDs from start based on volume
- Low volume = few LEDs, high volume = many LEDs
- Similar to classic VU meter

**Effect 2: `frequency_spectrum(strip1, strip2, strip3, bands)`**
- Each strip shows different frequency band
- Strip 1 = bass (blue)
- Strip 2 = mid (green)
- Strip 3 = high (red)
- Number of LEDs lit = energy in that band

**Effect 3: `pulse_effect(strip, volume, color)`**
- Entire strip pulses brightness with volume
- Like breathing with the music
- Use the color library from adafruit_led_animation

**Effect 4: `waveform_viz(strip, audio_data)`**
- Downsample audio waveform to LED count
- Each LED represents amplitude at that point in time
- Creates visual "oscilloscope" effect

**Effect 5: `comet_reactive(strip, features)`**
- Use `Comet` from adafruit_led_animation (like your looper.py!)
- Speed based on volume
- Color based on dominant frequency
- Multiple comets if using PixelSubset

**Your choice:** Pick 2-3 effects to implement, you can add more later

---

### Phase 7: Main Loop (main.py)

**What to code:**
The main script that ties everything together.

**Structure (similar to your looper.py):**

```python
# Pseudocode structure
import config
import audio_analyzer
import effects
import board
import neopixel
import sounddevice as sd

# Initialize LEDs (like looper.py)
# pixels = neopixel.NeoPixel(...)

# Set up audio stream
# stream = sd.InputStream(...)

try:
    while True:
        # 1. Read audio (like your GPIO.input() but for audio)
        # audio_chunk = read from stream
        
        # 2. Analyze (like checking button states)
        # features = audio_analyzer.get_audio_features(audio_chunk)
        
        # 3. Map to visual (like your set_volume() logic)
        # color = map features to color
        
        # 4. Update LEDs (like your animations.animate())
        # effects.frequency_spectrum(strip1, strip2, strip3, features)
        # strips.show()
        
        # 5. Control frame rate
        # sleep or rely on audio blocking

except KeyboardInterrupt:
    # Cleanup (like your finally: GPIO.cleanup())
    # Turn off LEDs
    # Close audio stream
```

**Key differences from looper.py:**
- Instead of `GPIO.input()` → use audio stream read
- Instead of `set_volume()` → update LED colors/brightness
- Instead of pre-loaded sounds → live audio analysis

---

## 🎯 Implementation Strategy

### Minimal Viable Product (30 min coding)
1. `config.py` - Just the basics
2. `test_leds.py` - Solid color test
3. `main.py` - Read audio, map volume → brightness

### Audio-Reactive v1 (1 hour coding)
4. `audio_analyzer.py` - Add RMS calculation
5. `main.py` - Update: volume → LED brightness
6. Should pulse with your playing!

### Multi-Band Reactive v2 (1.5 hours coding)
7. `audio_analyzer.py` - Add FFT and frequency bands
8. `effects.py` - Create spectrum effect
9. `main.py` - Use 3 strips for bass/mid/high

### Polished Performance Ready (2+ hours coding)
10. Add multiple effect modes
11. Add smoothing/filtering
12. Add beat detection
13. Optimize performance

---

## 🔑 Key Code Patterns

### Pattern 1: Audio Stream Setup (sounddevice)
```python
# Unlike pygame.mixer which plays sounds,
# sounddevice captures audio in real-time

import sounddevice as sd

def audio_callback(indata, frames, time, status):
    """Called automatically when audio arrives"""
    # indata is numpy array of audio samples
    # Process here or store in queue
    pass

stream = sd.InputStream(
    channels=1,
    samplerate=44100,
    callback=audio_callback
)
stream.start()
```

### Pattern 2: NeoPixel Update (from your looper.py)
```python
# You already know this!
import board
import neopixel

pixels = neopixel.NeoPixel(
    board.D18, 
    144, 
    brightness=0.3,
    auto_write=False  # Manual control like your looper
)

# Update LEDs
for i in range(144):
    pixels[i] = (r, g, b)
pixels.show()  # Push to hardware
```

### Pattern 3: Using adafruit_led_animation (from looper.py)
```python
# You're already familiar with this!
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.color import *

comet = Comet(pixels, speed=0.1, color=BLUE, tail_length=20)

# In loop:
comet.animate()  # Just like your looper.py
```

---

## 💡 Suggested Coding Order

1. **Start with `config.py`** - Define all constants
2. **Write `test_leds.py`** - Verify hardware (solid colors only)
3. **Write `test_audio.py`** - Verify audio input (print RMS only)
4. **Write `audio_analyzer.py`** - Start with just RMS function
5. **Write simple `main.py`** - Volume → brightness only
6. **Test end-to-end** - Play instrument, LEDs should pulse!
7. **Expand `audio_analyzer.py`** - Add FFT and frequency bands
8. **Write `effects.py`** - Add visual mapping functions
9. **Enhance `main.py`** - Use frequency-reactive effects
10. **Polish** - Add smoothing, multiple modes, etc.

---

## 🎨 Effect Ideas Tailored to Your Instrument

### Effect: Envelope Follower
- Match your instrument's 50ms attack / 150ms release
- LEDs fade in/out with notes
- Feels connected to playing

### Effect: Scale-Aware Colors
- Major Pentatonic = warm colors (orange/red)
- Minor Pentatonic = cool colors (blue/purple)
- Chromatic = rainbow cycling
- Would need serial communication from Daisy or infer from audio

### Effect: Window Position Indicator
- Show window offset as position on strip
- Center LED = no offset
- Left side = negative offset
- Right side = positive offset

### Effect: Mode Visualization
- Different pattern per mode:
  - Single Note = VU meter
  - Chord = 3 pulses (root/3rd/5th positions)
  - Arpeggio = chasing lights at 140ms tempo
  - Latch = sustained glow

---

## 🧪 Testing Approach

### Test 1: Hardware Only (test_leds.py)
```python
# Just verify strips light up
# No audio needed yet
```

### Test 2: Audio + File Input (test_audio.py with MP3)
```bash
# Use audio_input.py with FileAudioInput source
poetry run python scripts/test_audio.py

# Point to an MP3 file for testing TONIGHT
# No USB audio interface needed yet
audio = get_audio_input(source="file", filepath="test.mp3")
```

### Test 3: Switch to Live Input (1 line change)
```bash
# Tomorrow when you have the USB interface connected:
audio = get_audio_input(source="live", device=0)

# Everything else stays the same!
# No code refactoring needed
```

### Test 4: Volume Reactive (main.py v1)
```python
# Volume → brightness
# Simplest audio-reactive behavior
# Works with both file and live input
```

### Test 5: Frequency Reactive (main.py v2)
```python
# FFT → colors or strip assignment
# More interesting, still simple
```

### Test 6: Full Effects (main.py v3)
```python
# Use adafruit_led_animation
# Multiple effect modes
# Production ready
```

---

## 📚 Libraries You'll Use

### Familiar (from looper.py)
- `board` - GPIO pin definitions
- `neopixel` - WS2812B control
- `adafruit_led_animation` - Comet, AnimationGroup, etc.
- `adafruit_led_animation.color` - Color constants

### New for this project
- `sounddevice` - Audio input (better than pygame for capture)
- `numpy` - Audio data processing, FFT
- `scipy` - Advanced audio analysis (optional)

### Why not pygame.mixer?
- pygame.mixer is great for **playback** (your looper.py)
- For audio **capture**, sounddevice is much simpler
- But you can use pygame for other things if you want!

---

## 🎯 Minimal First Script Template

**Goal:** Get something working in 30 minutes

**What you'll code in `main.py` (v1):**
1. Import neopixel, sounddevice, numpy
2. Initialize LEDs (one strip or three, your choice)
3. Set up audio input stream
4. Loop:
   - Read audio chunk
   - Calculate RMS
   - Map RMS to brightness (0.0-1.0)
   - Set all LEDs to single color with that brightness
   - Show LEDs
5. Cleanup on Ctrl+C

**Run:**
```bash
poetry run sudo python main.py
```

**Expected:** LEDs pulse brighter when you play louder!

---

## 🔧 Development Tips

### Tip 1: Start Simple
- Don't try to do everything at once
- Get volume → brightness working first
- Add complexity incrementally

### Tip 2: Use Your looper.py Patterns
- You already know NeoPixel and animations
- Comet, AnimationGroup, PixelSubset all work the same
- Just replace GPIO button checks with audio features

### Tip 3: Debugging
- Print audio features to console
- Test effects with fake data first
- Verify one thing at a time (LEDs, then audio, then combine)

### Tip 4: Performance
- `auto_write=False` and manual `show()` for control
- Limit FPS (30-60 is plenty)
- Reduce brightness if CPU struggles

---

## 📖 Code Examples to Get You Started

### Example 1: Basic NeoPixel Setup (You Know This!)
```python
import board
import neopixel

# Daisy-chained (all 432 as one strip)
pixels = neopixel.NeoPixel(board.D18, 432, brightness=0.3, auto_write=False)

# OR Parallel (three separate strips)
strip1 = neopixel.NeoPixel(board.D18, 144, brightness=0.3, auto_write=False)
strip2 = neopixel.NeoPixel(board.D13, 144, brightness=0.3, auto_write=False)
strip3 = neopixel.NeoPixel(board.D19, 144, brightness=0.3, auto_write=False)
```

### Example 2: Audio Input (New for You)
```python
import sounddevice as sd
import numpy as np

# Callback function (called automatically when audio arrives)
def audio_callback(indata, frames, time, status):
    # indata is a numpy array of audio samples
    # indata.shape = (CHUNK_SIZE, CHANNELS)
    audio_data = indata[:, 0]  # Get first channel if stereo
    
    # Calculate volume
    rms = np.sqrt(np.mean(audio_data**2))
    print(f"Volume: {rms:.0f}")

# Start audio stream
stream = sd.InputStream(
    channels=1,           # Mono
    samplerate=44100,
    blocksize=1024,       # CHUNK_SIZE
    callback=audio_callback
)

stream.start()
# Stream runs in background, callback fires automatically
```

### Example 3: Simple FFT (Frequency Analysis)
```python
import numpy as np

def analyze_frequencies(audio_data, sample_rate):
    # Perform FFT
    fft_result = np.fft.rfft(audio_data)
    frequencies = np.fft.rfftfreq(len(audio_data), 1/sample_rate)
    magnitudes = np.abs(fft_result)
    
    # Get bass energy (0-200 Hz)
    bass_mask = frequencies < 200
    bass_energy = np.mean(magnitudes[bass_mask])
    
    # Get mid energy (200-2000 Hz)
    mid_mask = (frequencies >= 200) & (frequencies < 2000)
    mid_energy = np.mean(magnitudes[mid_mask])
    
    # Get high energy (2000+ Hz)
    high_mask = frequencies >= 2000
    high_energy = np.mean(magnitudes[high_mask])
    
    return bass_energy, mid_energy, high_energy
```

### Example 4: Map to LED Color
```python
def audio_to_color(bass, mid, high):
    # Map frequency bands to RGB
    r = int(high * 255)   # High freq = red
    g = int(mid * 255)    # Mid freq = green
    b = int(bass * 255)   # Bass = blue
    return (r, g, b)
```

---

## 🎨 Visual Effect Suggestions

### Effect Option 1: Three-Band Spectrum (Recommended First)
Each strip shows a different frequency band - easiest to implement and very visual.

**What to code:**
- Strip 1: Bass bar graph (blue)
- Strip 2: Mid bar graph (green)
- Strip 3: High bar graph (red)
- Height based on energy in that band

### Effect Option 2: Unified Pulse
All strips same color, brightness follows volume - simplest to implement.

**What to code:**
- Read volume
- Set all LEDs to single color
- Brightness = volume level

### Effect Option 3: Reactive Comet (Like looper.py!)
Use Comet animation but control speed with audio.

**What to code:**
- Create Comet objects (you know this!)
- Adjust `speed` parameter based on volume or frequency
- Faster comets when louder

### Effect Option 4: Note Attack Flash
Detect sudden volume increases (note onsets) and flash white.

**What to code:**
- Track previous volume
- If `current_volume - previous_volume > threshold`: flash white
- Fades back to normal color
- Matches your instrument's envelope feel

---

## 🧩 Putting It Together

### Your coding workflow:

1. **Day 1: Setup & Testing**
   - Poetry setup
   - Write config.py
   - Write and test test_leds.py
   - Write and test test_audio.py
   - **Goal:** Verify hardware works

2. **Day 2: Basic Reactive**
   - Write audio_analyzer.py (RMS only)
   - Write simple main.py (volume → brightness)
   - **Goal:** LEDs pulse with playing

3. **Day 3: Frequency Reactive**
   - Expand audio_analyzer.py (add FFT)
   - Write effects.py (frequency spectrum)
   - Update main.py to use effects
   - **Goal:** Different colors for different sounds

4. **Day 4: Polish**
   - Add multiple effects
   - Add smoothing
   - Optimize performance
   - **Goal:** Performance ready

---

## ⚙️ Configuration You'll Need to Tune

### Audio Settings (in config.py)
- `CHUNK_SIZE`: 512 (responsive) vs 2048 (smooth)
- `SAMPLE_RATE`: 44100 (CD quality) vs 22050 (lower CPU)

### Visual Settings (in config.py)
- `LED_BRIGHTNESS`: 0.3 (safe) vs 1.0 (full power)
- `FPS_TARGET`: 30 (smooth) vs 60 (very smooth, higher CPU)
- `SMOOTHING_FACTOR`: 0.1-0.5 (prevent flickering)

### Frequency Bands (in config.py)
- Tune bass/mid/high ranges based on your instrument
- Your instrument is mostly 200-2000 Hz range
- May want narrower bands for better visualization

---

## 🚀 Quick Start Commands

```bash
# Create project
mkdir nime-led-visuals && cd nime-led-visuals
poetry init

# Add dependencies
poetry add rpi-ws281x adafruit-circuitpython-neopixel
poetry add adafruit-circuitpython-led-animations
poetry add sounddevice numpy scipy

# Test LEDs (write this script)
poetry run sudo python test_leds.py

# Test audio (write this script)
poetry run sudo python test_audio.py

# Run main (write this script)
poetry run sudo python main.py
```

---

## 📚 Resources

**Adafruit LED Animation Guide:**
https://learn.adafruit.com/circuitpython-led-animations

**sounddevice Documentation:**
https://python-sounddevice.readthedocs.io/

**NumPy FFT Tutorial:**
https://numpy.org/doc/stable/reference/routines.fft.html

---

Ready to start? Begin with Phase 1 (Poetry setup) and let me know when you're ready for the next phase!

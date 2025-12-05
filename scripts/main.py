#!/usr/bin/env python3
"""Main loop for audio-reactive LED visuals with threading"""

import time
import sys
import platform
import threading
import numpy as np
import subprocess
import os

from config import NUM_LEDS_PER_STRIP, NUM_STRIPS, LED_BRIGHTNESS, SAMPLE_RATE, CHUNK_SIZE, AUDIO_INPUT_DEVICE
from audio_input import get_audio_input
from audio_analyzer import AudioAnalyzer

# Only import LED libraries on Linux (Raspberry Pi)
if platform.system() == 'Linux':
    import board
    import neopixel
    from adafruit_led_animation.helper import PixelSubset
    from effects import LEDEffects
    HAS_LEDS = True
else:
    HAS_LEDS = False


def initialize_strips():
    """Create NeoPixel strip with subsets for daisy-chained segments"""
    import sys
    print(f"  Python: {sys.executable}")
    print(f"  neopixel module: {neopixel.__file__}")
    
    total_leds = NUM_LEDS_PER_STRIP * NUM_STRIPS
    print(f"  Total LEDs: {total_leds} ({NUM_STRIPS} strips x {NUM_LEDS_PER_STRIP})")
    
    # Single NeoPixel on GPIO 18 for all daisy-chained LEDs
    # Set hardware brightness to 1.0 (max) - all brightness control is done in effects.py
    # via the LED_BRIGHTNESS config and perceptual correction in get_perceptual_brightness_correction()
    pixels = neopixel.NeoPixel(
        board.D18,
        total_leds,
        brightness=1.0,
        auto_write=False
    )
    print(f"  len(pixels) = {len(pixels)}")
    
    # Create PixelSubset for each daisy-chained strip segment
    strips = [
        PixelSubset(pixels, 0, NUM_LEDS_PER_STRIP),
        PixelSubset(pixels, NUM_LEDS_PER_STRIP, 2 * NUM_LEDS_PER_STRIP),
        PixelSubset(pixels, 2 * NUM_LEDS_PER_STRIP, 3 * NUM_LEDS_PER_STRIP)
    ]
    print(f"  Strip lengths: {len(strips[0])}, {len(strips[1])}, {len(strips[2])}")
    
    return pixels, strips


def audio_thread_func(audio, analyzer, shared_features, stop_event):
    """Continuously read and analyze audio without waiting for LED updates
    
    Args:
        audio: audio input source
        analyzer: AudioAnalyzer instance
        shared_features: dict to store latest features for LED thread
        stop_event: threading.Event to signal shutdown
    """
    try:
        while not stop_event.is_set():
            # Read audio chunk
            chunk = audio.read_chunk()
            
            # Analyze audio features
            features = analyzer.analyze(chunk)
            
            # Store latest features (dict update is atomic in Python)
            shared_features.update(features)
            
            # No sleep - keep reading audio constantly
    except Exception as e:
        print(f"\n❌ Audio thread error: {e}")
    finally:
        audio.close()


def led_thread_func(pixels, strips, shared_features, stop_event):
    """Update LEDs periodically without blocking audio
    
    Args:
        pixels: main neopixel.NeoPixel object (for show() calls)
        strips: list of PixelSubset objects
        shared_features: dict with latest audio features
        stop_event: threading.Event to signal shutdown
    """
    print("💡 LED thread started")
    frame_count = 0
    try:
        while not stop_event.is_set():
            # Use latest features from audio thread
            LEDEffects.frequency_spectrum(strips, shared_features)
            
            # Show all changes at once (daisy-chained)
            pixels.show()
            
            frame_count += 1
            if frame_count == 1:
                print(f"💡 First LED frame rendered (total LEDs: {len(pixels)})")
            
            # LED updates at 60 FPS (16.67ms) - balance between responsiveness and CPU load
            time.sleep(0.01667)
    except Exception as e:
        print(f"\n❌ LED thread error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup LEDs
        pixels.fill((0, 0, 0))
        pixels.show()


def main(audio_source='live', filepath=None):
    """Main loop with audio and LED threads
    
    Args:
        audio_source: 'file' or 'live'
        filepath: path to MP3 file (required if audio_source='file')
    """
    if HAS_LEDS:
        print("🎨 Initializing LED strips...")
        pixels, strips = initialize_strips()
    else:
        print("📱 (No LEDs on this platform, audio analysis only)")
        pixels = None
        strips = None

    print("🎵 Initializing audio input...")
    audio = get_audio_input(source=audio_source, filepath=filepath, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE, device=AUDIO_INPUT_DEVICE)

    print("📊 Initializing audio analyzer...")
    analyzer = AudioAnalyzer(sample_rate=SAMPLE_RATE)
    
    # For file input, audio is pre-loaded by librosa - no playback needed
    if audio_source == 'file':
        print("🔊 Analyzing audio file...")

    # Shared state for communication between threads
    shared_features = {
        'volume': 0.0,
        'bass': 0.0,
        'mid': 0.0,
        'high': 0.0,
        'sub_bass': 0.0,
        'low_mid': 0.0,
        'mid_high': 0.0,
        'treble': 0.0,
        'centroid': 0.0,
        'bandwidth': 0.0,
        'transient': 0.0,
        'envelope': 0.0,
        'spectrum': None,  # 32-band spectrum
    }
    stop_event = threading.Event()

    print("▶️  Starting audio-reactive visualization...")
    print("   Press Ctrl+C to stop")
    print()  # Extra line for spectrum display

    # Start audio thread (continuous reading)
    audio_t = threading.Thread(
        target=audio_thread_func,
        args=(audio, analyzer, shared_features, stop_event),
        daemon=True,
        name="AudioThread"
    )
    audio_t.start()

    # Start LED thread (periodic updates)
    if HAS_LEDS:
        led_t = threading.Thread(
            target=led_thread_func,
            args=(pixels, strips, shared_features, stop_event),
            daemon=True,
            name="LEDThread"
        )
        led_t.start()

    # Main thread: print features and handle shutdown
    try:
        while True:
            spectrum = shared_features.get('spectrum', None)
            
            # ANSI colors
            RED = '\033[91m'
            BLUE = '\033[94m'
            RESET = '\033[0m'
            
            dominant_freq = shared_features.get('dominant_freq', 0.0)
            tonalness = shared_features.get('tonalness', 0.0)
            
            if spectrum is not None and len(spectrum) >= 32:
                # Visualize the actual 32-band spectrum with band-by-band brightness
                # Match the algorithm in effects.frequency_spectrum() for accuracy
                
                total_leds = NUM_LEDS_PER_STRIP * NUM_STRIPS
                center = total_leds // 2
                leds_per_side = total_leds // 2
                
                # Compress 216 LEDs per side to ~27 chars for display (8:1 compression)
                compression = 8
                display_width = (leds_per_side // compression)
                
                # Pre-compute brightness for each displayed position (matching effects.py exactly)
                displayed_brightness = []
                for display_i in range(display_width):
                    # Map display position back to actual LED position
                    led_pos = display_i * compression
                    
                    # Map position to band (matching band_map logic in effects.py)
                    if leds_per_side <= 1:
                        band_idx = 0
                        pos_in_band = 0.5
                    else:
                        band_frac = (led_pos + 0.5) * 31.0 / leds_per_side
                        band_idx = min(31, int(band_frac))
                        pos_in_band = band_frac - band_idx
                    
                    # Calculate brightness with feathering (matching effects.py)
                    distance_from_center = abs(pos_in_band - 0.5)
                    center_weight = max(0.0, 1.0 - distance_from_center * 0.4)  # Gentle falloff
                    feathered_energy = center_weight * float(spectrum[band_idx])
                    
                    # Feathering from adjacent bands
                    if band_idx > 0:
                        prev_weight = 0.50 * max(0.0, (pos_in_band - 0.0) / 0.50)
                        feathered_energy += prev_weight * float(spectrum[band_idx - 1])
                    if band_idx < 31:
                        next_weight = 0.50 * max(0.0, (1.0 - pos_in_band) / 0.50)
                        feathered_energy += next_weight * float(spectrum[band_idx + 1])
                    
                    if band_idx > 1:
                        prev2_weight = 0.35 * max(0.0, (pos_in_band - 0.0) / 0.50)
                        feathered_energy += prev2_weight * float(spectrum[band_idx - 2])
                    if band_idx < 30:
                        next2_weight = 0.35 * max(0.0, (1.0 - pos_in_band) / 0.50)
                        feathered_energy += next2_weight * float(spectrum[band_idx + 2])
                    
                    displayed_brightness.append(min(1.0, feathered_energy))
                
                # Display: one unified mirrored spectrum (center=red/bass to edges=blue/treble)
                # Treble←[CENTER: Bass]→Treble
                
                # Get hue for display position (matching effects.py)
                def get_hue_for_display_pos(dist_from_center):
                    """Get hue based on display distance from center (band mapping)"""
                    # dist_from_center ranges 0-26 (display width), scale to 31 bands
                    band_frac = (dist_from_center + 0.5) * 31.0 / display_width
                    band_idx = min(31, int(band_frac))
                    # Map band to hue (0° red at band 0, 240° blue at band 31)
                    if band_idx < 16:
                        return (band_idx / 16.0) * 30.0  # Red to orange
                    else:
                        return 180.0 + ((band_idx - 16) / 16.0) * 60.0  # Cyan to blue
                
                def char_for_brightness(brightness, hue):
                    """Return colored character based on brightness and hue"""
                    if hue < 90:  # Red/orange
                        if brightness > 0.7:
                            return f"{RED}█{RESET}"
                        elif brightness > 0.4:
                            return f"{RED}▓{RESET}"
                        elif brightness > 0.1:
                            return f"{RED}░{RESET}"
                    else:  # Cyan/blue
                        if brightness > 0.7:
                            return f"{BLUE}█{RESET}"
                        elif brightness > 0.4:
                            return f"{BLUE}▓{RESET}"
                        elif brightness > 0.1:
                            return f"{BLUE}░{RESET}"
                    return "·"
                
                # Build display: mirror left side (reversed), then right side (normal)
                output = "▐"
                
                # Left half: display_width-1 down to 0 (edges to center)
                for i in range(display_width - 1, -1, -1):
                    brightness = displayed_brightness[i]
                    hue = get_hue_for_display_pos(i)
                    output += char_for_brightness(brightness, hue)
                
                # Right half: 0 to display_width-1 (center to edges)
                for i in range(display_width):
                    brightness = displayed_brightness[i]
                    hue = get_hue_for_display_pos(i)
                    output += char_for_brightness(brightness, hue)
                
                output += "▐\n"
                
                # Second line: frequency and spectrum stats
                mean_spectrum = float(np.mean(spectrum))
                max_spectrum = float(np.max(spectrum))
                output += f"{dominant_freq:5.0f}Hz  T:{tonalness:.2f}  spectrum[avg:{mean_spectrum:.3f} max:{max_spectrum:.3f}]     "
            else:
                output = "Waiting...                        "
            
            print(output, end='\r', flush=True)
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
        stop_event.set()
        
        # Wait for threads to finish
        audio_t.join(timeout=2.0)
        if HAS_LEDS:
            led_t.join(timeout=2.0)
        
        print("✓ Done!")


if __name__ == '__main__':
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description='Audio-reactive LED visualization'
    )
    parser.add_argument(
        '--file',
        type=str,
        help='MP3 filename (looks in music/ directory by default)'
    )

    args = parser.parse_args()

    if args.file:
        # Try music/ directory first, then current directory
        filepath = args.file
        if not os.path.exists(filepath) and os.path.exists(f'music/{filepath}'):
            filepath = f'music/{filepath}'
        
        print(f"Using file input: {filepath}")
        main(audio_source='file', filepath=filepath)
    else:
        print("Using live audio input")
        main(audio_source='live')

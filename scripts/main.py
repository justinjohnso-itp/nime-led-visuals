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
    # Single NeoPixel on GPIO 18 for all daisy-chained LEDs
    pixels = neopixel.NeoPixel(
        board.D18,
        NUM_LEDS_PER_STRIP * NUM_STRIPS,
        brightness=LED_BRIGHTNESS,
        auto_write=False
    )
    
    # Create PixelSubset for each daisy-chained strip segment
    strips = [
        PixelSubset(pixels, 0, NUM_LEDS_PER_STRIP),
        PixelSubset(pixels, NUM_LEDS_PER_STRIP, 2 * NUM_LEDS_PER_STRIP),
        PixelSubset(pixels, 2 * NUM_LEDS_PER_STRIP, 3 * NUM_LEDS_PER_STRIP)
    ]
    
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
    try:
        while not stop_event.is_set():
            # Use latest features from audio thread
            LEDEffects.frequency_spectrum(strips, shared_features)
            
            # Show all changes at once (daisy-chained)
            pixels.show()
            
            # LED updates at 60 FPS (16.67ms) - balance between responsiveness and CPU load
            time.sleep(0.01667)
    except Exception as e:
        print(f"\n❌ LED thread error: {e}")
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
        'envelope': 0.0
    }
    stop_event = threading.Event()

    print("▶️  Starting audio-reactive visualization...")
    print("   Press Ctrl+C to stop")

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
            # Create ASCII spectrum visualizer with 5 bands
            sub_bass = shared_features['sub_bass']
            bass = shared_features['bass']
            low_mid = shared_features['low_mid']
            mid_high = shared_features['mid_high']
            treble = shared_features['treble']
            transient = shared_features['transient']
            volume = shared_features['volume']
            envelope = shared_features['envelope']
            
            # Create bars (6 chars per band, fixed width, colored)
            bar_width = 6
            RED = '\033[91m'
            ORANGE = '\033[33m'
            GREEN = '\033[92m'
            BLUE = '\033[94m'
            RESET = '\033[0m'
            
            # Colored bars with monospace █
            sub_bass_bar = f"{RED}{'█' * int(sub_bass * bar_width)}{RESET}" + ' ' * (bar_width - int(sub_bass * bar_width))
            bass_bar = f"{RED}{'█' * int(bass * bar_width)}{RESET}" + ' ' * (bar_width - int(bass * bar_width))
            low_mid_bar = f"{ORANGE}{'█' * int(low_mid * bar_width)}{RESET}" + ' ' * (bar_width - int(low_mid * bar_width))
            mid_high_bar = f"{GREEN}{'█' * int(mid_high * bar_width)}{RESET}" + ' ' * (bar_width - int(mid_high * bar_width))
            treble_bar = f"{BLUE}{'█' * int(treble * bar_width)}{RESET}" + ' ' * (bar_width - int(treble * bar_width))
            
            # Transient indicator
            transient_char = '⚡' if transient > 0.05 else ' '
            
            # Create the display with fixed widths (all on one line)
            output = f"SUB [{sub_bass_bar}] "
            output += f"BASS [{bass_bar}] "
            output += f"L-MID [{low_mid_bar}] "
            output += f"M-HI [{mid_high_bar}] "
            output += f"TRE [{treble_bar}] "
            output += f"VOL:{volume:.2f} ENV:{envelope:.2f} {transient_char}"
            output += " " * 20  # Padding to clear previous output
            
            print(output, end='\r')
            time.sleep(0.1)  # Update display every 100ms

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

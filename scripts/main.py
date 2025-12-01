#!/usr/bin/env python3
"""Main loop for audio-reactive LED visuals with threading"""

import time
import sys
import platform
import threading
import numpy as np
import subprocess
import os

from config import GPIO_PINS, NUM_LEDS_PER_STRIP, LED_BRIGHTNESS, SAMPLE_RATE, CHUNK_SIZE
from audio_input import get_audio_input
from audio_analyzer import AudioAnalyzer

# Only import LED libraries on Linux (Raspberry Pi)
if platform.system() == 'Linux':
    import board
    import neopixel
    from effects import LEDEffects
    HAS_LEDS = True
else:
    HAS_LEDS = False


def initialize_strips():
    """Create NeoPixel objects for each strip"""
    strips = []
    for pin_name in ['D18', 'D13', 'D19']:
        pin = getattr(board, pin_name)
        strip = neopixel.NeoPixel(
            pin,
            NUM_LEDS_PER_STRIP,
            brightness=LED_BRIGHTNESS,
            auto_write=False
        )
        strips.append(strip)
    return strips


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


def led_thread_func(strips, shared_features, stop_event):
    """Update LEDs periodically without blocking audio
    
    Args:
        strips: list of neopixel.NeoPixel objects
        shared_features: dict with latest audio features
        stop_event: threading.Event to signal shutdown
    """
    try:
        while not stop_event.is_set():
            # Use latest features from audio thread
            LEDEffects.frequency_spectrum(strips, shared_features)
            
            # Fixed 20 FPS LED updates (50ms)
            time.sleep(0.05)
    except Exception as e:
        print(f"\n❌ LED thread error: {e}")
    finally:
        # Cleanup LEDs
        for strip in strips:
            strip.fill((0, 0, 0))
            strip.show()


def main(audio_source='live', filepath=None):
    """Main loop with audio and LED threads
    
    Args:
        audio_source: 'file' or 'live'
        filepath: path to MP3 file (required if audio_source='file')
    """
    if HAS_LEDS:
        print("🎨 Initializing LED strips...")
        strips = initialize_strips()
    else:
        print("📱 (No LEDs on this platform, audio analysis only)")
        strips = None

    print("🎵 Initializing audio input...")
    audio = get_audio_input(source=audio_source, filepath=filepath, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)

    print("📊 Initializing audio analyzer...")
    analyzer = AudioAnalyzer(sample_rate=SAMPLE_RATE)
    
    # Play audio file if provided
    if audio_source == 'file':
        if platform.system() == 'Darwin':
            subprocess.Popen(['afplay', filepath])
        elif platform.system() == 'Linux':
            ffmpeg_proc = subprocess.Popen(['ffmpeg', '-i', filepath, '-f', 's16le', '-ar', '44100', '-ac', '2', '-'], 
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            subprocess.Popen(['aplay', '-f', 'S16_LE', '-r', '44100', '-c', '2'], stdin=ffmpeg_proc.stdout, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            ffmpeg_proc.stdout.close()
        time.sleep(0.5)  # Give playback time to start
        print("🔊 Playing audio...")

    # Shared state for communication between threads
    shared_features = {
        'volume': 0.0,
        'bass': 0.0,
        'mid': 0.0,
        'high': 0.0
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
            args=(strips, shared_features, stop_event),
            daemon=True,
            name="LEDThread"
        )
        led_t.start()

    # Main thread: print features and handle shutdown
    try:
        while True:
            # Print current features for monitoring
            print(f"Volume: {shared_features['volume']:.3f} | Bass: {shared_features['bass']:.3f} | Mid: {shared_features['mid']:.3f} | High: {shared_features['high']:.3f}", end='\r')
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

#!/usr/bin/env python3
"""Main loop for audio-reactive LED visuals"""

import time
import sys
import platform
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


def main(audio_source='live', filepath=None):
    """Main loop
    
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

    print("▶️  Starting audio-reactive visualization...")
    print("   Press Ctrl+C to stop")

    try:
        while True:
            # Read audio chunk
            chunk = audio.read_chunk()

            # Analyze audio features
            features = analyzer.analyze(chunk)

            # Print features for testing
            print(f"Volume: {features['volume']:.3f} | Bass: {features['bass']:.3f} | Mid: {features['mid']:.3f} | High: {features['high']:.3f}", end='\r')

            # Apply LED effects only if available
            if HAS_LEDS:
                LEDEffects.frequency_spectrum(strips, features)

            # Small delay for frame rate
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
    finally:
        # Cleanup
        if HAS_LEDS:
            for strip in strips:
                strip.fill((0, 0, 0))
                strip.show()
        audio.close()
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

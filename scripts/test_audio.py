#!/usr/bin/env python3
"""Analyze audio file and collect statistics for visualization tuning"""

import sys
import time
import numpy as np
import platform
import subprocess
import os
from audio_input import get_audio_input
from audio_analyzer import AudioAnalyzer
from config import SAMPLE_RATE, CHUNK_SIZE

def main(filepath):
    print(f"Analyzing: {filepath}\n")

    audio = get_audio_input(source="file", filepath=filepath, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
    analyzer = AudioAnalyzer(sample_rate=SAMPLE_RATE)

    # Start audio playback in background AFTER loading
    try:
        if platform.system() == 'Darwin':
            subprocess.Popen(['afplay', filepath])
        elif platform.system() == 'Linux':
            ffmpeg_proc = subprocess.Popen(['ffmpeg', '-i', filepath, '-f', 's16le', '-ar', '44100', '-ac', '2', '-'], 
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            subprocess.Popen(['aplay', '-f', 'S16_LE', '-r', '44100', '-c', '2'], stdin=ffmpeg_proc.stdout, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            ffmpeg_proc.stdout.close()
        time.sleep(0.5)  # Give playback time to start
        print("Playing audio...\n")
    except Exception as e:
        print(f"⚠️  Audio playback unavailable: {e}\n")

    # Collect statistics
    volumes = []
    basses = []
    mids = []
    highs = []
    
    chunk_count = 0
    first_chunk = True
    initial_position = None
    chunk_duration = CHUNK_SIZE / SAMPLE_RATE

    print("Reading audio...")
    while True:
        chunk = audio.read_chunk()
        features = analyzer.analyze(chunk)

        volumes.append(features['volume'])
        basses.append(features['bass'])
        mids.append(features['mid'])
        highs.append(features['high'])

        print(f"  Chunk {chunk_count}: Vol={features['volume']:.3f} Bass={features['bass']:.3f} Mid={features['mid']:.3f} High={features['high']:.3f}")

        # Break after one complete pass through the file
        if first_chunk:
            initial_position = audio.position
            first_chunk = False
        elif audio.position < initial_position:
            # File looped, we've analyzed one complete pass
            break

        chunk_count += 1
        time.sleep(chunk_duration)  # Stay in sync with audio playback

    audio.close()

    # Print statistics
    print("\n" + "="*60)
    print("AUDIO ANALYSIS STATISTICS")
    print("="*60)

    for name, values in [('Volume', volumes), ('Bass', basses), ('Mid', mids), ('High', highs)]:
        arr = np.array(values)
        print(f"\n{name}:")
        print(f"  Min:    {arr.min():.4f}")
        print(f"  Max:    {arr.max():.4f}")
        print(f"  Mean:   {arr.mean():.4f}")
        print(f"  Median: {np.median(arr):.4f}")
        print(f"  Std:    {arr.std():.4f}")
        print(f"  Q25:    {np.percentile(arr, 25):.4f}")
        print(f"  Q75:    {np.percentile(arr, 75):.4f}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: poetry run python analyze_audio.py <mp3_file>")
        sys.exit(1)

    main(sys.argv[1])

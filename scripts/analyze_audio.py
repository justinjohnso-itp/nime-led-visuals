#!/usr/bin/env python3
"""Analyze audio file and collect statistics for visualization tuning"""

import sys
import numpy as np
from audio_input import get_audio_input
from audio_analyzer import AudioAnalyzer
from config import SAMPLE_RATE, CHUNK_SIZE


def main(filepath):
    print(f"Analyzing: {filepath}\n")

    audio = get_audio_input(source="file", filepath=filepath, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
    analyzer = AudioAnalyzer(sample_rate=SAMPLE_RATE)

    # Collect statistics
    volumes = []
    basses = []
    mids = []
    highs = []
    
    chunk_count = 0
    max_chunks = 500  # About 5 seconds at 44.1kHz with 1024 chunk size

    print("Reading audio...")
    while chunk_count < max_chunks:
        chunk = audio.read_chunk()
        features = analyzer.analyze(chunk)

        volumes.append(features['volume'])
        basses.append(features['bass'])
        mids.append(features['mid'])
        highs.append(features['high'])

        if chunk_count % 50 == 0:
            print(f"  Chunk {chunk_count}: Vol={features['volume']:.3f} Bass={features['bass']:.3f} Mid={features['mid']:.3f} High={features['high']:.3f}")

        chunk_count += 1

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

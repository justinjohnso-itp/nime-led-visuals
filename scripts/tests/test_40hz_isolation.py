#!/usr/bin/env python3
"""Test 40 Hz tone isolation in sub_bass band"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from audio_analyzer import AudioAnalyzer
from config import SAMPLE_RATE, CHUNK_SIZE, FREQ_BANDS

def generate_sine_tone(freq_hz, duration_sec, sample_rate):
    """Generate a pure sine wave"""
    t = np.arange(int(sample_rate * duration_sec)) / sample_rate
    return (np.sin(2 * np.pi * freq_hz * t) * 0.8).astype(np.float32)

def test_frequency_isolation(freq_hz):
    """Test how well a frequency is isolated to its expected band"""
    print(f"\n{'='*60}")
    print(f"Testing {freq_hz} Hz tone isolation")
    print(f"{'='*60}")
    
    # Generate 0.5 seconds of tone
    tone = generate_sine_tone(freq_hz, 0.5, SAMPLE_RATE)
    
    analyzer = AudioAnalyzer(sample_rate=SAMPLE_RATE)
    
    # Feed chunks through analyzer
    results = []
    for i in range(0, len(tone) - CHUNK_SIZE, CHUNK_SIZE):
        chunk = tone[i:i + CHUNK_SIZE]
        features = analyzer.analyze(chunk)
        if features['volume'] > 0:  # Skip initial buffering
            results.append(features)
    
    if not results:
        print("No results (still buffering)")
        return
    
    # Average the results
    avg = {key: np.mean([r[key] for r in results]) for key in results[0]}
    
    print(f"\nBand Energies (normalized 0-1):")
    print(f"  sub_bass (20-90 Hz):   {avg.get('sub_bass', 0):.3f}")
    print(f"  bass (90-250 Hz):      {avg.get('bass', 0):.3f}")
    print(f"  low_mid (250-1k Hz):   {avg.get('low_mid', 0):.3f}")
    print(f"  mid_high (1k-4k Hz):   {avg.get('mid_high', 0):.3f}")
    print(f"  treble (4k-20k Hz):    {avg.get('treble', 0):.3f}")
    
    # Calculate isolation percentage
    total = avg.get('sub_bass', 0) + avg.get('bass', 0) + avg.get('low_mid', 0) + avg.get('mid_high', 0) + avg.get('treble', 0)
    if total > 0:
        sub_bass_pct = (avg.get('sub_bass', 0) / total) * 100
        bass_pct = (avg.get('bass', 0) / total) * 100
        print(f"\nIsolation:")
        print(f"  sub_bass share: {sub_bass_pct:.1f}%")
        print(f"  bass share:     {bass_pct:.1f}%")
        print(f"  combined low:   {sub_bass_pct + bass_pct:.1f}%")

def main():
    print("Audio Analyzer Configuration:")
    print(f"  Sample Rate: {SAMPLE_RATE} Hz")
    print(f"  Chunk Size:  {CHUNK_SIZE} samples")
    print(f"  Freq Bands:  {FREQ_BANDS}")
    
    # Test 40 Hz (should be mostly sub_bass)
    test_frequency_isolation(40)
    
    # Test 100 Hz (should be mostly bass)
    test_frequency_isolation(100)
    
    # Test 500 Hz (should be mostly low_mid)
    test_frequency_isolation(500)

if __name__ == '__main__':
    main()

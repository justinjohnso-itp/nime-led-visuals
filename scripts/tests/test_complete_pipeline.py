#!/usr/bin/env python3
"""Test the complete dominant frequency visualization pipeline"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import NUM_LEDS_PER_STRIP, NUM_STRIPS
from audio_analyzer import AudioAnalyzer
from effects import LEDEffects
import numpy as np
import colorsys

class MockPixelSubset:
    def __init__(self, size):
        self.pixels = [(0, 0, 0)] * size
    
    def __len__(self):
        return len(self.pixels)
    
    def __setitem__(self, idx, color):
        self.pixels[idx] = color
    
    def __getitem__(self, idx):
        return self.pixels[idx]


def rgb_to_hue_degrees(r, g, b):
    """Convert RGB to hue in degrees"""
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
    return h * 360


def test_pipeline():
    """Test with synthesized audio at different frequencies"""
    
    sample_rate = 44100
    chunk_size = 1024
    analyzer = AudioAnalyzer(sample_rate=sample_rate)
    
    # Test cases: (frequency_hz, name)
    # Using instrument range: 32.7 Hz (C1) to 7040 Hz (B8)
    test_cases = [
        (40, "Low Bass"),
        (80, "Bass"),
        (165, "Low Mid Bass"),
        (330, "Mid Bass"),
        (660, "Mid"),
        (1320, "Upper Mid"),
        (2640, "Presence"),
        (5280, "High Presence"),
    ]
    
    print("\n" + "="*80)
    print("DOMINANT FREQUENCY VISUALIZATION PIPELINE TEST")
    print("="*80)
    
    for freq_hz, name in test_cases:
        # Synthesize a sine wave at this frequency
        t = np.linspace(0, chunk_size / sample_rate, chunk_size, endpoint=False)
        amplitude = 0.5  # Keep amplitude moderate
        audio = amplitude * np.sin(2 * np.pi * freq_hz * t)
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Analyze
        features = analyzer.analyze(audio_int16)
        
        # Apply LED effect
        strips = [
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
        ]
        LEDEffects.frequency_spectrum(strips, features)
        
        # Get center color
        center_idx = NUM_LEDS_PER_STRIP // 2
        r, g, b = strips[1][center_idx]
        hue = rgb_to_hue_degrees(r, g, b)
        
        # Also get edge colors
        r_edge_low, g_edge_low, b_edge_low = strips[0][0]
        hue_edge_low = rgb_to_hue_degrees(r_edge_low, g_edge_low, b_edge_low)
        
        r_edge_high, g_edge_high, b_edge_high = strips[2][-1]
        hue_edge_high = rgb_to_hue_degrees(r_edge_high, g_edge_high, b_edge_high)
        
        # Print results
        print(f"\n{name:15} ({freq_hz:5} Hz)")
        print(f"  Analysis:")
        print(f"    Centroid: {features['centroid']:.3f} ({20*(20000/20)**features['centroid']:7.0f} Hz)")
        print(f"    Bandwidth: {features['bandwidth']:.3f}")
        print(f"    Volume: {features['volume']:.3f}")
        print(f"  LED Colors:")
        print(f"    Center:     RGB({r:3d}, {g:3d}, {b:3d}) Hue={hue:6.1f}°")
        print(f"    Left Edge:  RGB({r_edge_low:3d}, {g_edge_low:3d}, {b_edge_low:3d}) Hue={hue_edge_low:6.1f}°")
        print(f"    Right Edge: RGB({r_edge_high:3d}, {g_edge_high:3d}, {b_edge_high:3d}) Hue={hue_edge_high:6.1f}°")
    
    print("\n" + "="*80)
    print("✓ Pipeline test complete")
    print("="*80)
    print("\nNotes:")
    print("  - Centroid should increase as frequency increases")
    print("  - Center color hue should shift from red → green → blue as frequency increases")
    print("  - Edge colors should show adjacent frequencies (lower on left, higher on right)")
    print("  - Pure sine waves have low bandwidth, so edges should be subtle")


if __name__ == '__main__':
    test_pipeline()

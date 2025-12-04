#!/usr/bin/env python3
"""Test the LED visualization across the full instrument frequency range"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import colorsys
from audio_analyzer import AudioAnalyzer
from effects import LEDEffects
from config import NUM_LEDS_PER_STRIP, NUM_STRIPS, SPECTRUM_FREQS

class MockPixelSubset:
    def __init__(self, size):
        self.pixels = [(0, 0, 0)] * size
    
    def __len__(self):
        return len(self.pixels)
    
    def __setitem__(self, idx, color):
        self.pixels[idx] = color
    
    def __getitem__(self, idx):
        return self.pixels[idx]


def test_instrument_range():
    """Test frequencies across the instrument range with proper multi-chunk feeding"""
    
    sample_rate = 44100
    chunk_size = 1024
    analyzer = AudioAnalyzer(sample_rate=sample_rate)
    
    # Test frequencies within instrument range: 32.7 Hz (C1) to 7040 Hz (B8)
    test_cases = [
        (40, "Low Bass (E1)"),
        (82, "Bass (E2)"),
        (165, "Mid Bass (E3)"),
        (330, "Low Mid (E4)"),
        (659, "Mid (E5)"),
        (1319, "Upper Mid (E6)"),
        (2637, "High (E7)"),
        (5274, "Very High (E8)"),
    ]
    
    print("\n" + "="*80)
    print("INSTRUMENT RANGE FREQUENCY TEST")
    print(f"Frequency range: {SPECTRUM_FREQS[0]:.1f} Hz - {SPECTRUM_FREQS[-1]:.1f} Hz")
    print("="*80)
    
    for freq_hz, name in test_cases:
        # Feed multiple chunks to properly fill the spectrum buffer
        for chunk_num in range(2):
            t = np.linspace(chunk_num * chunk_size / sample_rate, 
                           (chunk_num + 1) * chunk_size / sample_rate, 
                           chunk_size, endpoint=False)
            amplitude = 0.5
            audio = amplitude * np.sin(2 * np.pi * freq_hz * t)
            audio_int16 = (audio * 32767).astype(np.int16)
            features = analyzer.analyze(audio_int16)
        
        # Now render the final features
        strips = [
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
        ]
        LEDEffects.frequency_spectrum(strips, features)
        
        # Analyze the result
        center_strip = strips[1].pixels
        lit_leds = sum(1 for r, g, b in center_strip if (r, g, b) != (0, 0, 0))
        
        # Get brightness statistics
        brightness_values = [max(r, g, b) for r, g, b in center_strip if (r, g, b) != (0, 0, 0)]
        if brightness_values:
            avg_brightness = np.mean(brightness_values)
            max_brightness = max(brightness_values)
        else:
            avg_brightness = 0
            max_brightness = 0
        
        # Get hue range
        hues = []
        for r, g, b in center_strip:
            if (r, g, b) != (0, 0, 0):
                h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
                hues.append(h * 360)
        
        if hues:
            hue_min = min(hues)
            hue_max = max(hues)
        else:
            hue_min = hue_max = 0
        
        print(f"\n{name:20} ({freq_hz:5} Hz)")
        print(f"  Spectrum: max={np.max(features['spectrum']):.3f}, sum={np.sum(features['spectrum']):.3f}")
        print(f"  Dominant band: {features['dominant_band']}, freq: {features['dominant_freq']:.0f} Hz")
        print(f"  LEDs: {lit_leds} lit, brightness {avg_brightness:.0f}-{max_brightness:.0f}")
        print(f"  Hues: {hue_min:.1f}° - {hue_max:.1f}°")
        
        # Visual bar
        bar_width = 40
        lit_bar = int(lit_leds / NUM_LEDS_PER_STRIP * bar_width)
        print(f"  [{('█' * lit_bar).ljust(bar_width)}]")


if __name__ == '__main__':
    test_instrument_range()

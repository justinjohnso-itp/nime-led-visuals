#!/usr/bin/env python3
"""Test the new mirrored logarithmic spectrum visualization"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import colorsys
from config import NUM_LEDS_PER_STRIP, NUM_STRIPS, NUM_SPECTRUM_BANDS

class MockPixelSubset:
    """Mock LED strip for testing"""
    def __init__(self, size):
        self.pixels = [(0, 0, 0)] * size
    
    def __len__(self):
        return len(self.pixels)
    
    def __setitem__(self, idx, color):
        self.pixels[idx] = color
    
    def __getitem__(self, idx):
        return self.pixels[idx]


def visualize_strip(name, pixels, every_n=6):
    """Print a visual representation of an LED strip"""
    print(f"\n{name}:")
    for i, (r, g, b) in enumerate(pixels.pixels):
        # Convert RGB back to hue for understanding
        if (r, g, b) == (0, 0, 0):
            char = "⚫"
        else:
            h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
            hue = h * 360
            brightness = "█" if v > 0.8 else "▓" if v > 0.5 else "░"
            
            if hue < 30:
                char = f"🔴{brightness}"  # Red (bass)
            elif hue < 60:
                char = f"🟠{brightness}"  # Orange
            elif hue < 150:
                char = f"🟡{brightness}"  # Yellow/Green
            elif hue < 210:
                char = f"🔵{brightness}"  # Blue
            else:
                char = f"🟣{brightness}"  # Purple/Magenta
        
        # Print every Nth LED to fit on screen
        if i % every_n == 0:
            print(f"{char}", end="")
    print()


def test_spectrum_cases():
    """Test with different spectrum patterns"""
    
    # Import the effect
    from effects import LEDEffects
    
    test_cases = [
        ("Bass Only (Band 0)", np.array([1.0] + [0.0] * 31)),
        ("Mid (Band 15)", np.array([0.0] * 15 + [1.0] + [0.0] * 16)),
        ("Treble Only (Band 31)", np.array([0.0] * 31 + [1.0])),
        ("Bass + Treble", np.array([1.0] + [0.0] * 29 + [0.0] * 1 + [1.0])),
        ("Full Spectrum", np.linspace(0.2, 1.0, 32)),
        ("Sine Wave Spectrum", 0.5 + 0.5 * np.sin(np.linspace(0, 2*np.pi, 32))),
        ("Harmonic Series", np.array([1.0, 0.5, 0.33, 0.25, 0.2] + [0.1] * 27)),
    ]
    
    for name, spectrum in test_cases:
        print(f"\n{'='*80}")
        print(f"Test: {name}")
        print(f"{'='*80}")
        
        # Create mock strips
        strips = [
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
        ]
        
        # Apply effect with spectrum data
        features = {'spectrum': spectrum}
        LEDEffects.frequency_spectrum(strips, features)
        
        # Visualize
        visualize_strip("Left Strip  ", strips[0], every_n=4)
        visualize_strip("Center Strip", strips[1], every_n=4)
        visualize_strip("Right Strip ", strips[2], every_n=4)
        
        # Print some stats
        print("\nCenter strip stats:")
        center_pixels = strips[1].pixels
        lit_leds = sum(1 for r, g, b in center_pixels if (r, g, b) != (0, 0, 0))
        print(f"  Lit LEDs: {lit_leds}/{NUM_LEDS_PER_STRIP}")
        
        # Find hue range in center strip
        hues = []
        for r, g, b in center_pixels:
            if (r, g, b) != (0, 0, 0):
                h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
                hues.append(h * 360)
        
        if hues:
            print(f"  Hue range: {min(hues):.1f}° - {max(hues):.1f}°")
            print(f"  Avg brightness: {np.mean([c[0] + c[1] + c[2] for c in center_pixels if c != (0,0,0)]) / (3*255):.2f}")


if __name__ == '__main__':
    test_spectrum_cases()

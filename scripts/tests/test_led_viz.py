#!/usr/bin/env python3
"""Test LED visualization with dominant frequency mapping"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import colorsys
from config import NUM_LEDS_PER_STRIP, NUM_STRIPS

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


def visualize_strip(name, pixels):
    """Print a visual representation of an LED strip"""
    print(f"\n{name}:")
    for i, (r, g, b) in enumerate(pixels.pixels):
        # Convert RGB back to hue for understanding
        if (r, g, b) == (0, 0, 0):
            char = "⚫"
        else:
            h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
            hue = h * 360
            if hue < 30:
                char = "🔴"  # Red (bass)
            elif hue < 60:
                char = "🟠"  # Orange
            elif hue < 90:
                char = "🟡"  # Yellow
            elif hue < 150:
                char = "🟢"  # Green
            elif hue < 210:
                char = "🔵"  # Blue
            elif hue < 270:
                char = "🟣"  # Purple
            else:
                char = "🔴"  # Back to red
        
        # Print every 12th LED to fit on screen
        if i % 12 == 0:
            print(f"  {char}", end="")
    print()


def test_dominant_frequency():
    """Test with different centroid values"""
    
    # Import the effect
    import sys
    sys.path.insert(0, '/Users/justin/Library/CloudStorage/Dropbox/NYU/semester-3-2025-fall/new-interfaces-for-musical-expression/nime-led-visuals/scripts')
    from effects import LEDEffects
    
    test_cases = [
        ("Low Bass (0.1)", {"centroid": 0.1, "bandwidth": 0.3, "volume": 0.5}),
        ("Mid-Range (0.5)", {"centroid": 0.5, "bandwidth": 0.3, "volume": 0.7}),
        ("High Treble (0.9)", {"centroid": 0.9, "bandwidth": 0.3, "volume": 0.6}),
        ("Quiet Bass (0.1)", {"centroid": 0.1, "bandwidth": 0.3, "volume": 0.2}),
        ("Loud Treble (0.95)", {"centroid": 0.95, "bandwidth": 0.2, "volume": 1.0}),
    ]
    
    for name, features in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {name}")
        print(f"Features: Centroid={features['centroid']:.2f}, BW={features['bandwidth']:.2f}, Vol={features['volume']:.2f}")
        print(f"{'='*60}")
        
        # Create mock strips
        strips = [
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
            MockPixelSubset(NUM_LEDS_PER_STRIP),
        ]
        
        # Apply effect
        LEDEffects.frequency_spectrum(strips, features)
        
        # Visualize
        visualize_strip("Left Strip  (reversed)", strips[0])
        visualize_strip("Center Strip", strips[1])
        visualize_strip("Right Strip ", strips[2])
        
        # Print center LED colors for debugging
        print("\nCenter strip first 10 LEDs (RGB values):")
        for i in range(min(10, NUM_LEDS_PER_STRIP)):
            r, g, b = strips[1][i]
            print(f"  LED {i}: ({r:3d}, {g:3d}, {b:3d})")


if __name__ == '__main__':
    test_dominant_frequency()

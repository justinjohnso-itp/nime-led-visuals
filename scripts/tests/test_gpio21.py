#!/usr/bin/env python3
"""Test LED strip on GPIO21 (pin 40) as alternative to GPIO18."""

import time
import board
import neopixel

NUM_TEST_LEDS = 30  # Just test first 30 LEDs

print("=== GPIO21 Test (Pin 40) ===")
print("Make sure data wire is connected to physical pin 40!")
print()

try:
    pixels = neopixel.NeoPixel(board.D21, NUM_TEST_LEDS, brightness=1.0, auto_write=False)
    print(f"✓ NeoPixel initialized on GPIO21 with {NUM_TEST_LEDS} LEDs")
except Exception as e:
    print(f"✗ Failed to initialize: {e}")
    exit(1)

colors = [
    ((255, 0, 0), "RED"),
    ((0, 255, 0), "GREEN"),
    ((0, 0, 255), "BLUE"),
    ((255, 255, 255), "WHITE"),
]

for rgb, name in colors:
    print(f"  {name}...")
    pixels.fill(rgb)
    pixels.show()
    time.sleep(1)

print("\nChase test...")
for i in range(NUM_TEST_LEDS):
    pixels.fill((0, 0, 0))
    pixels[i] = (0, 255, 0)
    pixels.show()
    time.sleep(0.02)

pixels.fill((0, 0, 0))
pixels.show()
print("✓ GPIO21 test complete!")
print("\nIf you saw colors, GPIO21 works! Update config.py to use GPIO 21.")

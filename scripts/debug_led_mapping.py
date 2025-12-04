#!/usr/bin/env python3
"""Debug script to visualize LED-to-band mapping"""

import numpy as np
from config import SPECTRUM_FREQS, NUM_LEDS_PER_STRIP, NUM_STRIPS

total_leds = NUM_LEDS_PER_STRIP * NUM_STRIPS
center = total_leds // 2
leds_per_side = total_leds // 2

print(f"Total LEDs: {total_leds}, Center: {center}, LEDs per side: {leds_per_side}")
print(f"SPECTRUM_FREQS length: {len(SPECTRUM_FREQS)}")
print()

# Calculate cumulative log frequency widths (0.0 to 1.0)
log_freq_widths = []
for band_idx in range(32):
    log_width = np.log10(SPECTRUM_FREQS[band_idx + 1]) - np.log10(SPECTRUM_FREQS[band_idx])
    log_freq_widths.append(log_width)

total_log_width = sum(log_freq_widths)
cumulative_log_width = 0.0
band_boundaries = [0.0]
for log_width in log_freq_widths:
    cumulative_log_width += log_width / total_log_width
    band_boundaries.append(min(1.0, cumulative_log_width))
band_boundaries[-1] = 1.0

print("Band boundaries (normalized 0.0-1.0):")
for i in range(32):
    freq_start = SPECTRUM_FREQS[i]
    freq_end = SPECTRUM_FREQS[i + 1]
    boundary_start = band_boundaries[i]
    boundary_end = band_boundaries[i + 1]
    print(f"Band {i:2d}: {freq_start:7.1f}-{freq_end:7.1f} Hz | Boundaries: {boundary_start:.4f}-{boundary_end:.4f}")

print()
print("LED position to band mapping (sample):")

def get_band_for_position(pos, leds_per_side):
    """Map LED position (0 to leds_per_side-1) to band index (0-31)"""
    if leds_per_side <= 1:
        return 0
    normalized_pos = min(1.0, pos / float(leds_per_side - 1))
    
    for band_idx in range(32):
        if normalized_pos < band_boundaries[band_idx + 1] or band_idx == 31:
            return band_idx
    return 31

# Count LEDs per band
leds_per_band = [0] * 32
for pos in range(leds_per_side):
    band = get_band_for_position(pos, leds_per_side)
    leds_per_band[band] += 1

print("LEDs allocated to each band:")
for i in range(32):
    freq_start = SPECTRUM_FREQS[i]
    freq_end = SPECTRUM_FREQS[i + 1]
    print(f"Band {i:2d}: {freq_start:7.1f}-{freq_end:7.1f} Hz | {leds_per_band[i]:3d} LEDs")

print()
print(f"Total LEDs allocated: {sum(leds_per_band)} (should be {leds_per_side})")

# Show mapping for specific positions
print()
print("Sample position mappings:")
sample_positions = [0, 1, 2, 10, 50, 100, 150, 200, 210, 213, 214, 215]
for pos in sample_positions:
    band = get_band_for_position(pos, leds_per_side)
    if pos < leds_per_side:
        norm_pos = pos / float(leds_per_side - 1)
        freq_start = SPECTRUM_FREQS[band]
        freq_end = SPECTRUM_FREQS[band + 1]
        print(f"Position {pos:3d} (norm {norm_pos:.4f}) → Band {band:2d} ({freq_start:7.1f}-{freq_end:7.1f} Hz)")

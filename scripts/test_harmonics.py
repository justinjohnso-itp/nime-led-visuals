#!/usr/bin/env python3
"""Test harmonic suppression with pure tones + harmonics"""

import numpy as np
from audio_analyzer import AudioAnalyzer
from config import SAMPLE_RATE, CHUNK_SIZE, NUM_SPECTRUM_BANDS

def generate_tone_with_harmonics(freq, duration_s, sample_rate=44100, harmonic_amps=None):
    """Generate a tone with harmonics for testing.
    
    Args:
        freq: Fundamental frequency in Hz
        duration_s: Duration in seconds
        sample_rate: Sample rate in Hz
        harmonic_amps: List of [amp1, amp2, amp3, ...] for harmonics (1st is fundamental)
                      If None, uses typical instrument distribution: [1.0, 0.5, 0.33, 0.25, 0.2]
    """
    if harmonic_amps is None:
        harmonic_amps = [1.0, 0.5, 0.33, 0.25, 0.2]
    
    num_samples = int(duration_s * sample_rate)
    t = np.arange(num_samples) / sample_rate
    signal = np.zeros(num_samples)
    
    # Add fundamental + harmonics
    for harmonic_idx, amp in enumerate(harmonic_amps, start=1):
        harmonic_freq = freq * harmonic_idx
        signal += amp * np.sin(2 * np.pi * harmonic_freq * t)
    
    # Normalize to prevent clipping
    signal = signal / np.max(np.abs(signal)) * 0.9
    
    return (signal * 32768.0).astype(np.int16)

def test_fundamental_suppression(test_freq, duration_s=2.0):
    """Test harmonic suppression on a tone."""
    print(f"\n{'='*70}")
    print(f"Testing {test_freq} Hz tone with harmonics ({duration_s}s)")
    print(f"{'='*70}")
    
    # Generate test signal
    audio = generate_tone_with_harmonics(test_freq, duration_s)
    
    # Analyze in chunks
    analyzer = AudioAnalyzer()
    chunk_size = CHUNK_SIZE
    max_spectrum = np.zeros(NUM_SPECTRUM_BANDS)
    dominant_bands = []
    
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i+chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        
        features = analyzer.analyze(chunk)
        spectrum = features.get('spectrum', np.zeros(NUM_SPECTRUM_BANDS))
        max_spectrum = np.maximum(max_spectrum, spectrum)
        
        if features['dominant_band'] >= 0:
            dominant_bands.append(features['dominant_band'])
    
    # Print top bands
    from config import SPECTRUM_FREQS
    
    top_10 = np.argsort(-max_spectrum)[:10]
    print(f"\nTop 10 bands (energy):")
    print(f"{'Band':>5} {'Freq Range':>15} {'Energy':>8} {'Expected Harmonic':<20}")
    
    fundamental_freq = test_freq
    for rank, band_idx in enumerate(top_10, start=1):
        freq_low = SPECTRUM_FREQS[band_idx]
        freq_high = SPECTRUM_FREQS[band_idx + 1]
        freq_center = (freq_low + freq_high) / 2
        energy = max_spectrum[band_idx]
        
        # Determine which harmonic this is close to
        if fundamental_freq > 0:
            harmonic_num = freq_center / fundamental_freq
            if harmonic_num < 1.5:
                harmonic_str = "Fundamental (1x)"
            elif harmonic_num < 2.5:
                harmonic_str = f"2nd harmonic (~{harmonic_num:.1f}x)"
            elif harmonic_num < 3.5:
                harmonic_str = f"3rd harmonic (~{harmonic_num:.1f}x)"
            elif harmonic_num < 4.5:
                harmonic_str = f"4th harmonic (~{harmonic_num:.1f}x)"
            else:
                harmonic_str = f"Higher ({harmonic_num:.1f}x)"
        else:
            harmonic_str = "?"
        
        print(f"{band_idx:>5} {freq_low:>7.0f}-{freq_high:>7.0f}Hz {energy:>8.3f} {harmonic_str:<20}")
    
    # Calculate energy concentration
    fundamental_band = dominant_bands[0] if dominant_bands else -1
    if fundamental_band >= 0:
        fund_energy = max_spectrum[fundamental_band]
        total_energy = np.sum(max_spectrum)
        concentration = (fund_energy / total_energy) * 100 if total_energy > 0 else 0
        print(f"\nFundamental band concentration: {concentration:.1f}%")

if __name__ == "__main__":
    # Test a few frequencies
    test_frequencies = [100, 200, 300, 440]  # Hz
    
    for freq in test_frequencies:
        test_fundamental_suppression(freq, duration_s=0.5)

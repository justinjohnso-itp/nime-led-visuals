"""Audio feature extraction for real-time visualization"""

import numpy as np
from config import (
    SAMPLE_RATE,
    BASS_LOW,
    BASS_HIGH,
    MID_LOW,
    MID_HIGH,
    HIGH_LOW,
    HIGH_HIGH,
    SMOOTHING_FACTOR,
)


class AudioAnalyzer:
    """Extract frequency and volume features from audio chunks"""

    def __init__(self, sample_rate=SAMPLE_RATE, smoothing=SMOOTHING_FACTOR):
        self.sample_rate = sample_rate
        self.smoothing = smoothing
        # Initialize smoothed values
        self.prev_volume = 0.0
        self.prev_bass = 0.0
        self.prev_mid = 0.0
        self.prev_high = 0.0
        # Running max for per-band normalization
        self.bass_max = 0.1
        self.mid_max = 0.1
        self.high_max = 0.1
        self.decay_rate = 0.98  # Slowly decay max values

    def analyze(self, audio_chunk):
        """Analyze audio chunk and return features
        
        Args:
            audio_chunk: numpy array of audio samples (int16 or float32)
            
        Returns:
            dict with keys: volume, bass, mid, high (all 0.0-1.0)
        """
        # Convert to float for processing
        if audio_chunk.dtype == np.int16:
            audio = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio = audio_chunk.astype(np.float32)

        # Calculate RMS volume
        volume = np.sqrt(np.mean(audio**2))

        # FFT analysis
        fft = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), 1 / self.sample_rate)

        # Extract frequency bands
        bass = self._get_band_energy(fft, freqs, BASS_LOW, BASS_HIGH)
        mid = self._get_band_energy(fft, freqs, MID_LOW, MID_HIGH)
        high = self._get_band_energy(fft, freqs, HIGH_LOW, HIGH_HIGH)

        # Apply log scaling to compress high values
        bass = np.log10(bass + 1)
        mid = np.log10(mid + 1)
        high = np.log10(high + 1)

        # Update running max for each band (adaptive peak detection)
        self.bass_max = max(bass, self.bass_max * self.decay_rate)
        self.mid_max = max(mid, self.mid_max * self.decay_rate)
        self.high_max = max(high, self.high_max * self.decay_rate)

        # Normalize each band independently by its own max
        bass_norm = bass / max(self.bass_max, 0.01)
        mid_norm = mid / max(self.mid_max, 0.01)
        high_norm = high / max(self.high_max, 0.01)
        
        # Clip to 0-1 range
        bass_norm = np.clip(bass_norm, 0, 1)
        mid_norm = np.clip(mid_norm, 0, 1)
        high_norm = np.clip(high_norm, 0, 1)

        # Apply smoothing to prevent flickering
        volume = self._smooth(volume, self.prev_volume)
        bass_norm = self._smooth(bass_norm, self.prev_bass)
        mid_norm = self._smooth(mid_norm, self.prev_mid)
        high_norm = self._smooth(high_norm, self.prev_high)

        # Store for next smoothing
        self.prev_volume = volume
        self.prev_bass = bass_norm
        self.prev_mid = mid_norm
        self.prev_high = high_norm

        return {
            "volume": volume,
            "bass": bass_norm,
            "mid": mid_norm,
            "high": high_norm,
        }

    def _get_band_energy(self, fft, freqs, low_freq, high_freq):
        """Get average energy in frequency band"""
        mask = (freqs >= low_freq) & (freqs < high_freq)
        return np.mean(fft[mask]) if np.any(mask) else 0.0

    def _smooth(self, current, previous):
        """Apply exponential smoothing"""
        return previous + self.smoothing * (current - previous)

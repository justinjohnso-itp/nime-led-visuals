"""Audio feature extraction - simple and working version"""

import numpy as np
from scipy.signal import stft
from config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    SMOOTHING_FACTOR,
    BRIGHTNESS_EXPONENT,
    ATTACK_TIME,
    DECAY_TIME,
    INPUT_GAIN,
    NOISE_GATE_THRESHOLD,
    FREQ_MIN,
    FREQ_MAX,
    FREQ_BANDS,
)


class AudioAnalyzer:
    """Extract frequency and volume features from audio chunks"""

    def __init__(self, sample_rate=SAMPLE_RATE, smoothing=SMOOTHING_FACTOR):
        self.sample_rate = sample_rate
        self.smoothing = smoothing
        
        # Per-band peak tracking (independent normalization for each band)
        self.band_max = {name: 0.1 for _, _, name in FREQ_BANDS}
        self.decay_rate = 0.60
        self.prev_raw_volume = 0.0
        
        # Legacy maxes
        self.bass_max = 0.1
        self.mid_max = 0.1
        self.high_max = 0.1
        
        # ADSR envelope
        self.envelope_value = 0.0
        self.target_envelope = 0.0

    def analyze(self, audio_chunk):
        """Analyze audio chunk and return features"""
        # Convert to float
        if audio_chunk.dtype == np.int16:
            audio = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio = audio_chunk.astype(np.float32)

        # Apply input gain
        audio = audio * INPUT_GAIN
        
        # Calculate volume
        volume = np.sqrt(np.mean(audio**2))
        
        # Apply noise gate
        if volume < NOISE_GATE_THRESHOLD:
            volume = 0.0
            audio = np.zeros_like(audio)

        # Direct FFT (no scipy.stft complexity)
        # Apply Hamming window to reduce spectral leakage
        window = np.hamming(len(audio))
        audio_windowed = audio * window

        # FFT with 2x zero-padding for better frequency resolution
        fft = np.abs(np.fft.rfft(audio_windowed, n=len(audio) * 2))
        freqs = np.fft.rfftfreq(len(audio) * 2, 1 / self.sample_rate)

        # Extract frequency bands
        band_energies = {}
        band_norms = {}
        
        for low_freq, high_freq, name in FREQ_BANDS:
            mask = (freqs >= low_freq) & (freqs < high_freq)
            energy = np.mean(fft[mask]) if np.any(mask) else 0.0
            band_energies[name] = energy
            
            # Update running max
            self.band_max[name] = max(energy, self.band_max[name] * self.decay_rate)
            
            # Normalize
            norm = energy / max(self.band_max[name], 0.01)
            band_norms[name] = np.clip(norm, 0, 1)
        
        # Legacy bands
        bass = band_norms.get('bass', 0.0)
        mid = (band_norms.get('low_mid', 0.0) + band_norms.get('mid_high', 0.0)) / 2
        high = band_norms.get('treble', 0.0)
        
        # Spectral features
        magnitude = fft / (np.sum(fft) + 1e-10)
        centroid_hz = np.sum(freqs * magnitude)
        centroid_norm = np.log10(max(centroid_hz, FREQ_MIN)) / np.log10(FREQ_MAX)
        centroid_norm = np.clip(centroid_norm, 0, 1)
        
        variance = np.sum((freqs - centroid_hz) ** 2 * magnitude)
        bandwidth_hz = np.sqrt(variance) if variance > 0 else 0
        bandwidth_norm = np.log10(max(bandwidth_hz, 1)) / np.log10(FREQ_MAX / 4)
        bandwidth_norm = np.clip(bandwidth_norm, 0, 1)
        
        # Transient detection
        total_energy = sum(band_energies.values())
        energy_change = total_energy - self.prev_raw_volume
        transient = max(0, energy_change) / max(total_energy, 0.001)
        transient = np.clip(transient, 0, 1)
        self.prev_raw_volume = total_energy
        
        # ADSR envelope
        self.target_envelope = max(bass, mid, high)
        if self.target_envelope > self.envelope_value:
            self.envelope_value = self.target_envelope
        else:
            chunk_duration = CHUNK_SIZE / self.sample_rate
            decay_factor = 1.0 - (chunk_duration / DECAY_TIME)
            self.envelope_value = self.envelope_value * decay_factor
        
        self.envelope_value = np.clip(self.envelope_value, 0, 1)
        
        return {
            "volume": volume,
            "bass": bass,
            "mid": mid,
            "high": high,
            "sub_bass": band_norms.get('sub_bass', 0.0),
            "bass": band_norms.get('bass', 0.0),
            "low_mid": band_norms.get('low_mid', 0.0),
            "mid_high": band_norms.get('mid_high', 0.0),
            "treble": band_norms.get('treble', 0.0),
            "centroid": centroid_norm,
            "bandwidth": bandwidth_norm,
            "transient": transient,
            "envelope": self.envelope_value,
        }

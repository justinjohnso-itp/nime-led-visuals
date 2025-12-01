"""Audio feature extraction for real-time visualization"""

import numpy as np
from config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    BASS_LOW,
    BASS_HIGH,
    MID_LOW,
    MID_HIGH,
    HIGH_LOW,
    HIGH_HIGH,
    SMOOTHING_FACTOR,
    BRIGHTNESS_EXPONENT,
    ATTACK_TIME,
    DECAY_TIME,
    FREQ_MIN,
    FREQ_MAX,
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
        self.prev_centroid = 0.0
        self.prev_bandwidth = 0.0
        # Per-band peak tracking (independent normalization for each band)
        self.bass_max = 0.1
        self.mid_max = 0.1
        self.high_max = 0.1
        self.decay_rate = 0.85  # Fast decay (was 0.95, then 0.92) - let peaks drop quickly
        self.prev_raw_volume = 0.0  # For transient detection
        
        # Attack/Decay envelope state (for brightness envelope)
        self.envelope_value = 0.0  # Current brightness envelope (0-1)
        self.target_envelope = 0.0  # Target brightness (what we're trying to reach)

    def analyze(self, audio_chunk):
        """Analyze audio chunk and return features
        
        Args:
            audio_chunk: numpy array of audio samples (int16 or float32)
            
        Returns:
            dict with keys: volume, bass, mid, high, centroid, bandwidth (all 0.0-1.0)
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

        # Extract frequency bands (no log scaling - keep it raw and responsive)
        bass = self._get_band_energy(fft, freqs, BASS_LOW, BASS_HIGH)
        mid = self._get_band_energy(fft, freqs, MID_LOW, MID_HIGH)
        high = self._get_band_energy(fft, freqs, HIGH_LOW, HIGH_HIGH)

        # Update running max for EACH band independently (allows all bands to shine)
        self.bass_max = max(bass, self.bass_max * self.decay_rate)
        self.mid_max = max(mid, self.mid_max * self.decay_rate)
        self.high_max = max(high, self.high_max * self.decay_rate)

        # Normalize each band by its OWN max (per-band normalization)
        # This lets treble peaks show as bright blue, bass as red, mid as green
        bass_norm = bass / max(self.bass_max, 0.001)
        mid_norm = mid / max(self.mid_max, 0.001)
        high_norm = high / max(self.high_max, 0.001)
        
        # Clip to 0-1 range
        bass_norm = np.clip(bass_norm, 0, 1)
        mid_norm = np.clip(mid_norm, 0, 1)
        high_norm = np.clip(high_norm, 0, 1)

        # Calculate spectral centroid (dominant frequency) and bandwidth
        centroid, bandwidth = self._calculate_spectral_features(fft, freqs)

        # NO SMOOTHING on features - just raw data straight to LED
        # (Only smooth the envelope, not the analysis)
        # Store raw values for transient detection
        self.prev_volume = volume
        self.prev_bass = bass_norm
        self.prev_mid = mid_norm
        self.prev_high = high_norm
        self.prev_centroid = centroid
        self.prev_bandwidth = bandwidth

        # Detect transients: relative change in energy (not absolute)
        # Use the sum of all bands as a better indicator than just volume RMS
        total_energy = bass + mid + high
        energy_change = total_energy - self.prev_raw_volume
        
        # Transient is any sudden increase (but not overly sensitive)
        transient = max(0, energy_change) / max(total_energy, 0.001)  # Normalized by current energy
        transient = np.clip(transient, 0, 1)
        self.prev_raw_volume = total_energy
        
        # Apply ADSR envelope to brightness for "punchy" response
        # Target is envelope that responds to transients immediately
        self.target_envelope = envelope_val = max(bass_norm, mid_norm, high_norm)  # Peak of any band
        
        # Attack: jump IMMEDIATELY to new peaks (nearly zero latency)
        # Decay: fall back down smoothly (150ms = natural release)
        if self.target_envelope > self.envelope_value:
            # Attack phase: instant (no smoothing)
            self.envelope_value = self.target_envelope
        else:
            # Decay phase: smooth fall with exponential decay
            chunk_duration = CHUNK_SIZE / self.sample_rate  # Actual chunk time (~23.2ms)
            decay_factor = 1.0 - (chunk_duration / DECAY_TIME)
            self.envelope_value = self.envelope_value * decay_factor
        
        self.envelope_value = np.clip(self.envelope_value, 0, 1)
        
        return {
            "volume": volume,
            "bass": bass_norm,
            "mid": mid_norm,
            "high": high_norm,
            "centroid": centroid,  # Normalized to 0-1 (Hz to 0-1 range)
            "bandwidth": bandwidth,  # Normalized to 0-1
            "transient": transient,  # 0-1, higher = sudden loud event
            "envelope": self.envelope_value,  # ADSR brightness envelope
        }

    def _get_band_energy(self, fft, freqs, low_freq, high_freq):
        """Get average energy in frequency band"""
        mask = (freqs >= low_freq) & (freqs < high_freq)
        return np.mean(fft[mask]) if np.any(mask) else 0.0

    def _calculate_spectral_features(self, fft, freqs):
        """Calculate spectral centroid and bandwidth
        
        Spectral centroid is the "center of mass" of the frequency spectrum:
        - Pure tone → centroid at that frequency
        - Complex sound → centroid at weighted average (brightness indicator)
        
        Bandwidth is the RMS spread around centroid:
        - Pure sine wave → very low bandwidth
        - Broad spectrum → high bandwidth
        
        Returns:
            (centroid, bandwidth) both normalized to 0-1 range
        """
        # Spectral centroid: weighted average frequency
        magnitude = fft / (np.sum(fft) + 1e-10)
        centroid_hz = np.sum(freqs * magnitude)
        
        # Normalize centroid to 0-1 range
        centroid_norm = np.log10(max(centroid_hz, FREQ_MIN)) / np.log10(FREQ_MAX)
        centroid_norm = np.clip(centroid_norm, 0, 1)
        
        # Bandwidth: RMS width around centroid
        variance = np.sum((freqs - centroid_hz) ** 2 * magnitude)
        bandwidth_hz = np.sqrt(variance) if variance > 0 else 0
        
        # Normalize bandwidth to 0-1 (max 4 octaves ≈ 8x frequency ratio)
        bandwidth_norm = np.log10(max(bandwidth_hz, 1)) / np.log10(FREQ_MAX / 4)
        bandwidth_norm = np.clip(bandwidth_norm, 0, 1)
        
        return centroid_norm, bandwidth_norm

    def _smooth(self, current, previous):
        """Apply exponential smoothing"""
        return previous + self.smoothing * (current - previous)

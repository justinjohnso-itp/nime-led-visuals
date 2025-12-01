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
    INPUT_GAIN,
    NOISE_GATE_THRESHOLD,
    FREQ_BANDS,
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
        self.band_max = {name: 0.1 for _, _, name in FREQ_BANDS}
        self.decay_rate = 0.60  # Very fast decay - kills spectral leakage sidelobes quickly
        self.prev_raw_volume = 0.0  # For transient detection
        
        # Legacy band maxes for backward compatibility
        self.bass_max = 0.1
        self.mid_max = 0.1
        self.high_max = 0.1
        
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

        # Apply input gain to boost quiet signals
        audio = audio * INPUT_GAIN
        
        # Calculate RMS volume (before clipping)
        volume = np.sqrt(np.mean(audio**2))
        
        # Apply noise gate - kill signals below threshold
        if volume < NOISE_GATE_THRESHOLD:
            volume = 0.0
            audio = np.zeros_like(audio)
        else:
            # Apply Tukey window (hybrid Hann+rectangular)
            # Better than Hann for transient preservation while still reducing spectral leakage
            # alpha=0.5 means 50% of window is tapered (good balance for audio)
            window = np.blackman(len(audio))  # Slightly more aggressive leakage reduction than Hann
            audio = audio * window

        # FFT with zero-padding for better frequency resolution
        # Pad to 2x chunk size (improves spectral definition without changing latency)
        padded_len = len(audio) * 2
        fft = np.abs(np.fft.rfft(audio, n=padded_len))
        freqs = np.fft.rfftfreq(padded_len, 1 / self.sample_rate)

        # Extract all frequency bands
        band_energies = {}
        band_norms = {}
        for low_freq, high_freq, name in FREQ_BANDS:
            energy = self._get_band_energy(fft, freqs, low_freq, high_freq)
            band_energies[name] = energy
            
            # Update running max independently per band
            self.band_max[name] = max(energy, self.band_max[name] * self.decay_rate)
            
            # Normalize by own max (higher floor = less noise amplification)
            norm = energy / max(self.band_max[name], 0.01)
            band_norms[name] = np.clip(norm, 0, 1)
        
        # Legacy band extraction for effects.py compatibility
        bass = band_energies.get('bass', 0.0)
        mid = (band_energies.get('low_mid', 0.0) + band_energies.get('mid_high', 0.0)) / 2
        high = band_energies.get('treble', 0.0)
        
        bass_norm = band_norms.get('bass', 0.0)
        mid_norm = (band_norms.get('low_mid', 0.0) + band_norms.get('mid_high', 0.0)) / 2
        high_norm = band_norms.get('treble', 0.0)

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
            # All 5 frequency bands for granular color control
            "sub_bass": band_norms.get('sub_bass', 0.0),
            "bass": band_norms.get('bass', 0.0),
            "low_mid": band_norms.get('low_mid', 0.0),
            "mid_high": band_norms.get('mid_high', 0.0),
            "treble": band_norms.get('treble', 0.0),
            "centroid": centroid,  # Normalized to 0-1 (Hz to 0-1 range)
            "bandwidth": bandwidth,  # Normalized to 0-1
            "transient": transient,  # 0-1, higher = sudden loud event
            "envelope": self.envelope_value,  # ADSR brightness envelope
        }

    def _get_band_energy(self, fft, freqs, low_freq, high_freq):
        """Get total energy in frequency band
        
        Uses sum instead of mean to avoid biasing against small bands.
        Normalizes by bin width to handle zero-padding scaling.
        """
        mask = (freqs >= low_freq) & (freqs < high_freq)
        if not np.any(mask):
            return 0.0
        
        # Sum energy (not mean, which biases small bands)
        energy = np.sum(fft[mask])
        
        # Normalize by number of bins to scale consistently with zero-padding
        num_bins = np.sum(mask)
        return energy / max(num_bins, 1)

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

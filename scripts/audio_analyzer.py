"""Audio feature extraction using librosa (industry standard for audio analysis)

Librosa handles:
- Mel-scale spectral analysis (logarithmic frequency matching human ears)
- Proper windowing and overlapping (reduces spectral leakage by design)
- Octave-band energy extraction (cleaner frequency separation)
- No manual FFT management needed
"""

import numpy as np
import librosa
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
)


class AudioAnalyzer:
    """Extract frequency and volume features from audio chunks using librosa"""

    def __init__(self, sample_rate=SAMPLE_RATE, smoothing=SMOOTHING_FACTOR):
        self.sample_rate = sample_rate
        self.smoothing = smoothing
        
        # Per-band peak tracking (independent normalization for each band)
        self.band_max = {
            'sub_bass': 0.1,
            'bass': 0.1,
            'low_mid': 0.1,
            'mid_high': 0.1,
            'treble': 0.1,
        }
        self.decay_rate = 0.60  # Fast decay to kill lingering leakage
        self.prev_raw_volume = 0.0  # For transient detection
        
        # Legacy band maxes for backward compatibility
        self.bass_max = 0.1
        self.mid_max = 0.1
        self.high_max = 0.1
        
        # Attack/Decay envelope state (for brightness)
        self.envelope_value = 0.0
        self.target_envelope = 0.0
        
        # Audio buffer for librosa melspectrogram
        # We need n_fft samples minimum (2048) for good frequency resolution
        self.audio_buffer = np.array([], dtype=np.float32)
        self.min_buffer_size = 2048  # n_fft size - minimum for melspectrogram

    def analyze(self, audio_chunk):
        """Analyze audio using mel-scale spectrogram (better frequency separation)
        
        Librosa's mel-spectrogram:
        - Uses logarithmic frequency scale (matches human hearing)
        - Automatically handles windowing and overlap
        - Separates low frequencies better (40 Hz won't leak into 200+ Hz)
        - Industry standard (used in Spotify, music recognition, etc.)
        
        Args:
            audio_chunk: numpy array of audio samples (int16 or float32)
            
        Returns:
            dict with frequency band energies and features
        """
        # Convert to float
        if audio_chunk.dtype == np.int16:
            audio = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio = audio_chunk.astype(np.float32)

        # Apply input gain
        audio = audio * INPUT_GAIN
        
        # Calculate volume on current chunk
        volume = np.sqrt(np.mean(audio**2))
        
        # Accumulate in buffer
        self.audio_buffer = np.concatenate([self.audio_buffer, audio])
        
        # Only analyze when we have enough buffered samples
        if len(self.audio_buffer) < self.min_buffer_size:
            # Return empty features while building buffer
            return self._empty_features()
        
        # Apply noise gate
        if volume < NOISE_GATE_THRESHOLD:
            volume = 0.0
            # Zero out buffer if too quiet
            self.audio_buffer = np.zeros_like(self.audio_buffer)
        
        # Compute mel-spectrogram: librosa handles windowing/overlap internally
        # n_mels=128: 128 mel-bands (logarithmic frequency spacing)
        # n_fft=2048: window size (good frequency resolution)
        # hop_length=512: 50% overlap between frames
        try:
            mel_spec = librosa.feature.melspectrogram(
                y=self.audio_buffer,
                sr=self.sample_rate,
                n_mels=128,  # 128 mel-bands (logarithmic frequency scale)
                n_fft=2048,  # Large FFT for low-freq separation
                hop_length=512,  # 50% overlap = less spectral leakage
                fmin=FREQ_MIN,  # 20 Hz floor
                fmax=FREQ_MAX,  # 20 kHz ceiling
                power=2.0,  # Power spectrum (magnitude squared)
                window='hann',
                center=True,  # Center padding for alignment
                pad_mode='reflect',  # Better than zeros for edges
            )
        except Exception as e:
            print(f"Melspectrogram error: {e}")
            return self._empty_features()
        
        # Drop first chunk from buffer (to avoid re-analyzing same data next iteration)
        self.audio_buffer = self.audio_buffer[CHUNK_SIZE:]
        
        # Handle empty spectrogram
        if mel_spec.shape[1] == 0:
            return self._empty_features()
        
        # Convert power spectrum to dB scale
        mel_db = librosa.power_to_db(mel_spec, ref=np.max)
        
        # Handle NaN/inf values
        mel_db = np.nan_to_num(mel_db, nan=-80.0, posinf=0.0, neginf=-80.0)
        
        # Extract energy from latest frame (rightmost column = most recent audio)
        latest_frame_db = mel_db[:, -1]  # Last frame
        
        # Convert dB back to linear for band energy calculation
        latest_frame_linear = librosa.db_to_power(latest_frame_db)
        latest_frame_linear = np.nan_to_num(latest_frame_linear, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Map mel-bands to our 5 frequency bands
        # Librosa provides mel_frequencies() to know which Hz each mel-band represents
        mel_freqs = librosa.mel_frequencies(n_mels=128, fmin=FREQ_MIN, fmax=FREQ_MAX)
        
        # Define frequency ranges for our bands (in Hz)
        band_ranges = {
            'sub_bass': (20, 80),
            'bass': (80, 250),
            'low_mid': (250, 1000),
            'mid_high': (1000, 4000),
            'treble': (4000, 20000),
        }
        
        # Extract energy for each band
        band_energies = {}
        band_norms = {}
        
        for band_name, (freq_low, freq_high) in band_ranges.items():
            # Find mel-bands in this frequency range
            mask = (mel_freqs >= freq_low) & (mel_freqs < freq_high)
            
            if np.any(mask):
                # Sum energy in this band
                energy = np.sum(latest_frame_linear[mask])
                # Normalize by number of mel-bands (so bands of different widths are comparable)
                energy = energy / np.sum(mask)
            else:
                energy = 0.0
            
            band_energies[band_name] = energy
            
            # Update running max for this band
            self.band_max[band_name] = max(energy, self.band_max[band_name] * self.decay_rate)
            
            # Normalize by running max
            norm = energy / max(self.band_max[band_name], 0.01)
            band_norms[band_name] = np.clip(norm, 0, 1)
        
        # Legacy band extraction for backward compatibility
        bass = band_norms.get('bass', 0.0)
        mid = (band_norms.get('low_mid', 0.0) + band_norms.get('mid_high', 0.0)) / 2
        high = band_norms.get('treble', 0.0)
        
        # Calculate spectral centroid on mel-scale
        # (which frequencies are active?)
        energy_weighted = latest_frame_linear * mel_freqs
        centroid_hz = np.sum(energy_weighted) / (np.sum(latest_frame_linear) + 1e-10)
        centroid_norm = np.log10(max(centroid_hz, FREQ_MIN)) / np.log10(FREQ_MAX)
        centroid_norm = np.clip(centroid_norm, 0, 1)
        
        # Bandwidth: RMS width of frequency distribution
        variance = np.sum((mel_freqs - centroid_hz) ** 2 * latest_frame_linear) / (np.sum(latest_frame_linear) + 1e-10)
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
            # Attack: immediate
            self.envelope_value = self.target_envelope
        else:
            # Decay: smooth falloff
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

    def _empty_features(self):
        """Return placeholder features while building buffer"""
        return {
            "volume": 0.0,
            "bass": 0.0,
            "mid": 0.0,
            "high": 0.0,
            "sub_bass": 0.0,
            "bass": 0.0,
            "low_mid": 0.0,
            "mid_high": 0.0,
            "treble": 0.0,
            "centroid": 0.0,
            "bandwidth": 0.0,
            "transient": 0.0,
            "envelope": 0.0,
        }

"""Audio feature extraction using librosa mel-spectrogram (production version)"""

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
    FREQ_BANDS,
)


class AudioAnalyzer:
    """Extract frequency and volume features using mel-scale spectrogram"""

    def __init__(self, sample_rate=SAMPLE_RATE, smoothing=SMOOTHING_FACTOR):
        self.sample_rate = sample_rate
        self.smoothing = smoothing
        
        # Per-band peak tracking
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
        
        # Streaming buffer: accumulate chunks until we have enough for analysis
        self.buffer = np.array([], dtype=np.float32)
        
        # STFT/Melspectrogram parameters (must match librosa calls)
        # n_fft=4096 gives 10.77 Hz/bin resolution (vs 21.5 Hz at 2048) for better sub-bass isolation
        self.n_fft = 4096
        self.hop_length = 512

    def analyze(self, audio_chunk):
        """Analyze audio using mel-spectrogram"""
        # Convert to float
        if audio_chunk.dtype == np.int16:
            audio = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio = audio_chunk.astype(np.float32)

        # Apply input gain
        audio = audio * INPUT_GAIN
        
        # Calculate volume
        volume = np.sqrt(np.mean(audio**2))
        
        # Accumulate in buffer
        self.buffer = np.concatenate([self.buffer, audio])
        
        # Apply noise gate to entire buffer if current chunk is silent
        if volume < NOISE_GATE_THRESHOLD:
            volume = 0.0
            self.buffer = np.zeros_like(self.buffer)
        
        # Only analyze when buffer has enough samples for melspectrogram
        # n_fft=4096 needs at least 4096 samples to produce any output
        if len(self.buffer) < self.n_fft:
            # Return real volume while buffering (don't discard it)
            return self._empty_features(volume=volume)
        
        # Compute mel-spectrogram on accumulated buffer
        try:
            S = librosa.feature.melspectrogram(
                y=self.buffer,
                sr=self.sample_rate,
                n_mels=128,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                fmin=FREQ_MIN,
                fmax=FREQ_MAX,
                power=2.0,
                window=('kaiser', 14),  # Kaiser β=14: -120dB sidelobes vs Hann's -32dB
                center=False,  # Don't center-pad (we manage buffering)
            )
            # S shape: (128, num_frames)
        except Exception as e:
            print(f"Melspectrogram error: {e}, buffer_len={len(self.buffer)}")
            return self._empty_features()
        
        # Extract latest frame (most recent audio)
        latest_frame = S[:, -1]  # (128,)
        
        # Drop analyzed samples from buffer (prevent re-analysis)
        # With center=False: frame t begins at sample t*hop_length and spans n_fft samples
        # After N frames, we've analyzed up to sample N*hop_length + n_fft - 1
        # Drop num_frames * hop_length to keep overlap and prevent re-analysis
        num_frames = S.shape[1]
        samples_to_drop = num_frames * self.hop_length
        self.buffer = self.buffer[samples_to_drop:]
        
        # Map mel-bands to frequency bands
        mel_freqs = librosa.mel_frequencies(n_mels=128, fmin=FREQ_MIN, fmax=FREQ_MAX)
        
        band_energies = {}
        band_norms = {}
        
        for low_freq, high_freq, name in FREQ_BANDS:
            # Find mel-bands in this frequency range
            mask = (mel_freqs >= low_freq) & (mel_freqs < high_freq)
            
            if np.any(mask):
                # Mean energy in this band (mel-scale spreads energy logarithmically)
                energy = np.mean(latest_frame[mask])
            else:
                energy = 0.0
            
            band_energies[name] = energy
            
            # Update running max
            self.band_max[name] = max(energy, self.band_max[name] * self.decay_rate)
            
            # Normalize by running max
            norm = energy / max(self.band_max[name], 0.01)
            band_norms[name] = np.clip(norm, 0, 1)
        
        # Legacy bands
        bass = band_norms.get('bass', 0.0)
        mid = (band_norms.get('low_mid', 0.0) + band_norms.get('mid_high', 0.0)) / 2
        high = band_norms.get('treble', 0.0)
        
        # Spectral centroid
        magnitude = latest_frame / (np.sum(latest_frame) + 1e-10)
        centroid_hz = np.sum(mel_freqs * magnitude)
        centroid_norm = np.log10(max(centroid_hz, FREQ_MIN)) / np.log10(FREQ_MAX)
        centroid_norm = np.clip(centroid_norm, 0, 1)
        
        # Bandwidth
        variance = np.sum((mel_freqs - centroid_hz) ** 2 * magnitude)
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

    def _empty_features(self, volume=0.0):
        """Return silence features while buffering, preserving real volume"""
        return {
            "volume": volume,
            "bass": 0.0,
            "mid": 0.0,
            "high": 0.0,
            "sub_bass": 0.0,
            "low_mid": 0.0,
            "mid_high": 0.0,
            "treble": 0.0,
            "centroid": 0.0,
            "bandwidth": 0.0,
            "transient": 0.0,
            "envelope": 0.0,
        }

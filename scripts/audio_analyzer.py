"""Audio feature extraction using numpy FFT (fast real-time version)"""

import numpy as np
from numpy.fft import rfft, rfftfreq

from config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    SMOOTHING_FACTOR,
    DECAY_TIME,
    INPUT_GAIN,
    NOISE_GATE_THRESHOLD,
    FREQ_MIN,
    FREQ_MAX,
    FREQ_BANDS,
    NUM_SPECTRUM_BANDS,
    SPECTRUM_FREQS,
)


class AudioAnalyzer:
    """Extract frequency and volume features using a single FFT per chunk"""

    def __init__(self, sample_rate=SAMPLE_RATE, smoothing=SMOOTHING_FACTOR):
        self.sample_rate = sample_rate
        self.smoothing = smoothing

        # Per-band peak tracking (legacy 5 bands)
        self.band_max = {name: 0.1 for _, _, name in FREQ_BANDS}
        self.decay_rate = 0.60
        self.prev_raw_volume = 0.0

        # 32-band spectrum state
        self.spectrum_max = np.full(NUM_SPECTRUM_BANDS, 0.1)
        self.prev_spectrum = np.zeros(NUM_SPECTRUM_BANDS)

        # ADSR envelope
        self.envelope_value = 0.0

        # FFT setup
        self.n_fft = CHUNK_SIZE
        self.window = np.hanning(self.n_fft).astype(np.float32)

        # Frequency axis for FFT bins
        self.freqs = rfftfreq(self.n_fft, d=1.0 / self.sample_rate)

        # Pre-compute legacy band bin indices
        self.band_bins = {}
        for low_f, high_f, name in FREQ_BANDS:
            idx = np.where((self.freqs >= low_f) & (self.freqs < high_f))[0]
            self.band_bins[name] = idx if idx.size > 0 else None

        # Pre-compute 32-band bin indices (logarithmically spaced)
        self.spectrum_bins = []
        for i in range(NUM_SPECTRUM_BANDS):
            low_f = SPECTRUM_FREQS[i]
            high_f = SPECTRUM_FREQS[i + 1]
            idx = np.where((self.freqs >= low_f) & (self.freqs < high_f))[0]
            self.spectrum_bins.append(idx if idx.size > 0 else None)

    def analyze(self, audio_chunk):
        """Analyze one audio chunk using a single FFT"""
        # Convert to float32 in [-1, 1]
        if audio_chunk.dtype == np.int16:
            audio = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio = audio_chunk.astype(np.float32)

        # Mono downmix if stereo
        if audio.ndim > 1:
            audio = np.mean(audio, axis=-1)

        # Apply input gain
        audio = audio * INPUT_GAIN

        # Volume (RMS)
        volume = float(np.sqrt(np.mean(audio ** 2))) if audio.size > 0 else 0.0

        # Noise gate - if below threshold, return silence
        if volume < NOISE_GATE_THRESHOLD:
            # Decay the spectrum smoothly
            self.prev_spectrum *= 0.9
            return {
                "volume": 0.0,
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
                "envelope": self.envelope_value * 0.9,
                "spectrum": self.prev_spectrum.copy(),
            }

        # Ensure frame matches FFT size
        if audio.size < self.n_fft:
            frame = np.zeros(self.n_fft, dtype=np.float32)
            frame[-audio.size:] = audio
        else:
            frame = audio[-self.n_fft:]

        # Window and FFT
        windowed = frame * self.window
        spectrum = rfft(windowed)
        power = spectrum.real ** 2 + spectrum.imag ** 2

        # === 32-band spectrum with smoothing ===
        spectrum_bands = np.zeros(NUM_SPECTRUM_BANDS)
        for i, idx in enumerate(self.spectrum_bins):
            if idx is not None and len(idx) > 0:
                spectrum_bands[i] = float(np.mean(power[idx]))

        # Update running max with decay
        self.spectrum_max = np.maximum(spectrum_bands, self.spectrum_max * self.decay_rate)

        # Normalize
        spectrum_norm = spectrum_bands / np.maximum(self.spectrum_max, 0.01)
        spectrum_norm = np.clip(spectrum_norm, 0.0, 1.0)

        # Smooth with previous frame (reduces flickering)
        attack = 0.6
        decay = 0.2
        for i in range(NUM_SPECTRUM_BANDS):
            if spectrum_norm[i] > self.prev_spectrum[i]:
                self.prev_spectrum[i] += (spectrum_norm[i] - self.prev_spectrum[i]) * attack
            else:
                self.prev_spectrum[i] += (spectrum_norm[i] - self.prev_spectrum[i]) * decay

        # === Legacy 5-band output ===
        band_norms = {}
        total_energy = 0.0

        for name, idx in self.band_bins.items():
            if idx is None or len(idx) == 0:
                energy = 0.0
            else:
                energy = float(np.mean(power[idx]))

            total_energy += energy
            self.band_max[name] = max(energy, self.band_max[name] * self.decay_rate)
            norm = energy / max(self.band_max[name], 0.01)
            band_norms[name] = float(np.clip(norm, 0.0, 1.0))

        # Legacy bands
        bass = band_norms.get("bass", 0.0)
        mid = (band_norms.get("low_mid", 0.0) + band_norms.get("mid_high", 0.0)) / 2.0
        high = band_norms.get("treble", 0.0)

        # Spectral centroid
        mag_sum = float(np.sum(power))
        if mag_sum > 0.0:
            mag_norm = power / mag_sum
            centroid_hz = float(np.sum(self.freqs * mag_norm))
        else:
            centroid_hz = 0.0

        if centroid_hz <= 0.0:
            centroid_norm = 0.0
        else:
            centroid_norm = np.log10(max(centroid_hz, FREQ_MIN)) / np.log10(FREQ_MAX)
            centroid_norm = float(np.clip(centroid_norm, 0.0, 1.0))

        # Bandwidth
        if mag_sum > 0.0:
            variance = float(np.sum((self.freqs - centroid_hz) ** 2 * mag_norm))
            bandwidth_hz = float(np.sqrt(variance)) if variance > 0.0 else 0.0
        else:
            bandwidth_hz = 0.0

        if bandwidth_hz <= 0.0:
            bandwidth_norm = 0.0
        else:
            bandwidth_norm = np.log10(max(bandwidth_hz, 1.0)) / np.log10(FREQ_MAX / 4.0)
            bandwidth_norm = float(np.clip(bandwidth_norm, 0.0, 1.0))

        # Transient detection
        energy_change = total_energy - self.prev_raw_volume
        if total_energy > 0.0:
            transient = max(0.0, energy_change) / max(total_energy, 0.001)
        else:
            transient = 0.0
        transient = float(np.clip(transient, 0.0, 1.0))
        self.prev_raw_volume = total_energy

        # ADSR envelope
        target = max(bass, mid, high)
        if target > self.envelope_value:
            self.envelope_value = target
        else:
            chunk_duration = CHUNK_SIZE / self.sample_rate
            decay_factor = 1.0 - (chunk_duration / DECAY_TIME)
            self.envelope_value = self.envelope_value * decay_factor

        self.envelope_value = float(np.clip(self.envelope_value, 0.0, 1.0))

        return {
            "volume": volume,
            "bass": band_norms.get("bass", 0.0),
            "mid": mid,
            "high": high,
            "sub_bass": band_norms.get("sub_bass", 0.0),
            "low_mid": band_norms.get("low_mid", 0.0),
            "mid_high": band_norms.get("mid_high", 0.0),
            "treble": band_norms.get("treble", 0.0),
            "centroid": centroid_norm,
            "bandwidth": bandwidth_norm,
            "transient": transient,
            "envelope": self.envelope_value,
            "spectrum": self.prev_spectrum.copy(),  # 32-band smoothed spectrum
        }

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

        # FFT setup - use CHUNK_SIZE for fast response
        self.n_fft = CHUNK_SIZE
        self.window = np.hanning(self.n_fft).astype(np.float32)
        self.freqs = rfftfreq(self.n_fft, d=1.0 / self.sample_rate)

        # Larger FFT for cleaner 32-band spectrum (2048 samples = 21 Hz/bin)
        self.spectrum_n_fft = 2048
        self.spectrum_window = np.hanning(self.spectrum_n_fft).astype(np.float32)
        self.spectrum_freqs = rfftfreq(self.spectrum_n_fft, d=1.0 / self.sample_rate)
        self.spectrum_buffer = np.zeros(self.spectrum_n_fft, dtype=np.float32)

        # Pre-compute legacy band bin indices
        self.band_bins = {}
        for low_f, high_f, name in FREQ_BANDS:
            idx = np.where((self.freqs >= low_f) & (self.freqs < high_f))[0]
            self.band_bins[name] = idx if idx.size > 0 else None

        # Pre-compute 32-band bin indices using the larger spectrum FFT
        self.spectrum_bins = []
        for i in range(NUM_SPECTRUM_BANDS):
            low_f = SPECTRUM_FREQS[i]
            high_f = SPECTRUM_FREQS[i + 1]
            idx = np.where((self.spectrum_freqs >= low_f) & (self.spectrum_freqs < high_f))[0]
            self.spectrum_bins.append(idx if idx.size > 0 else None)
        
        # Running max decay rate for 32-band spectrum (balance responsiveness with peak holding)
        self.spectrum_decay_rate = 0.95  # Fast decay for responsiveness, slow enough to hold peaks
        
        # A-weighting curve for perceptual loudness (approximate)
        # Makes the spectrum reflect what's actually audible
        self.a_weight = self._compute_a_weight(self.spectrum_freqs)
    
    def _compute_a_weight(self, freqs):
        """Compute A-weighting curve for perceptual loudness"""
        # A-weighting formula (attempt - simplified version)
        # Full A-weight: attenuates bass and high treble, boosts 1-6 kHz
        f = np.maximum(freqs, 1.0)  # Avoid divide by zero
        
        # Attempt simplified A-weighting based on equal-loudness contours
        # This boosts mids (1-4kHz) and rolls off lows and highs
        ra = (12194**2 * f**4) / (
            (f**2 + 20.6**2) * 
            np.sqrt((f**2 + 107.7**2) * (f**2 + 737.9**2)) * 
            (f**2 + 12194**2)
        )
        # Normalize so 1kHz = 1.0
        a_weight = ra / np.max(ra + 1e-10)
        return a_weight.astype(np.float32)

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
            # Decay envelope and spectrum, snap to zero when very small
            self.envelope_value *= 0.85
            if self.envelope_value < 0.01:
                self.envelope_value = 0.0
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
                "envelope": self.envelope_value,
                "spectrum": self.prev_spectrum.copy(),
                "dominant_band": -1,
                "dominant_freq": 0.0,
                "tonalness": 0.0,
            }

        # Ensure frame matches FFT size (for legacy bands)
        if audio.size < self.n_fft:
            frame = np.zeros(self.n_fft, dtype=np.float32)
            frame[-audio.size:] = audio
        else:
            frame = audio[-self.n_fft:]

        # Window and FFT (fast, for legacy bands)
        windowed = frame * self.window
        spectrum = rfft(windowed)
        power = spectrum.real ** 2 + spectrum.imag ** 2

        # === 32-band spectrum using larger 2048-sample buffer ===
        # Roll the buffer and add new samples
        self.spectrum_buffer = np.roll(self.spectrum_buffer, -len(audio))
        self.spectrum_buffer[-len(audio):] = audio
        
        # Larger FFT for cleaner frequency resolution
        spectrum_windowed = self.spectrum_buffer * self.spectrum_window
        spectrum_fft = rfft(spectrum_windowed)
        spectrum_power = spectrum_fft.real ** 2 + spectrum_fft.imag ** 2
        
        # A-weighting disabled for instrument visualization
        # (A-weighting suppresses bass; we want full spectrum representation)
        # spectrum_power = spectrum_power * self.a_weight
        
        spectrum_bands = np.zeros(NUM_SPECTRUM_BANDS)
        for i, idx in enumerate(self.spectrum_bins):
            if idx is not None and len(idx) > 0:
                spectrum_bands[i] = float(np.mean(spectrum_power[idx]))
        
        # Bass boost: low frequencies naturally quieter, enhance them for visualization
        # Boost strongest at band 0, fade out by band 15
        bass_boost = np.ones(NUM_SPECTRUM_BANDS)
        for i in range(16):
            # Linear ramp from 3.0x boost (band 0) to 1.0x (band 15)
            bass_boost[i] = 3.0 - (i / 16.0) * 2.0
        spectrum_bands = spectrum_bands * bass_boost
        
        # Harmonic suppression: suppress overtones relative to the detected fundamental
        # Find the strongest band (fundamental frequency of the note being played)
        fundamental_band = int(np.argmax(spectrum_bands))
        
        # Suppress harmonics (2x, 3x, 4x, 5x) of the fundamental frequency
        harmonic_suppression = np.ones(NUM_SPECTRUM_BANDS)
        harmonic_ratios = [2.0, 3.0, 4.0, 5.0]  # 2nd, 3rd, 4th, 5th harmonics
        
        for harmonic_ratio in harmonic_ratios:
            harmonic_band = int(fundamental_band * harmonic_ratio)
            if harmonic_band < NUM_SPECTRUM_BANDS:
                # Suppress this harmonic band and its neighbors (±1 band width)
                suppression_width = max(1, fundamental_band // 4)  # Band width depends on fundamental position
                for offset in range(-suppression_width, suppression_width + 1):
                    band_idx = harmonic_band + offset
                    if 0 <= band_idx < NUM_SPECTRUM_BANDS:
                        # Gaussian-shaped suppression centered on harmonic
                        distance = abs(offset) / float(suppression_width + 1)
                        suppression = 0.3 + (0.7 * np.exp(-distance * distance))  # 0.3 to 1.0
                        harmonic_suppression[band_idx] *= suppression
        
        spectrum_bands = spectrum_bands * harmonic_suppression

        # Find dominant band BEFORE normalization (raw energy)
        total_band_energy = float(np.sum(spectrum_bands))
        if total_band_energy > 0.0:
            dominant_band = int(np.argmax(spectrum_bands))
            dominant_energy = float(spectrum_bands[dominant_band])
            tonalness = dominant_energy / total_band_energy  # How peaked the spectrum is
            dominant_freq = float(0.5 * (SPECTRUM_FREQS[dominant_band] + SPECTRUM_FREQS[dominant_band + 1]))
        else:
            dominant_band = -1
            dominant_freq = 0.0
            tonalness = 0.0

        # Update running max with decay (slower for 32-band spectrum to capture sustained notes)
        self.spectrum_max = np.maximum(spectrum_bands, self.spectrum_max * self.spectrum_decay_rate)

        # Normalize: divide by running max, but don't let quiet bands inflate
        # Use a very gentle noise floor: bands below 0.1% of global max stay quiet
        global_max = float(np.max(self.spectrum_max))
        noise_floor = global_max * 0.001  # Very gentle threshold (0.1%)
        
        spectrum_norm = np.zeros(NUM_SPECTRUM_BANDS)
        for i in range(NUM_SPECTRUM_BANDS):
            if spectrum_bands[i] > noise_floor:
                spectrum_norm[i] = spectrum_bands[i] / np.maximum(self.spectrum_max[i], 0.01)
            else:
                spectrum_norm[i] = 0.0
        
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
            "spectrum": self.prev_spectrum.copy(),
            "dominant_band": dominant_band,
            "dominant_freq": dominant_freq,
            "tonalness": tonalness,
        }

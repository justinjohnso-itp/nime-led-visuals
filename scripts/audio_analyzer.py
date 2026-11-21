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
    BRIGHTNESS_EXPONENT,
    get_live_params,
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
        # Ensure every band has at least one FFT bin (no dead bands)
        self.spectrum_bins = []
        for i in range(NUM_SPECTRUM_BANDS):
            low_f = SPECTRUM_FREQS[i]
            high_f = SPECTRUM_FREQS[i + 1]
            idx = np.where((self.spectrum_freqs >= low_f) & (self.spectrum_freqs < high_f))[0]
            if idx.size == 0:
                # Fallback: pick the closest FFT bin to the band center
                center_f = 0.5 * (low_f + high_f)
                closest = np.argmin(np.abs(self.spectrum_freqs - center_f))
                idx = np.array([closest])
            self.spectrum_bins.append(idx)
        
        # Running max decay rate for 32-band spectrum (balance responsiveness with peak holding)
        self.spectrum_decay_rate = 0.80  # Faster decay so sustained notes normalize higher (was 0.95)
        
        # A-weighting curve for perceptual loudness (approximate)
        # Makes the spectrum reflect what's actually audible
        self.a_weight = self._compute_a_weight(self.spectrum_freqs)

        # Audible root frequency weighting curve across the 32 bands
        # Emphasizes musical fundamentals (40 Hz - 900 Hz) and attenuates high overtone/cymbal wash
        self.root_weight_curve = self._compute_root_weight_curve()

    def _compute_root_weight_curve(self):
        """Compute perceptual root-note weighting curve for the 32 logarithmic bands."""
        curve = np.ones(NUM_SPECTRUM_BANDS, dtype=np.float32)
        for i in range(NUM_SPECTRUM_BANDS):
            fc = 0.5 * (SPECTRUM_FREQS[i] + SPECTRUM_FREQS[i + 1])
            if fc < 38.0:
                # Sub-bass rumble control (20-38 Hz): gentle ramp into audible bass roots
                curve[i] = 0.90 + 0.50 * ((fc - 20.0) / 18.0)
            elif fc <= 350.0:
                # Primary bass & fundamental root zone (38-350 Hz): peak emphasis
                curve[i] = 1.75
            elif fc <= 950.0:
                # Midrange chord/vocal/lead root zone (350-950 Hz): strong root presence
                progress = (np.log10(fc) - np.log10(350.0)) / (np.log10(950.0) - np.log10(350.0))
                curve[i] = 1.75 - 0.55 * progress  # 1.75 -> 1.20
            elif fc <= 2200.0:
                # Upper melody / lower harmonics (950-2200 Hz): smooth roll-off
                progress = (np.log10(fc) - np.log10(950.0)) / (np.log10(2200.0) - np.log10(950.0))
                curve[i] = 1.20 - 0.65 * progress  # 1.20 -> 0.55
            else:
                # High overtones, hi-hats, sibilance (2200-7040 Hz): keep subtle so roots dominate
                progress = (np.log10(fc) - np.log10(2200.0)) / (np.log10(7040.0) - np.log10(2200.0))
                curve[i] = max(0.25, 0.55 - 0.30 * progress)  # 0.55 -> 0.25
        return curve
    
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

        params = get_live_params()
        input_gain = float(params.get("input_gain", INPUT_GAIN))
        noise_gate = float(params.get("noise_gate", NOISE_GATE_THRESHOLD))
        attack_speed = float(params.get("attack_speed", 0.60))
        decay_speed = float(params.get("decay_speed", 0.20))
        peak_hold_decay = float(params.get("peak_hold_decay", self.spectrum_decay_rate))
        harmonic_supp_strength = float(params.get("harmonic_suppression", 0.85))
        bass_boost_max = float(params.get("bass_boost", 2.2))
        root_focus = float(params.get("root_focus", 0.80))

        # Apply input gain
        audio = audio * input_gain

        # Volume (RMS)
        volume = float(np.sqrt(np.mean(audio ** 2))) if audio.size > 0 else 0.0

        # Noise gate - if below threshold, return silence
        if volume < noise_gate:
            # Decay envelope and spectrum, snap to zero when very small
            self.envelope_value *= 0.85
            if self.envelope_value < 0.01:
                self.envelope_value = 0.0
            self.prev_spectrum *= max(0.0, 1.0 - decay_speed * 0.5)
            return {
                "volume": 0.0,
                "raw_volume": volume,
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
        # Only boost the VERY LOWEST bands (0-3) to avoid flattening the spectrum
        # CONSERVATIVE boost to keep spectrum tight around fundamental
        bass_boost = np.ones(NUM_SPECTRUM_BANDS)
        for i in range(4):
            # Ramp from bass_boost_max (band 0) to 1.0x (band 4)
            bass_boost[i] = bass_boost_max - (i / 4.0) * (bass_boost_max - 1.0)
        spectrum_bands = spectrum_bands * bass_boost

        # Audible root frequency weighting (live music tuning):
        # Emphasizes defining root fundamentals (40-950 Hz) over high overtone/cymbal wash
        if root_focus > 0.0:
            effective_root_curve = 1.0 + root_focus * (self.root_weight_curve - 1.0)
            spectrum_bands = spectrum_bands * np.maximum(0.15, effective_root_curve)
        
        # Harmonic suppression: EXTREME attenuation to isolate the fundamental frequency ONLY
        # Goal: visualization shows ONE tight "group" with no harmonic energy visible
        harmonic_suppression = np.ones(NUM_SPECTRUM_BANDS)
        
        # Find dominant band BEFORE applying harmonic suppression
        if np.sum(spectrum_bands) > 0.0 and harmonic_supp_strength > 0.0:
            temp_dominant_band = int(np.argmax(spectrum_bands))
            fundamental_freq = 0.5 * (SPECTRUM_FREQS[temp_dominant_band] + SPECTRUM_FREQS[temp_dominant_band + 1])
            
            # Suppress harmonics: 2x, 3x, 4x, etc. the fundamental frequency
            # EXTREME: -36dB for 2nd (zero it out), -30dB for 3rd, -24dB for 4th+
            for band_idx in range(NUM_SPECTRUM_BANDS):
                band_center_freq = 0.5 * (SPECTRUM_FREQS[band_idx] + SPECTRUM_FREQS[band_idx + 1])
                
                # Check if this band is a harmonic of the fundamental
                if fundamental_freq > 0.0:
                    # Check if it's close to 2x, 3x, 4x, 5x, etc.
                    # Skip 1x (that's the fundamental itself)
                    for harmonic_num in range(2, 16):  # Check up to 15th harmonic
                        exact_harmonic_freq = fundamental_freq * harmonic_num
                        
                        # Measure how close this band center is to the harmonic
                        freq_ratio = band_center_freq / exact_harmonic_freq
                        
                        # VERY TIGHT window: ±5% (tightest possible) - only suppress bands EXACTLY at harmonics
                        # This prevents collateral suppression of non-harmonic frequencies
                        if 0.95 <= freq_ratio <= 1.05:
                            # EXTREME suppression - essentially zero out harmonics completely
                            if harmonic_num == 2:
                                base_suppression_db = -36.0 * harmonic_supp_strength
                            elif harmonic_num == 3:
                                base_suppression_db = -30.0 * harmonic_supp_strength
                            else:
                                base_suppression_db = -24.0 * harmonic_supp_strength
                            
                            # Gaussian window: full suppression at center, sharp fade at edges
                            # Within ±5% window, apply gaussian-like suppression
                            deviation = abs(freq_ratio - 1.0)  # 0.0 to 0.05
                            # Gaussian decay: exp(-x^2 / (2 * sigma^2)) where sigma = 0.02
                            gaussian = np.exp(-((deviation / 0.015) ** 2) / 2.0)
                            suppression_db = base_suppression_db * gaussian
                            
                            suppression_linear = 10.0 ** (suppression_db / 20.0)
                            harmonic_suppression[band_idx] = min(harmonic_suppression[band_idx], suppression_linear)
                            break  # Only suppress for the closest harmonic
        else:
            temp_dominant_band = int(np.argmax(spectrum_bands)) if np.sum(spectrum_bands) > 0.0 else -1
        
        spectrum_bands = spectrum_bands * harmonic_suppression
        
        # Post-suppression cleanup: kill any band that's way above neighbors (escaped harmonics)
        # This catches harmonics that slipped through the ±5% detection window, especially at high frequencies
        non_zero_bands = spectrum_bands[spectrum_bands > 0.0001]
        if len(non_zero_bands) > 5 and harmonic_supp_strength > 0.0:
            median_energy = float(np.median(non_zero_bands))
            # More aggressive threshold: 2.0x median instead of 2.5x to catch more harmonics
            harmonic_threshold = median_energy * 2.0
            outlier_mult = 1.0 - (0.9 * harmonic_supp_strength)  # 0.1 when strength=1.0, 1.0 when strength=0.0
            
            for i in range(NUM_SPECTRUM_BANDS):
                # Check if this band is much higher than median (likely an escaped harmonic)
                if spectrum_bands[i] > harmonic_threshold and i != temp_dominant_band:
                    # Extra aggressive: reduce escaped harmonics to 10% (was 30%)
                    spectrum_bands[i] *= outlier_mult
        
        # Bass bleed: DISABLED for tight fundamental visualization
        # The global normalization now handles bass prominence without spreading energy

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
        self.spectrum_max = np.maximum(spectrum_bands, self.spectrum_max * peak_hold_decay)

        # Normalize using GLOBAL max (not per-band) to keep spectral peaks sharp
        # This ensures the fundamental frequency stands out from harmonics/noise
        global_max = float(np.max(self.spectrum_max))
        
        spectrum_norm = np.zeros(NUM_SPECTRUM_BANDS)
        for i in range(NUM_SPECTRUM_BANDS):
            # Use global maximum for normalization (not per-band max)
            # This preserves the shape of the spectrum
            if spectrum_bands[i] > 0:
                spectrum_norm[i] = spectrum_bands[i] / np.maximum(global_max, 0.01)
            else:
                spectrum_norm[i] = 0.0
        
        spectrum_norm = np.clip(spectrum_norm, 0.0, 1.0)

        # Root dominance contrast: push down secondary spectral wash in live mixes
        # while keeping the defining root frequency peak(s) at full strength
        if root_focus > 0.0:
            frame_peak = float(np.max(spectrum_norm))
            if frame_peak > 0.01:
                dominance_exp = 1.0 + (0.95 * root_focus)
                spectrum_norm = frame_peak * ((spectrum_norm / frame_peak) ** dominance_exp)

        # Smooth with previous frame (reduces flickering)
        attack = attack_speed
        decay = decay_speed
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
            "raw_volume": volume,
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

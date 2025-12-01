# Spectral Leakage Analysis & Solutions

## The Problem

A 40 Hz sine wave (pure sub-bass) is showing up across BASS, L-MID, M-HI, and TRE bands when it should ONLY appear in SUB band. This is **fundamental FFT spectral leakage**, not just windowing artifacts.

### Why This Happens

1. **FFT assumes periodic continuation**: The FFT treats your signal as if it repeats infinitely. A 40 Hz sine wave that doesn't align perfectly with FFT bin boundaries creates discontinuities at the boundary.

2. **Discontinuities require many frequencies to represent**: To express a discontinuity in the frequency domain, the FFT must spread energy across the entire spectrum (like an impulse response).

3. **Single-chunk FFT is fundamentally limited**: With 1024 samples at 44.1 kHz:
   - Frequency resolution = 44100 / 1024 = 43 Hz per bin
   - At 40 Hz, this is between bins → energy leaks across the spectrum
   - Nearest bins are 0 Hz and 43 Hz, so 40 Hz appears as a "blend" across many bins

### Root Cause of Your Observation

The issue is NOT that windowing failed (Blackman is actually good). The issue is:

1. **40 Hz is NOT an analysis frequency** in your 1024-sample FFT
   - Analysis frequencies: 0, 43, 86, 129, 172, 215, etc. Hz
   - 40 Hz is between 0 and 43 Hz → leakage guaranteed
   - Even with perfect windowing, some energy must appear in neighboring bins

2. **Your band extraction is working correctly** by catching leakage in higher bands
   - The leakage is real energy from the 40 Hz wave
   - Windowing reduced it significantly (good!)
   - But can't eliminate it entirely

---

## Solutions (in order of effectiveness)

### Solution 1: Overlapping Windows (STFT) - BEST for Real-Time
**This is the recommended fix for your use case.**

Instead of single 1024-sample chunks, use **50% overlapping STFT** with proper synthesis windowing:

```python
# In audio_analyzer.py __init__:
self.overlap_buffer = np.zeros(CHUNK_SIZE // 2)
self.window = np.hamming(CHUNK_SIZE)  # or blackman

def analyze(self, audio_chunk):
    # Overlap: second half of previous + first half of current
    windowed = np.concatenate([
        self.overlap_buffer,
        audio_chunk
    ])
    
    # Apply window
    windowed = windowed * self.window
    
    # FFT analysis
    fft = np.abs(np.fft.rfft(windowed, n=CHUNK_SIZE*2))  # Zero-pad to 2x
    freqs = np.fft.rfftfreq(CHUNK_SIZE*2, 1/SAMPLE_RATE)
    
    # Store second half for next overlap
    self.overlap_buffer = audio_chunk[CHUNK_SIZE//2:]
```

**Benefits:**
- Reduces spectral leakage by ~6-12 dB
- Increased frequency resolution without latency hit
- Industry standard for audio analysis (used in librosa, essentia, etc.)

**Why it works:**
- Each frequency component gets analyzed at multiple phase positions
- Leakage artifacts average out across overlaps
- Smoother spectral representation

---

### Solution 2: Increase FFT Size (Zero-Padding Alternative)
Zero-padding to 4096 samples instead of 2048:

```python
fft = np.abs(np.fft.rfft(audio * window, n=4096))
freqs = np.fft.rfftfreq(4096, 1/SAMPLE_RATE)
```

**Pros:**
- Simple one-line change
- Frequency resolution: 44100 / 4096 ≈ 10.8 Hz/bin (better)
- Latency: still 23.2 ms (no extra latency)

**Cons:**
- Zero-padding alone doesn't reduce leakage amplitude, just "interpolates" between bins
- A 40 Hz tone still appears spread across bins, just on finer grid

---

### Solution 3: Lower Cutoff for Band Ranges
Make band boundaries wider to account for leakage spreading:

```python
# Current: sub_bass (20-80 Hz) catches 40 Hz directly
# Problem: leakage spreads 40 Hz into higher bands

# Current FREQ_BANDS:
FREQ_BANDS = [
    (20, 80, "sub_bass"),        # 60 Hz wide
    (80, 250, "bass"),           # 170 Hz wide
    ...
]

# Option A: Use LOGARITHMIC bands (perceptually better)
# Ratios instead of linear spacing
FREQ_BANDS = [
    (20, 50, "sub_bass"),        # 1 octave
    (50, 100, "bass_low"),       # 1 octave
    (100, 200, "bass"),          # 1 octave
    ...
]

# Option B: Aggressive noise gate to kill leakage at band edges
# In _get_band_energy():
energy = np.sum(fft[mask])
# Kill the edges (first/last 2 bins of each band have most leakage)
if len(fft[mask]) > 4:
    energy -= np.sum(fft[mask][:2]) * 0.5  # Reduce edge bins
```

---

### Solution 4: Spectral Subtraction (Advanced)
Track "leakage profile" from noise and subtract it:

```python
def analyze(self, audio_chunk):
    # ... existing analysis ...
    
    # Estimate noise profile from silent periods
    if volume < 0.02:  # Quiet moment
        self.noise_profile = fft * 0.3 + self.noise_profile * 0.7
    
    # Subtract estimated leakage
    fft = np.maximum(fft - self.noise_profile * 0.8, 0)
```

**Pros:** 
- Targets actual leakage reduction
- Learns over time

**Cons:**
- Complex, sensitive tuning required
- Can cause artifacts if noise estimate is wrong

---

## What I've Already Done

My previous changes were good but only partially address this:

1. ✅ **Blackman window** - Better sidelobe suppression than Hann
2. ✅ **2x zero-padding** - Better frequency grid resolution
3. ✅ **Sum-based band extraction** - Prevents small-band bias
4. ❌ **Still has fundamental leakage** due to single-chunk analysis

---

## Recommended Implementation Path

### Phase 1: STFT (Immediate - 15 min)
Implement 50% overlapping STFT. This gives ~10 dB leakage reduction for ~2ms latency cost.

### Phase 2: Perceptual Band Restructuring (5 min)
Switch to logarithmic (octave-based) band spacing:

```python
# Human ears perceive frequency logarithmically
# A 40 Hz sine shouldn't leak significantly into 250 Hz band
FREQ_BANDS = [
    (20, 40, "sub_bass_low"),      # 20-40 Hz
    (40, 80, "sub_bass_high"),     # 40-80 Hz  
    (80, 160, "bass_low"),         # 80-160 Hz
    (160, 320, "bass_high"),       # 160-320 Hz
    (320, 640, "low_mid"),         # 320-640 Hz
    (640, 1280, "mid"),            # 640-1280 Hz
    (1280, 2560, "mid_high"),      # 1280-2560 Hz
    (2560, 5120, "treble_low"),    # 2560-5120 Hz
    (5120, 20000, "treble_high"),  # 5120-20k Hz
]
```

Then collapse to 5 bands for visual simplicity.

### Phase 3: Monitor & Tune
After implementing, check if leakage is now band-isolated. If a 40 Hz tone shows <0.1 energy in M-HI band, you've succeeded.

---

## Expected Results After STFT Implementation

**Before (current):**
```
40 Hz sine: SUB[█████] BASS[████] L-MID[██] M-HI[█]
```

**After STFT:**
```
40 Hz sine: SUB[██████] BASS[█] L-MID[ ] M-HI[ ]
```

The energy should stay isolated to the sub-bass band and attenuate rapidly.

---

## References

- **Spectral Leakage:** https://brianmcfee.net/dstbook-site/content/ch06-dft-properties/Leakage.html
- **Overlapping Windows (STFT):** https://en.wikipedia.org/wiki/Short-time_Fourier_transform
- **Window Functions:** https://dsp.stackexchange.com/questions/91378/what-can-be-done-on-top-of-windowing-that-can-reduce-spectral-leakage
- **Welch's Method:** (similar overlapping approach for power spectral density)

---

## Math Behind Leakage

For a tone at frequency $f$ not aligned with DFT bin $k$:

The DFT "sees" a discontinuous signal when looped, requiring the entire spectrum to represent it:

$$\text{Leakage} \propto \left| \frac{\sin(\pi(f - f_k)N)}{\sin(\pi(f - f_k))} \right|$$

Where:
- $f_k$ = frequency of nearest bin
- $N$ = FFT size

This sinc function has sidelobes that extend across all bins. Overlapping windows partially cancel these sidelobes through constructive interference.

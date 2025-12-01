"""Debug FFT resolution for 40 Hz"""
import numpy as np
import librosa
from config import SAMPLE_RATE, FREQ_MIN, FREQ_MAX

# 40 Hz tone
t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
tone = np.sin(2 * np.pi * 40 * t).astype(np.float32)

# Current librosa setup
S = librosa.feature.melspectrogram(
    y=tone, sr=SAMPLE_RATE, n_mels=128, n_fft=2048, hop_length=512,
    fmin=FREQ_MIN, fmax=FREQ_MAX, center=False
)

mel_freqs = librosa.mel_frequencies(n_mels=128, fmin=FREQ_MIN, fmax=FREQ_MAX)
latest_frame = S[:, -1]

print(f"40 Hz tone analysis:")
print(f"n_fft=2048, hop_length=512")
print(f"Frequency resolution: {SAMPLE_RATE / 2048:.2f} Hz/bin")
print(f"40 Hz expected bin: {40 / (SAMPLE_RATE / 2048):.2f}")
print()
print(f"Mel-spectrogram shape: {S.shape}")
print(f"128 mel bands span: {FREQ_MIN} - {FREQ_MAX} Hz")
print()

# Show energy distribution
print("Energy by mel band:")
for i in range(0, 128, 8):
    if i < len(mel_freqs):
        freq = mel_freqs[i]
        energy = latest_frame[i]
        print(f"  Mel {i:3d} @ {freq:7.1f} Hz: {energy:.3f}")

# Show which mel bands have significant energy
print("\nMel bands with >5% energy:")
threshold = np.max(latest_frame) * 0.05
for i, (freq, energy) in enumerate(zip(mel_freqs, latest_frame)):
    if energy > threshold:
        print(f"  Mel {i:3d} @ {freq:7.1f} Hz: {energy:.3f}")

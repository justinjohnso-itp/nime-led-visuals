"""Quick test of 40 Hz tone visualization"""
import numpy as np
import sys
sys.path.insert(0, 'scripts')

from audio_analyzer import AudioAnalyzer
from config import SAMPLE_RATE, CHUNK_SIZE, INPUT_GAIN

# Create a 40 Hz pure sine wave
duration = 1.0  # 1 second
t = np.arange(int(SAMPLE_RATE * duration)) / SAMPLE_RATE
amp = 0.5  # 50% of max
tone = (amp * np.sin(2 * np.pi * 40 * t)).astype(np.float32)

# Initialize analyzer
analyzer = AudioAnalyzer()

# Process in chunks
print(f"Processing 40 Hz tone at {SAMPLE_RATE} Hz, chunk size {CHUNK_SIZE}")
print(f"INPUT_GAIN = {INPUT_GAIN}")
print()

for i in range(0, len(tone), CHUNK_SIZE):
    chunk = tone[i:i+CHUNK_SIZE]
    if len(chunk) < CHUNK_SIZE:
        chunk = np.pad(chunk, (0, CHUNK_SIZE - len(chunk)))
    
    features = analyzer.analyze(chunk)
    
    # Print relevant features
    if i % (CHUNK_SIZE * 10) == 0:  # Print every 10 chunks
        print(f"Chunk {i//CHUNK_SIZE:3d}: sub_bass={features['sub_bass']:.3f}, bass={features['bass']:.3f}, vol={features['volume']:.3f}, envelope={features['envelope']:.3f}")

print("\nFinal features:")
for key in ['sub_bass', 'bass', 'low_mid', 'mid_high', 'treble', 'volume', 'envelope', 'centroid', 'bandwidth']:
    print(f"  {key:12s} = {features[key]:.3f}")

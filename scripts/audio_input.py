"""Audio input abstraction for file and live audio sources"""

import numpy as np
from abc import ABC, abstractmethod


class AudioInput(ABC):
    """Base class for audio input sources"""

    @abstractmethod
    def read_chunk(self):
        """Read and return audio chunk as numpy array"""
        pass

    @abstractmethod
    def close(self):
        """Clean up resources"""
        pass


class FileAudioInput(AudioInput):
    """Read audio from MP3 file using librosa"""

    def __init__(self, filepath, chunk_size=1024, sample_rate=44100):
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate

        try:
            import librosa
        except ImportError:
            print("Error: librosa not installed. Run: pixi add librosa")
            raise

        # Load entire file
        print(f"Loading audio file: {filepath}")
        self.audio, _ = librosa.load(filepath, sr=sample_rate)
        self.position = 0
        print(f"Loaded {len(self.audio) / sample_rate:.1f}s of audio")

    def read_chunk(self):
        """Return next chunk of audio, loop when finished"""
        start = self.position
        end = start + self.chunk_size

        if end > len(self.audio):
            # Loop back to beginning
            self.position = 0
            start = 0
            end = self.chunk_size

        chunk = self.audio[start:end]
        self.position = end

        # Convert to int16 format
        return np.int16(chunk * 32767)

    def close(self):
        pass


class LiveAudioInput(AudioInput):
    """Read audio from USB audio interface using sounddevice"""

    def __init__(self, chunk_size=1024, sample_rate=44100, device=None):
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate

        try:
            import sounddevice as sd
        except ImportError:
            print("Error: sounddevice not installed. Run: pixi add sounddevice")
            raise

        print(f"Opening audio device {device}...")
        self.stream = sd.InputStream(
            channels=1,
            samplerate=sample_rate,
            blocksize=chunk_size,
            device=device
        )
        self.stream.start()
        print("Audio stream started")

    def read_chunk(self):
        """Return next chunk from live audio"""
        data, _ = self.stream.read(self.chunk_size)
        return np.int16(data.flatten() * 32767)

    def close(self):
        self.stream.stop()
        self.stream.close()


def get_audio_input(source="file", filepath=None, chunk_size=1024, sample_rate=44100, device=None):
    """Factory function to get appropriate audio input
    
    Args:
        source: "file" or "live"
        filepath: path to MP3 file (required if source="file")
        chunk_size: audio chunk size in samples
        sample_rate: sample rate in Hz
        device: audio device index (for live input)
        
    Returns:
        AudioInput subclass instance
    """
    if source == "file":
        if not filepath:
            raise ValueError("filepath required for file input")
        return FileAudioInput(filepath, chunk_size=chunk_size, sample_rate=sample_rate)
    elif source == "live":
        return LiveAudioInput(chunk_size=chunk_size, sample_rate=sample_rate, device=device)
    else:
        raise ValueError(f"Unknown source: {source}")

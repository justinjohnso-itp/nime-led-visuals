"""Audio input abstraction for file and live audio sources"""

import numpy as np
from abc import ABC, abstractmethod


def _select_input_device(preferred, sd, min_input_channels=2):
    """
    Resolve an input device index using sounddevice.

    preferred:
        - int/float: explicit device index (validated)
        - str: case-insensitive substring matched against device name
        - None: use default input device or first device with enough input channels
    """
    devices = sd.query_devices()

    # 1) Explicit index
    if isinstance(preferred, (int, float)):
        idx = int(preferred)
        dev = sd.query_devices(idx)
        if dev["max_input_channels"] >= min_input_channels:
            print(f"Using explicit input device index {idx}: {dev['name']}")
            return idx
        else:
            print(
                f"Warning: Device {idx} ('{dev['name']}') has only "
                f"{dev['max_input_channels']} input channels; need {min_input_channels}. Ignoring."
            )

    # 2) Name pattern
    if isinstance(preferred, str) and preferred.strip():
        pattern = preferred.lower()
        matches = [
            (i, d)
            for i, d in enumerate(devices)
            if pattern in d["name"].lower()
            and d.get("max_input_channels", 0) >= min_input_channels
        ]
        if matches:
            idx, dev = matches[0]
            print(f"Matched input device by pattern '{preferred}': [{idx}] {dev['name']}")
            return idx
        else:
            print(
                f"Warning: No input device matching pattern '{preferred}' "
                f"with ≥{min_input_channels} channels found. Falling back."
            )

    # 3) Default input device, if suitable
    try:
        default_input_idx, _ = sd.default.device
    except Exception:
        default_input_idx = None

    if default_input_idx is not None and default_input_idx >= 0:
        dev = sd.query_devices(default_input_idx)
        if dev["max_input_channels"] >= min_input_channels:
            print(f"Using default input device [{default_input_idx}]: {dev['name']}")
            return default_input_idx

    # 4) First device with enough input channels
    for i, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) >= min_input_channels:
            print(f"Falling back to first suitable input device [{i}]: {dev['name']}")
            return i

    # 5) No suitable device
    raise RuntimeError(
        f"No audio input device with at least {min_input_channels} input channels found."
    )


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

        # Resolve device by name pattern, index, or auto-select
        # Allow mono devices (1 channel) - most USB audio interfaces are mono
        resolved_device = _select_input_device(device, sd, min_input_channels=1)
        dev_info = sd.query_devices(resolved_device)
        channels = min(2, dev_info["max_input_channels"])

        print(f"Opening audio device [{resolved_device}] '{dev_info['name']}' with {channels} channels...")
        self.stream = sd.InputStream(
            channels=channels,
            samplerate=sample_rate,
            blocksize=chunk_size,
            device=resolved_device
        )
        self.stream.start()
        print("Audio stream started")

    def read_chunk(self):
        """Return next chunk from live audio (stereo → mono average)"""
        data, _ = self.stream.read(self.chunk_size)
        # Average stereo channels to mono
        if data.ndim > 1:
            data = np.mean(data, axis=1)
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

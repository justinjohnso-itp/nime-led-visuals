"""Visual effects that map audio features to LED patterns"""

import colorsys
import numpy as np
from config import (
    COLORS, NUM_LEDS_PER_STRIP, NUM_STRIPS,
    HUE_RANGE, EDGE_HUE_SHIFT, CORE_FRACTION_MIN, CORE_FRACTION_MAX,
    MIN_BRIGHTNESS, EDGE_FADE_RATE, TRANSIENT_BOOST, BRIGHTNESS_EXPONENT
)


class LEDEffects:
    """Container for LED visualization effects"""

    @staticmethod
    def vu_meter(strip, volume, color=(0, 255, 0)):
        """Light up LEDs from start based on volume, with brightness following amplitude
        
        Args:
            strip: neopixel.NeoPixel or PixelSubset object
            volume: 0.0-1.0 volume level
            color: RGB tuple
        """
        num_leds = len(strip)
        num_lit = int(volume * num_leds)

        # Light up from beginning with brightness proportional to volume
        for i in range(num_leds):
            if i < num_lit:
                # Brightness follows the amplitude value
                scaled_color = tuple(int(c * volume) for c in color)
                strip[i] = scaled_color
            else:
                strip[i] = (0, 0, 0)

    @staticmethod
    def frequency_spectrum(strips, features):
        """Show bass/mid/treble across strips with color gradient
        
        Maps actual frequency band energies to colors:
        - Bass (red), Mid (green), Treble (blue)
        - Weighted by perceptual loudness (louder bands dominate color)
        
        Args:
            strips: list of 3 PixelSubset objects [left, center, right]
            features: dict with bass, mid, high, volume (all 0.0-1.0)
        """
        bass = features.get('bass', 0.0)       # 20-200 Hz
        mid = features.get('mid', 0.0)         # 200-2k Hz
        high = features.get('high', 0.0)       # 2k-20k Hz
        volume = features.get('volume', 0.0)
        transient = features.get('transient', 0.0)  # Sudden volume increase
        envelope = features.get('envelope', 0.0)  # ADSR brightness envelope (replaces raw volume)
        
        # Total LED count across all strips
        total_leds = NUM_LEDS_PER_STRIP * NUM_STRIPS
        
        # Determine hue based on which band is strongest (most energy)
        # This creates a natural color shift: bass=red, mid=green, treble=blue
        total_energy = bass + mid + high + 0.001  # Avoid division by zero
        bass_norm = bass / total_energy
        mid_norm = mid / total_energy
        high_norm = high / total_energy
        
        # Map band dominance to hue (0-360°)
        # Red (0°) for bass, Green (120°) for mid, Blue (240°) for treble
        hue = (bass_norm * 0 + mid_norm * 120 + high_norm * 240) % 360
        
        # Brightness uses ADSR envelope for immediate attack + smooth decay (like a synthesizer)
        # The envelope already incorporates volume and transient information
        # Apply power law for better perceptual distribution (quiet → very dark, loud → bright)
        brightness = max(MIN_BRIGHTNESS, envelope ** BRIGHTNESS_EXPONENT)
        
        # Build color distribution across all LEDs
        # Use the strongest band's energy to control stripe width
        # Low energy (quiet) = narrow core, High energy (loud) = wider core
        strongest_band = max(bass_norm, mid_norm, high_norm)
        core_fraction = CORE_FRACTION_MIN + ((CORE_FRACTION_MAX - CORE_FRACTION_MIN) * strongest_band)
        
        led_colors = []
        for led_idx in range(total_leds):
            # Distance from center (in normalized 0-1 space)
            center_pos = total_leds / 2.0
            distance_from_center = abs(led_idx - center_pos) / center_pos
            
            # Blend distance: edges show adjacent frequencies
            if distance_from_center < core_fraction:
                # Core region: dominant frequency
                current_hue = hue
                edge_fade = 1.0
            else:
                # Edge region: blend to adjacent frequencies
                edge_region = 1.0 - core_fraction
                edge_factor = (distance_from_center - core_fraction) / max(edge_region, 0.01)  # 0-1 in edge region
                edge_factor = np.clip(edge_factor, 0, 1)
                
                # Determine which side we're on and blend appropriately
                if led_idx > center_pos:
                    # Right edge: fade toward higher frequencies (more blue)
                    current_hue = hue + (edge_factor * EDGE_HUE_SHIFT)
                else:
                    # Left edge: fade toward lower frequencies (more red)
                    current_hue = hue - (edge_factor * EDGE_HUE_SHIFT)
                
                edge_fade = 1.0 - (edge_factor * EDGE_FADE_RATE)
            
            # Clamp hue to valid range
            current_hue = np.clip(current_hue, 0, 360)
            
            # Convert HSV to RGB
            r, g, b = colorsys.hsv_to_rgb(current_hue / 360.0, 1.0, brightness * edge_fade)
            color = (int(r * 255), int(g * 255), int(b * 255))
            led_colors.append(color)
        
        # Distribute colors symmetrically: left edge blends secondary → core → right edge blends secondary
        # This creates a mirror effect where edges show adjacent frequencies
        for i in range(NUM_LEDS_PER_STRIP):
            # Left strip: mirrored (reversed), so left edge (index 0) shows the fade like right edge
            left_idx = NUM_LEDS_PER_STRIP - 1 - i
            strips[0][i] = led_colors[left_idx]
            
            # Center strip: pure core
            strips[1][i] = led_colors[NUM_LEDS_PER_STRIP + i]
            
            # Right strip: normal order
            strips[2][i] = led_colors[2*NUM_LEDS_PER_STRIP + i]

    @staticmethod
    def pulse_effect(strip, volume, color=(255, 255, 255)):
        """Pulse entire strip brightness with volume (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            volume: 0.0-1.0 volume level
            color: RGB tuple
        """
        # Scale brightness by volume
        scaled_color = tuple(int(c * volume) for c in color)

        for i in range(len(strip)):
            strip[i] = scaled_color

    @staticmethod
    def waveform_viz(strip, audio_data):
        """Downsample waveform to LED count and display (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            audio_data: numpy array of audio samples
        """
        num_leds = len(strip)
        samples_per_led = len(audio_data) // num_leds

        for i in range(num_leds):
            start = i * samples_per_led
            end = start + samples_per_led
            chunk = audio_data[start:end]

            # Get max amplitude in this chunk
            amplitude = max(abs(chunk))

            # Brightness based on amplitude
            brightness = int(amplitude * 255)
            strip[i] = (brightness, brightness, brightness)

    @staticmethod
    def rainbow_chase(strip, position, speed=0.1):
        """Rainbow color chase across strip (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            position: 0.0-1.0 position along strip
            speed: animation speed (unused, for future)
        """
        num_leds = len(strip)
        led_index = int(position * num_leds) % num_leds

        for i in range(num_leds):
            distance = abs(i - led_index)
            # Fade based on distance
            brightness = max(0, 255 - distance * 30)
            hue = (i / num_leds) * 360
            rgb = LEDEffects._hsv_to_rgb(hue, 1.0, brightness / 255.0)
            strip[i] = rgb

    @staticmethod
    def _hsv_to_rgb(h, s, v):
        """Convert HSV to RGB
        
        Args:
            h: hue 0-360
            s: saturation 0-1
            v: value 0-1
            
        Returns:
            (r, g, b) tuple 0-255
        """
        r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def attack_flash(strip, volume, prev_volume, threshold=0.3, flash_color=(255, 255, 255)):
        """Flash on sudden volume increase (call pixels.show() after)
        
        Args:
            strip: PixelSubset or neopixel.NeoPixel object
            volume: current volume 0.0-1.0
            prev_volume: previous volume 0.0-1.0
            threshold: volume increase threshold to trigger flash
            flash_color: RGB tuple for flash
        """
        attack = volume - prev_volume

        if attack > threshold:
            # Flash at full brightness
            for i in range(len(strip)):
                strip[i] = flash_color
        else:
            # Fade to dim
            dim_color = tuple(int(c * volume * 0.5) for c in flash_color)
            for i in range(len(strip)):
                strip[i] = dim_color

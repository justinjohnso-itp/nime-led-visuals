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
        # Boost bass weight so it's more likely to show through (2x multiplier)
        weighted_bass = bass * 2.0
        total_energy = weighted_bass + mid + high + 0.001  # Avoid division by zero
        bass_norm = weighted_bass / total_energy
        mid_norm = mid / total_energy
        high_norm = high / total_energy
        
        # Map band dominance to hue (0-360°)
        # Red (0°) for bass, Green (120°) for mid, Blue (240°) for treble
        hue = (bass_norm * 0 + mid_norm * 120 + high_norm * 240) % 360
        
        # Brightness uses ADSR envelope + volume scaling
        # Envelope gives responsive peaks, volume gives overall loudness control
        # Apply power law for better perceptual distribution (quiet → very dark, loud → bright)
        envelope_brightness = np.clip(envelope, 0, 1) ** BRIGHTNESS_EXPONENT
        volume_brightness = np.clip(volume, 0, 1) ** BRIGHTNESS_EXPONENT
        # Combine: envelope for dynamics, volume for overall level
        brightness = max(MIN_BRIGHTNESS, envelope_brightness * 0.7 + volume_brightness * 0.3)
        brightness = np.clip(brightness, 0, 1)  # Ensure 0-1 range for RGB conversion
        
        # Build color distribution for each strip with proper edge blending
        # Use the strongest band's energy to control stripe width
        strongest_band = max(bass_norm, mid_norm, high_norm)
        core_fraction = CORE_FRACTION_MIN + ((CORE_FRACTION_MAX - CORE_FRACTION_MIN) * strongest_band)
        
        # Helper function to calculate LED color based on position within a strip
        def get_led_color(position_in_strip, is_left_edge=False, is_right_edge=False):
            """
            position_in_strip: 0.0-1.0 (0 = left edge of strip, 1 = right edge)
            is_left_edge: True if this strip's edge fades toward lower freqs
            is_right_edge: True if this strip's edge fades toward higher freqs
            """
            distance_from_center = abs(position_in_strip - 0.5) * 2  # 0-1, where 0 is center
            
            if distance_from_center < core_fraction:
                # Core region: dominant frequency
                current_hue = hue
                edge_fade = 1.0
            else:
                # Edge region: blend to adjacent frequencies
                edge_region = max(1.0 - core_fraction, 0.01)
                edge_factor = (distance_from_center - core_fraction) / edge_region
                edge_factor = np.clip(edge_factor, 0, 1)
                
                # Determine which edge we're on based on position
                if position_in_strip > 0.5:
                    # Right half of strip
                    if is_right_edge:
                        # Fade toward higher frequencies (more blue)
                        current_hue = hue + (edge_factor * EDGE_HUE_SHIFT)
                    else:
                        # No right edge blending
                        current_hue = hue
                else:
                    # Left half of strip
                    if is_left_edge:
                        # Fade toward lower frequencies (more red)
                        current_hue = hue - (edge_factor * EDGE_HUE_SHIFT)
                    else:
                        # No left edge blending
                        current_hue = hue
                
                edge_fade = 1.0 - (edge_factor * EDGE_FADE_RATE)
            
            current_hue = np.clip(current_hue, 0, 360)
            r, g, b = colorsys.hsv_to_rgb(current_hue / 360.0, 1.0, brightness * edge_fade)
            return (int(r * 255), int(g * 255), int(b * 255))
        
        # Build colors for left strip (left edge fades secondary, rest = core)
        for i in range(NUM_LEDS_PER_STRIP):
            pos = i / NUM_LEDS_PER_STRIP  # 0-1 across the strip
            strips[0][i] = get_led_color(pos, is_left_edge=True)
        
        # Build colors for center strip (no edges, pure core)
        for i in range(NUM_LEDS_PER_STRIP):
            pos = i / NUM_LEDS_PER_STRIP
            strips[1][i] = get_led_color(pos)
        
        # Build colors for right strip (right edge fades secondary, rest = core)
        for i in range(NUM_LEDS_PER_STRIP):
            pos = i / NUM_LEDS_PER_STRIP
            strips[2][i] = get_led_color(pos, is_right_edge=True)

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

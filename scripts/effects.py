"""Visual effects that map audio features to LED patterns"""

import colorsys
import numpy as np
from config import (
    COLORS, NUM_LEDS_PER_STRIP, NUM_STRIPS,
    HUE_RANGE, EDGE_HUE_SHIFT, CORE_FRACTION_MIN, CORE_FRACTION_MAX,
    MIN_BRIGHTNESS, EDGE_FADE_RATE, TRANSIENT_BOOST, BRIGHTNESS_EXPONENT, FREQ_BANDS
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

    # Class-level state for smoothing
    _prev_hue = 0.0
    _prev_brightness = 0.0
    
    @staticmethod
    def frequency_spectrum(strips, features):
        """Fast frequency spectrum visualization - stage-friendly colors
        
        Color palette: Red (bass) → Amber (low-mid) → Blue (treble)
        No greens/yellows - they look bad on stage
        
        Args:
            strips: list of 3 PixelSubset objects [left, center, right]
            features: dict with bass, mid, high, volume (all 0.0-1.0)
        """
        # Extract features
        sub_bass_val = features.get('sub_bass', 0.0)
        bass_val = features.get('bass', 0.0)
        low_mid_val = features.get('low_mid', 0.0)
        treble_val = features.get('treble', 0.0)
        envelope = features.get('envelope', 0.0)
        
        # Weighted color selection - skip green/yellow entirely
        # Red (0°) for bass, Amber (30°) for low-mids, Blue (240°) for treble
        bass_energy = sub_bass_val + bass_val
        
        # Calculate blend weights
        total = bass_energy + low_mid_val + treble_val + 0.001
        bass_weight = bass_energy / total
        mid_weight = low_mid_val / total
        treble_weight = treble_val / total
        
        # Map to stage-friendly hues: Red(0°) → Amber(30°) → Blue(240°)
        # Bass pulls toward red, low-mid pulls toward amber, treble pulls toward blue
        target_hue = (bass_weight * 0.0) + (mid_weight * 30.0) + (treble_weight * 240.0)
        
        # Brightness from envelope
        target_brightness = max(MIN_BRIGHTNESS, envelope ** BRIGHTNESS_EXPONENT)
        
        # Smoothing (attack/decay)
        attack = 0.7   # Fast attack
        decay = 0.15   # Slower decay
        
        # Hue smoothing
        hue_diff = target_hue - LEDEffects._prev_hue
        if abs(hue_diff) > 180:  # Handle wrap-around
            if hue_diff > 0:
                hue_diff -= 360
            else:
                hue_diff += 360
        hue_rate = attack if abs(hue_diff) > 0 else decay
        LEDEffects._prev_hue += hue_diff * hue_rate
        LEDEffects._prev_hue = LEDEffects._prev_hue % 360
        
        # Brightness smoothing
        if target_brightness > LEDEffects._prev_brightness:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * attack
        else:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * decay
        
        # Convert HSV to RGB
        r, g, b = colorsys.hsv_to_rgb(LEDEffects._prev_hue / 360.0, 1.0, LEDEffects._prev_brightness)
        base_color = (int(r * 255), int(g * 255), int(b * 255))
        
        # Fill all strips
        for strip in strips:
            strip.fill(base_color)

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

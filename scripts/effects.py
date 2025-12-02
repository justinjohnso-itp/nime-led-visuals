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
    _prev_edge = 0.0
    
    @staticmethod
    def frequency_spectrum(strips, features):
        """32-band frequency spectrum with edge effects
        
        Uses 32-band spectrum for smooth color mapping:
        - Bands 0-7 (20-200 Hz): Red (bass)
        - Bands 8-15 (200-1.5k Hz): Amber (low-mid)  
        - Bands 16-31 (1.5k-20k Hz): Blue edges (treble)
        
        Args:
            strips: list of 3 PixelSubset objects [left, center, right]
            features: dict with 'spectrum' (32-band array) and 'envelope'
        """
        spectrum = features.get('spectrum', None)
        envelope = features.get('envelope', 0.0)
        dominant_band = features.get('dominant_band', -1)
        tonalness = features.get('tonalness', 0.0)
        
        if spectrum is None or len(spectrum) < 32:
            spectrum = np.zeros(32)
        
        # Average energy in frequency regions (for edges/brightness)
        bass_energy = float(np.mean(spectrum[0:10]))     # 20-173 Hz (red)
        mid_energy = float(np.mean(spectrum[10:22]))     # 173-2.3k Hz (amber)
        treble_energy = float(np.mean(spectrum[22:32]))  # 2.3k-20k Hz (blue edges)
        
        # Fallback blended hue
        core_total = bass_energy + mid_energy + 0.001
        bass_weight = bass_energy / core_total
        mid_weight = mid_energy / core_total
        blended_hue = (bass_weight * 0.0) + (mid_weight * 30.0)
        
        # Use DOMINANT BAND for color when spectrum is tonal enough
        TONALNESS_THRESHOLD = 0.15
        if dominant_band >= 0 and tonalness > TONALNESS_THRESHOLD:
            if dominant_band < 10:
                target_hue = 0.0      # Bass (20-173 Hz) → Red
            elif dominant_band < 22:
                target_hue = 30.0     # Mid (173-2.3k Hz) → Amber
            else:
                target_hue = 240.0    # Treble (2.3k+ Hz) → Blue
        else:
            target_hue = blended_hue
        
        # Brightness from envelope - go fully dark when envelope is near zero
        if envelope < 0.01:
            target_brightness = 0.0
        else:
            target_brightness = max(MIN_BRIGHTNESS, envelope ** BRIGHTNESS_EXPONENT)
        
        # Edge intensity from treble (now 0-1 range since we use mean)
        target_edge = treble_energy  # Direct mapping, already 0-1
        
        # Smoothing - fast edges for transient response
        attack = 0.9
        decay = 0.5
        
        # Hue smoothing
        hue_diff = target_hue - LEDEffects._prev_hue
        LEDEffects._prev_hue += hue_diff * (attack if hue_diff > 0 else decay)
        
        # Brightness smoothing - faster decay to zero
        if target_brightness > LEDEffects._prev_brightness:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * attack
        elif target_brightness < 0.01:
            LEDEffects._prev_brightness *= 0.7  # Fast fade to black
        else:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * decay
        
        # Edge smoothing
        if target_edge > LEDEffects._prev_edge:
            LEDEffects._prev_edge += (target_edge - LEDEffects._prev_edge) * attack
        else:
            LEDEffects._prev_edge += (target_edge - LEDEffects._prev_edge) * decay
        
        # Core color (red/amber)
        r, g, b = colorsys.hsv_to_rgb(LEDEffects._prev_hue / 360.0, 1.0, LEDEffects._prev_brightness)
        core_color = (int(r * 255), int(g * 255), int(b * 255))
        
        # Edge parameters
        edge_intensity = LEDEffects._prev_edge ** 1.5  # Curve for dynamic range
        edge_size = int(NUM_LEDS_PER_STRIP * 0.6 * LEDEffects._prev_edge)
        feather_size = max(10, edge_size // 2)  # Gradient zone (at least 10 LEDs)
        
        # Bass core for center strip with subtle feathering (sharper edges)
        bass_core_size = int(NUM_LEDS_PER_STRIP * 0.7 * (bass_energy / (bass_energy + 0.3)))
        bass_feather_size = max(5, bass_core_size // 4)  # Smaller gradient zone for sharper edges
        bass_brightness = LEDEffects._prev_brightness
        bass_intensity = min(1.0, bass_energy * 2)
        
        center = NUM_LEDS_PER_STRIP // 2
        
        # Pre-calculate RGB values
        cr, cg, cb = colorsys.hsv_to_rgb(LEDEffects._prev_hue / 360.0, 1.0, LEDEffects._prev_brightness)
        br, bg, bb = colorsys.hsv_to_rgb(0.0, 1.0, bass_brightness)  # Pure red for bass core
        er, eg, eb = colorsys.hsv_to_rgb(240.0 / 360.0, 1.0, edge_intensity)  # Blue
        
        # If brightness is essentially zero, just fill black and return
        if LEDEffects._prev_brightness < 0.005:
            for strip in strips:
                strip.fill((0, 0, 0))
            return
        
        # Fill strips with feathered edge effects
        for i in range(NUM_LEDS_PER_STRIP):
            # Strip 0: edge at low indices (left side) with gradient
            dist_from_edge = i  # 0 at left edge
            if dist_from_edge < edge_size:
                if dist_from_edge < edge_size - feather_size:
                    # Solid edge zone
                    blend = 1.0
                else:
                    # Feather zone - gradient blend
                    blend = 1.0 - ((dist_from_edge - (edge_size - feather_size)) / feather_size)
                blend = blend * edge_intensity
                # Blend blue over core
                r = int(cr * 255 * (1 - blend) + er * 255 * blend)
                g = int(cg * 255 * (1 - blend) + eg * 255 * blend)
                b = int(cb * 255 * (1 - blend) + eb * 255 * blend)
                strips[0][i] = (r, g, b)
            else:
                strips[0][i] = core_color
            
            # Strip 1: bass core from center with feathered gradient
            dist_from_center = abs(i - center)
            if dist_from_center < bass_core_size:
                if dist_from_center < bass_core_size - bass_feather_size:
                    # Solid core zone
                    blend = 1.0
                else:
                    # Feather zone - gradient from red to core color
                    blend = 1.0 - ((dist_from_center - (bass_core_size - bass_feather_size)) / max(bass_feather_size, 1))
                blend = blend * bass_intensity
                # Blend red over core color
                r = int(cr * 255 * (1 - blend) + br * 255 * blend)
                g = int(cg * 255 * (1 - blend) + bg * 255 * blend)
                b = int(cb * 255 * (1 - blend) + bb * 255 * blend)
                strips[1][i] = (r, g, b)
            else:
                strips[1][i] = core_color
            
            # Strip 2: edge at high indices (right side) with gradient
            dist_from_edge = NUM_LEDS_PER_STRIP - 1 - i  # 0 at right edge
            if dist_from_edge < edge_size:
                if dist_from_edge < edge_size - feather_size:
                    blend = 1.0
                else:
                    blend = 1.0 - ((dist_from_edge - (edge_size - feather_size)) / feather_size)
                blend = blend * edge_intensity
                r = int(cr * 255 * (1 - blend) + er * 255 * blend)
                g = int(cg * 255 * (1 - blend) + eg * 255 * blend)
                b = int(cb * 255 * (1 - blend) + eb * 255 * blend)
                strips[2][i] = (r, g, b)
            else:
                strips[2][i] = core_color

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

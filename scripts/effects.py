"""Visual effects that map audio features to LED patterns"""

import colorsys
import numpy as np
from config import (
    COLORS, NUM_LEDS_PER_STRIP, NUM_STRIPS, LED_BRIGHTNESS,
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
    _prev_bass = 0.0  # Track bass intensity separately for faster decay
    
    @staticmethod
    def get_band_hue(band_index):
        """Map band index 0-31 to smooth hue gradient emphasizing reds and blues.
        
        Red/Orange (bass) → Blue/Cyan (treble), skipping muddy yellow/green midtones.
        
        Args:
            band_index: 0-31 spectrum band index
            
        Returns:
            hue: 0-360 degrees
        """
        # Emphasize warm reds/oranges and cool blues, skip yellow/green
        if band_index < 16:
            # Bands 0-15: Red (0°) to Orange (30°) - bass/mid warmth
            # 16 bands spread over only 30° for rich reds
            return (band_index / 16.0) * 30.0
        else:
            # Bands 16-31: Cyan (180°) to Blue (240°) - high-mid/treble cool
            # 16 bands spread over 60° of blue spectrum (cyan to deep blue)
            return 180.0 + ((band_index - 16) / 16.0) * 60.0
    
    @staticmethod
    def get_perceptual_brightness_correction(hue_degrees):
        """Apply ITU BT.709 luminance-based brightness correction.
        
        Makes all hues appear equally bright to the human eye, with red at max brightness.
        Uses inverse ITU BT.709 weighting: Y = 0.2126*R + 0.7152*G + 0.0722*B
        
        For red (1.0) perceived brightness = 0.2126, scale other colors:
        - Red: 1.0x (baseline)
        - Green: 0.297x (more sensitive eye perception)
        - Blue: capped at 1.0x (even at max, blue is dimmer than red by nature)
        
        Args:
            hue_degrees: 0-360 hue value
            
        Returns:
            brightness_multiplier: correction factor for equal perceived brightness
        """
        # Normalize hue to 0-1
        hue_norm = hue_degrees / 360.0
        
        # Pure red (0°) and magenta (300-360°) need full brightness
        # Pure green (120°) needs to be dimmed
        # Pure blue (240°) stays full (already dim by nature)
        
        if hue_norm < 0.083:  # 0-30°: Red to Orange (red dominant)
            # Linear blend from pure red (1.0) toward orange which has green
            progress = hue_norm / 0.083
            return 1.0 - (progress * 0.7)  # 1.0 down to 0.3 over red range
        elif hue_norm < 0.417:  # 30-150°: Orange to Cyan (green dominant)
            # Green zone is most sensitive, needs heavy dimming
            # Peak dimming at 120° (pure green at 0.297)
            progress = (hue_norm - 0.083) / 0.334  # 0 to 1 in green range
            # Use cosine curve to reach minimum at 120°
            import math
            dimming = 0.297 + (0.7 * math.cos(progress * math.pi))
            return dimming
        else:  # 150-360°: Cyan to Magenta to Red (blue/red dominant)
            # Blue and magenta back toward red
            progress = (hue_norm - 0.417) / 0.583  # 0 to 1 in blue/red range
            return 0.3 + (progress * 0.7)  # 0.3 up to 1.0
    
    @staticmethod
    def frequency_spectrum(strips, features):
        """Mirrored logarithmic 32-band frequency spectrum analyzer
        
        Center = Band 0 (bass, red)
        Mirrored outward = Bands 1→31 (progressively bluer toward edges, treble)
        
        LED allocation is logarithmic in frequency (equal visual space per octave).
        Brightness = energy in that band.
        
        Args:
            strips: list of 3 PixelSubset objects [left, center, right]
            features: dict with 'spectrum' (32-band array) and 'envelope'
        """
        from config import SPECTRUM_FREQS
        
        spectrum = features.get('spectrum', None)
        
        if spectrum is None or len(spectrum) < 32:
            spectrum = np.zeros(32)
        
        # Treat all 432 LEDs as one continuous strip
        total_leds = NUM_LEDS_PER_STRIP * NUM_STRIPS
        center = total_leds // 2
        leds_per_side = total_leds // 2
        
        # Calculate cumulative log frequency widths (0.0 to 1.0)
        log_freq_widths = []
        for band_idx in range(32):
            log_width = np.log10(SPECTRUM_FREQS[band_idx + 1]) - np.log10(SPECTRUM_FREQS[band_idx])
            log_freq_widths.append(log_width)
        
        total_log_width = sum(log_freq_widths)
        cumulative_log_width = 0.0
        band_boundaries = [0.0]  # Start at 0.0
        for log_width in log_freq_widths:
            cumulative_log_width += log_width / total_log_width
            band_boundaries.append(min(1.0, cumulative_log_width))  # Clamp to 1.0
        band_boundaries[-1] = 1.0  # Ensure last boundary is exactly 1.0
        
        # Map each LED position to a band based on logarithmic frequency distribution
        def get_band_for_position(pos, leds_per_side):
            """Map LED position (0 to leds_per_side-1) to band index (0-31)"""
            # Normalize position to 0.0-1.0
            if leds_per_side <= 1:
                return 0
            normalized_pos = min(1.0, pos / float(leds_per_side - 1))  # Clamp to 1.0
            
            # Find which band this position falls into
            # band_boundaries[i] is the start of band i, band_boundaries[i+1] is the end
            for band_idx in range(32):
                if normalized_pos < band_boundaries[band_idx + 1] or band_idx == 31:
                    return band_idx
            return 31  # Fallback to last band
        
        # Build full 432-LED array: mirrored spectrum from center outward
        leds = []
        for i in range(total_leds):
            dist_from_center = abs(i - center)
            
            # Map distance to band index based on logarithmic distribution
            band_idx = get_band_for_position(dist_from_center, leds_per_side)
            
            # Energy in this band
            band_energy = float(spectrum[band_idx])
            
            # Hue for this band: red (0°) at band 0, blue (240°) at band 31
            band_hue = LEDEffects.get_band_hue(band_idx)
            
            # Brightness = band energy scaled by LED_BRIGHTNESS
            band_brightness = band_energy * LED_BRIGHTNESS
            
            # Apply perceptual brightness correction for this hue
            brightness_correction = LEDEffects.get_perceptual_brightness_correction(band_hue)
            band_brightness = min(1.0, band_brightness * brightness_correction)
            
            # Convert HSV to RGB
            hue_normalized = band_hue / 360.0
            r_f, g_f, b_f = colorsys.hsv_to_rgb(hue_normalized, 1.0, band_brightness)
            r = int(r_f * 255)
            g = int(g_f * 255)
            b = int(b_f * 255)
            
            leds.append((r, g, b))
        
        # Write to all three strips
        for strip_idx, strip in enumerate(strips):
            for led_idx in range(NUM_LEDS_PER_STRIP):
                absolute_idx = strip_idx * NUM_LEDS_PER_STRIP + led_idx
                strip[led_idx] = leds[absolute_idx]

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

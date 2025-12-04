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
        - Red: 1.0x (baseline, boosted for bass prominence)
        - Green: 0.25x (more sensitive eye perception, but lower bass rarely goes here)
        - Blue: 0.5x (treble gets less emphasis to make bass more prominent)
        
        Args:
            hue_degrees: 0-360 hue value
            
        Returns:
            brightness_multiplier: correction factor for equal perceived brightness
        """
        # Normalize hue to 0-1
        hue_norm = hue_degrees / 360.0
        
        # Pure red (0°) and magenta (300-360°) need full brightness (bass emphasis)
        # Pure green (120°) needs to be dimmed
        # Pure blue (240°) gets reduced brightness (less emphasis on treble)
        
        if hue_norm < 0.083:  # 0-30°: Red to Orange (red dominant, bass emphasis)
            # Linear blend from pure red (1.0) toward orange which has green
            progress = hue_norm / 0.083
            return 1.0 - (progress * 0.75)  # 1.0 down to 0.25 over red range
        elif hue_norm < 0.417:  # 30-150°: Orange to Cyan (green dominant)
            # Green zone is most sensitive, needs heavy dimming
            # Peak dimming at 120° (pure green at 0.25)
            progress = (hue_norm - 0.083) / 0.334  # 0 to 1 in green range
            # Use cosine curve to reach minimum at 120°
            import math
            dimming = 0.25 + (0.75 * math.cos(progress * math.pi))
            return dimming
        else:  # 150-360°: Cyan to Magenta to Red (blue/red dominant)
            # Blue less bright, magenta back toward full red
            progress = (hue_norm - 0.417) / 0.583  # 0 to 1 in blue/red range
            return 0.5 + (progress * 0.5)  # 0.5 up to 1.0 (blue at 0.5, magenta at 1.0)
    
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
        
        # Pre-compute band mapping for all LED positions
        # Map band 0 (lowest freq) at center, band 31 (highest freq) at edges
        # This creates a spread where bass is centered and treble extends outward
        band_map = []  # [(band_idx, pos_in_band), ...] for each position
        for pos in range(leds_per_side):
            if leds_per_side <= 1:
                band_map.append((0, 0.5))
            else:
                # Map position linearly to band index, centered within bands
                # pos=0 (center) starts in band 0, pos=215 (edge) in band 31
                # Use (pos + 0.5) to center LEDs within their band ranges
                band_frac = (pos + 0.5) * 31.0 / leds_per_side
                band_idx = min(31, int(band_frac))
                
                # Position within that band (0.0 at start, 1.0 at end)
                pos_in_band = band_frac - band_idx
                
                band_map.append((band_idx, pos_in_band))
        
        # Build full 432-LED array: mirrored spectrum from center outward
        leds = []
        for i in range(total_leds):
            dist_from_center = abs(i - center)
            
            # Look up pre-computed band mapping
            if dist_from_center < leds_per_side:
                band_idx, pos_in_band = band_map[dist_from_center]
            else:
                band_idx, pos_in_band = 31, 0.5
            
            # Create a WIDE frequency "group" with double the LED count
            # Blend across multiple adjacent bands to create a large, cohesive visual cluster
            # The fundamental band gets peak brightness, spreads far to adjacent bands
            distance_from_center = abs(pos_in_band - 0.5)  # 0.0 at center, 0.5 at edges
            # Even gentler window: (1 - 0.3*x) to keep energy distributed across wider group
            # Brightness stays at 0.7 even at band edges, spreading energy further
            center_weight = max(0.0, 1.0 - distance_from_center * 0.6)  # Very gentle falloff 1.0→0.7
            feathered_energy = center_weight * float(spectrum[band_idx])

            # VERY aggressive feathering: blend adjacent AND second-adjacent bands
            # This creates a wide, strong visual cluster that's 2x the previous width
            # Goal: twice as many LEDs lit for the same tone
            
            # First adjacent bands: high contribution (40% max)
            if band_idx > 0:
                # Previous adjacent band contributes strongly
                prev_weight = 0.40 * max(0.0, (pos_in_band - 0.10) / 0.40)  # Ramps 0.0-0.40 as pos goes 0.10-0.50
                feathered_energy += prev_weight * float(spectrum[band_idx - 1])

            if band_idx < 31:
                # Next adjacent band contributes strongly
                next_weight = 0.40 * max(0.0, (0.90 - pos_in_band) / 0.40)  # Ramps 0.40-0.0 as pos goes 0.50-0.90
                feathered_energy += next_weight * float(spectrum[band_idx + 1])
            
            # Second adjacent bands: moderate contribution (15% max) to extend the group further
            if band_idx > 1:
                # Second-previous adjacent band contributes moderately
                prev2_weight = 0.15 * max(0.0, (pos_in_band - 0.0) / 0.50)  # Ramps 0.0-0.15 as pos goes 0.0-0.50
                feathered_energy += prev2_weight * float(spectrum[band_idx - 2])

            if band_idx < 30:
                # Second-next adjacent band contributes moderately
                next2_weight = 0.15 * max(0.0, (1.0 - pos_in_band) / 0.50)  # Ramps 0.15-0.0 as pos goes 0.50-1.0
                feathered_energy += next2_weight * float(spectrum[band_idx + 2])

            feathered_energy = min(1.0, feathered_energy)

            # Hue for this band: red (0°) at band 0, blue (240°) at band 31
            band_hue = LEDEffects.get_band_hue(band_idx)
            
            # Brightness = feathered energy scaled by LED_BRIGHTNESS
            band_brightness = feathered_energy * LED_BRIGHTNESS
            
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

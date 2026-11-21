"""Visual effects that map audio features to LED patterns"""

import colorsys
import numpy as np
from config import (
    COLORS, NUM_LEDS_PER_STRIP, NUM_STRIPS, LED_BRIGHTNESS,
    HUE_RANGE, EDGE_HUE_SHIFT, CORE_FRACTION_MIN, CORE_FRACTION_MAX,
    MIN_BRIGHTNESS, EDGE_FADE_RATE, TRANSIENT_BOOST, BRIGHTNESS_EXPONENT, FREQ_BANDS,
    get_live_params,
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

    # Class-level state for smoothing and live web preview
    _prev_hue = 0.0
    _prev_brightness = 0.0
    _prev_edge = 0.0
    _prev_bass = 0.0  # Track bass intensity separately for faster decay
    last_leds = [(0, 0, 0)] * (NUM_LEDS_PER_STRIP * NUM_STRIPS)
    
    @staticmethod
    def get_band_hue(band_index, bass_hue=0.0, treble_hue=240.0):
        """Map band index 0-31 to smooth hue gradient emphasizing reds and blues.
        
        Red/Orange (bass) → Blue/Cyan (treble), skipping muddy yellow/green midtones.
        
        Args:
            band_index: 0-31 spectrum band index
            bass_hue: center hue in degrees (default 0.0)
            treble_hue: outer edge hue in degrees (default 240.0)
            
        Returns:
            hue: 0-360 degrees
        """
        # Emphasize warm reds/oranges and cool blues, skip yellow/green when at default palette
        if abs(bass_hue - 0.0) < 0.5 and abs(treble_hue - 240.0) < 0.5:
            if band_index < 16:
                # Bands 0-15: Red (0°) to Orange (30°) - bass/mid warmth
                return (band_index / 16.0) * 30.0
            else:
                # Bands 16-31: Cyan (180°) to Blue (240°) - high-mid/treble cool
                return 180.0 + ((band_index - 16) / 16.0) * 60.0

        # Custom user-selected bass → treble hue palette
        if band_index < 16:
            return (bass_hue + (band_index / 16.0) * 30.0) % 360.0
        else:
            progress = (band_index - 16) / 16.0
            start_cool = (treble_hue - 60.0) % 360.0
            return (start_cool + progress * 60.0) % 360.0
    
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
        
        params = get_live_params()
        master_brightness = float(params.get("brightness", LED_BRIGHTNESS))
        response_intensity = float(params.get("response_intensity", 1.15))
        easing_exponent = float(params.get("easing_exponent", 1.25))
        cluster_width = float(params.get("cluster_width", 1.10))
        root_focus = float(params.get("root_focus", 0.80))
        root_real_estate = float(params.get("root_real_estate", 1.65))
        bass_hue = float(params.get("bass_hue", 0.0))
        treble_hue = float(params.get("treble_hue", 240.0))
        perceptual_blend = float(params.get("perceptual_correction", 1.0))

        # Pre-compute band mapping for all LED positions
        # Map band 0 (lowest freq) at center, band 31 (highest freq) at edges
        # root_real_estate > 1.0 warps physical strip space so audible root bands (0-20)
        # get up to ~75% of the physical LEDs across the 3 strips
        band_map = []  # [(band_idx, pos_in_band), ...] for each position
        for pos in range(leds_per_side):
            if leds_per_side <= 1:
                band_map.append((0, 0.5))
            else:
                norm_pos = (pos + 0.5) / leds_per_side
                warped_pos = norm_pos ** max(0.5, root_real_estate)
                band_frac = warped_pos * 31.0
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
            
            # Dynamic root expansion: audible root bands (bands 0-20, <950 Hz) expand wider
            # when they carry strong defining energy
            root_zone_factor = max(0.0, 1.0 - (band_idx / 22.0))
            local_peak_energy = float(spectrum[band_idx])
            effective_cluster = cluster_width * (1.0 + 0.35 * root_focus * root_zone_factor * local_peak_energy)

            # Create an EXTRA-WIDE frequency "group" with 4x the original LED count
            # Blend across FOUR levels of adjacent bands for a massive, cohesive visual cluster
            # The fundamental band gets peak brightness, spreads far to adjacent bands
            distance_from_center = abs(pos_in_band - 0.5)  # 0.0 at center, 0.5 at edges
            # Minimal falloff: (1 - 0.2*x) to keep energy distributed across very wide group
            # Brightness stays at 0.8 even at band edges, spreading energy very far
            falloff_rate = 0.4 if effective_cluster >= 1.0 else (0.4 + (1.0 - effective_cluster) * 1.2)
            center_weight = max(0.0, 1.0 - distance_from_center * falloff_rate)  # Very gentle falloff 1.0→0.8
            feathered_energy = center_weight * local_peak_energy

            # EXTREMELY aggressive feathering: blend 4 levels of adjacent bands
            # Scaled by effective_cluster (1.0 = default 4x wide blob, 0.0 = single band, >1.0 = wider)
            w1 = 0.50 * effective_cluster
            w2 = 0.35 * effective_cluster
            w3 = 0.20 * effective_cluster
            w4 = 0.10 * effective_cluster
            
            # First adjacent bands: very high contribution (50% max at default)
            if band_idx > 0 and w1 > 0.0:
                prev_weight = w1 * max(0.0, (pos_in_band - 0.0) / 0.50)  # Full range blend
                feathered_energy += prev_weight * float(spectrum[band_idx - 1])

            if band_idx < 31 and w1 > 0.0:
                next_weight = w1 * max(0.0, (1.0 - pos_in_band) / 0.50)  # Full range blend
                feathered_energy += next_weight * float(spectrum[band_idx + 1])
            
            # Second adjacent bands: high contribution (35% max at default)
            if band_idx > 1 and w2 > 0.0:
                prev2_weight = w2 * max(0.0, (pos_in_band - 0.0) / 0.50)
                feathered_energy += prev2_weight * float(spectrum[band_idx - 2])

            if band_idx < 30 and w2 > 0.0:
                next2_weight = w2 * max(0.0, (1.0 - pos_in_band) / 0.50)
                feathered_energy += next2_weight * float(spectrum[band_idx + 2])
            
            # Third adjacent bands: moderate contribution (20% max at default)
            if band_idx > 2 and w3 > 0.0:
                prev3_weight = w3 * max(0.0, (pos_in_band - 0.0) / 0.50)
                feathered_energy += prev3_weight * float(spectrum[band_idx - 3])

            if band_idx < 29 and w3 > 0.0:
                next3_weight = w3 * max(0.0, (1.0 - pos_in_band) / 0.50)
                feathered_energy += next3_weight * float(spectrum[band_idx + 3])
            
            # Fourth adjacent bands: light contribution (10% max at default)
            if band_idx > 3 and w4 > 0.0:
                prev4_weight = w4 * max(0.0, (pos_in_band - 0.0) / 0.50)
                feathered_energy += prev4_weight * float(spectrum[band_idx - 4])

            if band_idx < 28 and w4 > 0.0:
                next4_weight = w4 * max(0.0, (1.0 - pos_in_band) / 0.50)
                feathered_energy += next4_weight * float(spectrum[band_idx + 4])

            feathered_energy = min(1.0, feathered_energy * response_intensity)
            if feathered_energy > 0.0 and abs(easing_exponent - 1.0) > 0.01:
                feathered_energy = feathered_energy ** easing_exponent

            # Hue for this band: red (0°) at band 0, blue (240°) at band 31
            band_hue = LEDEffects.get_band_hue(band_idx, bass_hue=bass_hue, treble_hue=treble_hue)
            
            # Brightness = feathered energy scaled by master_brightness
            band_brightness = feathered_energy * master_brightness
            
            # Apply perceptual brightness correction for this hue
            raw_correction = LEDEffects.get_perceptual_brightness_correction(band_hue)
            brightness_correction = (1.0 - perceptual_blend) + (perceptual_blend * raw_correction)
            band_brightness = min(1.0, band_brightness * brightness_correction)
            
            # Convert HSV to RGB
            hue_normalized = band_hue / 360.0
            r_f, g_f, b_f = colorsys.hsv_to_rgb(hue_normalized, 1.0, band_brightness)
            r = int(r_f * 255)
            g = int(g_f * 255)
            b = int(b_f * 255)
            
            leds.append((r, g, b))
        
        LEDEffects.last_leds = leds

        # Write to all three strips if hardware/mock strips are provided
        if strips is not None:
            for strip_idx, strip in enumerate(strips):
                for led_idx in range(NUM_LEDS_PER_STRIP):
                    absolute_idx = strip_idx * NUM_LEDS_PER_STRIP + led_idx
                    strip[led_idx] = leds[absolute_idx]
        return leds

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

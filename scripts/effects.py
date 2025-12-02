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
            # Bands 16-31: Blue (240°) to Cyan (210°) - high-mid/treble cool
            # 16 bands spread over 30° of blue spectrum
            return 240.0 - ((band_index - 16) / 16.0) * 30.0
    
    @staticmethod
    def get_perceptual_brightness_correction(hue_degrees):
        """No correction - let brightness envelope handle overall brightness.
        
        Perceptual brightness correction in HSV value space causes desaturation/washed-out colors.
        Instead, we manage brightness through the audio envelope and edge intensity parameters.
        Red dominance is achieved by controlling blue edge saturation/intensity separately.
        
        Args:
            hue_degrees: 0-360 hue value
            
        Returns:
            brightness_multiplier: always 1.0 (no correction)
        """
        return 1.0
    
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
            # Use smooth 32-band hue gradient for tonal sounds
            target_hue = LEDEffects.get_band_hue(dominant_band)
        else:
            # Fall back to blended hue for noisy/broadband sounds
            target_hue = blended_hue
        
        # Brightness from envelope - go fully dark when envelope is near zero
        if envelope < 0.01:
            target_brightness = 0.0
        else:
            target_brightness = max(MIN_BRIGHTNESS, envelope ** BRIGHTNESS_EXPONENT)
        
        # Edge intensity from treble (now 0-1 range since we use mean)
        target_edge = treble_energy  # Direct mapping, already 0-1
        
        # Smoothing - very snappy for dynamic range
        attack = 0.8
        decay = 0.15
        
        # Hue smoothing
        hue_diff = target_hue - LEDEffects._prev_hue
        LEDEffects._prev_hue += hue_diff * (attack if hue_diff > 0 else decay)
        
        # Brightness smoothing - very aggressive decay to zero for dynamic peaks
        if target_brightness > LEDEffects._prev_brightness:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * attack
        elif target_brightness < 0.01:
            LEDEffects._prev_brightness *= 0.4  # Very fast fade to black
        else:
            LEDEffects._prev_brightness += (target_brightness - LEDEffects._prev_brightness) * decay
        
        # Edge smoothing - instant rise, snappy decay
        if target_edge > LEDEffects._prev_edge:
            LEDEffects._prev_edge = target_edge  # Instant
        else:
            LEDEffects._prev_edge += (target_edge - LEDEffects._prev_edge) * 0.25  # Fast decay
        
        # Bass smoothing - instant rise, ultra-aggressive decay for maximum movement
        if bass_energy > LEDEffects._prev_bass:
            LEDEffects._prev_bass = bass_energy  # Instant
        else:
            LEDEffects._prev_bass *= 0.5  # Drop to 50% each frame (collapses in ~2 frames)
        
        # Simple: just red core and blue edges, both dynamic
        red_brightness = LEDEffects._prev_bass * LEDEffects._prev_brightness * LED_BRIGHTNESS  # Red follows bass
        blue_brightness = LEDEffects._prev_edge * LED_BRIGHTNESS  # Blue follows treble
        
        # If everything is dark, just black
        if red_brightness < 0.005 and blue_brightness < 0.005:
            for strip in strips:
                strip.fill((0, 0, 0))
            return
        
        # Treat all 432 LEDs as one continuous strip
        total_leds = NUM_LEDS_PER_STRIP * NUM_STRIPS
        center = total_leds // 2
        
        # Red core size and blue edge size
        red_core_size = int(total_leds * 0.45 * LEDEffects._prev_bass)  # 0-45% from center outward (bigger)
        blue_edge_size = int(total_leds * 0.2 * LEDEffects._prev_edge)  # 0-20% on each end
        
        # Build full 432-LED array with feathering
        leds = []
        for i in range(total_leds):
            # Distance from center (0 at center, increases toward edges)
            dist_from_center = abs(i - center)
            
            # Red core: spreads from center outward with dynamic hue feathering based on bass
            # Very bassy = more deeper reds, less feathering
            # Less bassy = more oranges, more feathering
            if red_core_size > 0 and dist_from_center < red_core_size:
                red_blend = max(0.0, 1.0 - (dist_from_center / red_core_size))
                # Dynamic feather zone: high bass = small feather zone (more red), low bass = large feather zone (more orange)
                feather_start = red_core_size * (0.5 + 0.3 * LEDEffects._prev_bass)  # 0.5-0.8 range
                if dist_from_center > feather_start:
                    # In feather zone
                    feather_progress = (dist_from_center - feather_start) / (red_core_size - feather_start)
                    hue_shift = feather_progress * 30.0  # 0° → 30°
                else:
                    # In solid red zone
                    hue_shift = 0.0
                red_hue = hue_shift / 360.0
                red_sat = 1.0
                red_val = red_brightness * red_blend  # Brightness fades with distance
                r_f, g_f, b_f = colorsys.hsv_to_rgb(red_hue, red_sat, red_val)
                r_red = int(r_f * 255)
                g_red = int(g_f * 255)
                b_red = int(b_f * 255)
            else:
                r_red = g_red = b_red = 0
                red_blend = 0.0
            
            # Blue edges: on far left and far right with hue feathering only at inner boundary
            # Blue (240°) for most of it → Cyan (180°) only in inner 20%, with brightness falloff
            dist_from_left = i
            dist_from_right = total_leds - 1 - i
            is_left_edge = dist_from_left < blue_edge_size
            is_right_edge = dist_from_right < blue_edge_size
            
            if is_left_edge or is_right_edge:
                edge_dist = min(dist_from_left if is_left_edge else total_leds, 
                               dist_from_right if is_right_edge else total_leds)
                blue_blend = max(0.0, 1.0 - (edge_dist / max(blue_edge_size, 1)))
                # Only feather in the last 20% before center (inner edge of blue zone)
                feather_start = blue_edge_size * 0.8
                if edge_dist > feather_start:
                    # In feather zone (far from outer edge, close to center)
                    feather_progress = (edge_dist - feather_start) / (blue_edge_size - feather_start)
                    hue_shift = feather_progress * 60.0  # 240° → 180°
                else:
                    # In solid blue zone (close to outer edge)
                    hue_shift = 0.0
                blue_hue = (240.0 - hue_shift) / 360.0
                blue_sat = 1.0
                blue_val = blue_brightness * blue_blend  # Brightness fades with distance
                r_f, g_f, b_f = colorsys.hsv_to_rgb(blue_hue, blue_sat, blue_val)
                r_blue = int(r_f * 255)
                g_blue = int(g_f * 255)
                b_blue = int(b_f * 255)
            else:
                r_blue = g_blue = b_blue = 0
                blue_blend = 0.0
            
            # Mix red and blue
            r = int(max(0, min(255, r_red + r_blue)))
            g = int(max(0, min(255, g_red + g_blue)))
            b = int(max(0, min(255, b_red + b_blue)))
            
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

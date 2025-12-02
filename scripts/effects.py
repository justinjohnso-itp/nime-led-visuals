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
        
        # Edge smoothing - treble with slow decay for trailing effect
        if target_edge > LEDEffects._prev_edge:
            LEDEffects._prev_edge += (target_edge - LEDEffects._prev_edge) * 0.95  # Quick rise
        else:
            LEDEffects._prev_edge += (target_edge - LEDEffects._prev_edge) * 0.02  # Slow decay for trail
        
        # Bass smoothing - slow decay for sustained presence
        if bass_energy > LEDEffects._prev_bass:
            LEDEffects._prev_bass += (bass_energy - LEDEffects._prev_bass) * 0.95
        else:
            LEDEffects._prev_bass += (bass_energy - LEDEffects._prev_bass) * 0.01  # Very slow decay
        
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
        
        # Red core size and blue edge size (bigger red core now)
        red_core_size = int(total_leds * 0.3 * LEDEffects._prev_bass)  # 0-30% from center outward
        blue_edge_size = int(total_leds * 0.2 * LEDEffects._prev_edge)  # 0-20% on each end
        
        # Build full 432-LED array
        leds = []
        for i in range(total_leds):
            # Distance from center (0 at center, increases toward edges)
            dist_from_center = abs(i - center)
            
            # Red core: spreads from center outward
            red_blend = max(0.0, 1.0 - (dist_from_center / max(red_core_size, 1))) if red_core_size > 0 else 0.0
            
            # Blue edges: on far left and far right
            dist_from_left = i
            dist_from_right = total_leds - 1 - i
            blue_blend = 1.0 if (dist_from_left < blue_edge_size or dist_from_right < blue_edge_size) else 0.0
            
            # Mix red and blue
            r = int(red_brightness * 255 * red_blend + blue_brightness * 0 * blue_blend)
            g = int(red_brightness * 0 * red_blend + blue_brightness * 0 * blue_blend)
            b = int(red_brightness * 0 * red_blend + blue_brightness * 255 * blue_blend)
            
            leds.append((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))
        
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
